from __future__ import annotations

import json
import os
import time

from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import CartItem, Order, Product
from .observability import setup_logging, log_worker
from .order_status import set_order_status
from .queue import consume_order_requests


def _get_processing_delay_seconds() -> int:
    raw_value = os.getenv("ORDER_PROCESSING_DELAY_SECONDS", "0").strip()
    try:
        return max(int(raw_value), 0)
    except ValueError:
        return 0


def _process_order_message(ch, method, properties, body: bytes) -> None:
    request_id = "unknown"
    db: Session = SessionLocal()
    try:
        payload = json.loads(body.decode("utf-8"))
        request_id = str(payload["request_id"])
        log_worker(request_id, "Evento recibido desde RabbitMQ")
        customer_email = str(payload["customer_email"])
        customer_id = int(payload["customer_id"])

        items = db.query(CartItem).filter(CartItem.c_id == customer_email).all()
        if not items:
            set_order_status(request_id, "FAILED")
            log_worker(request_id, "Sin items en carrito, estado FAILED")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        product_ids = [i.products_id for i in items]
        products = db.query(Product).filter(Product.products_id.in_(product_ids)).all()
        price_by_id = {p.products_id: int(p.product_price) for p in products}

        total_q = 0
        final_price = 0
        for i in items:
            total_q += int(i.qty)
            final_price += int(price_by_id.get(i.products_id, 0)) * int(i.qty)

        order = Order(order_qty=total_q, order_price=final_price, c_id=customer_id)
        db.add(order)
        db.query(CartItem).filter(CartItem.c_id == customer_email).delete()
        db.commit()
        log_worker(request_id, "Orden persistida en MySQL y carrito limpiado")

        delay_seconds = _get_processing_delay_seconds()
        if delay_seconds > 0:
            log_worker(request_id, f"Simulando demora de {delay_seconds}s")
            time.sleep(delay_seconds)

        set_order_status(request_id, "CONFIRMED")
        log_worker(request_id, "Estado en Redis actualizado a CONFIRMED")
        log_worker(request_id, "Evento procesado")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        set_order_status(request_id, "FAILED")
        log_worker(request_id, f"Error procesando evento: {exc}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    finally:
        db.close()


def run_worker() -> None:
    setup_logging()
    consume_order_requests(_process_order_message)


if __name__ == "__main__":
    run_worker()
