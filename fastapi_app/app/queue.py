from __future__ import annotations

import json
import uuid

import pika

from .settings import get_settings


class QueueConnectionError(Exception):
    pass


settings = get_settings()


def _connection_params() -> pika.ConnectionParameters:
    credentials = pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_password)
    return pika.ConnectionParameters(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        virtual_host=settings.rabbitmq_vhost,
        credentials=credentials,
        heartbeat=30,
        blocked_connection_timeout=30,
    )


def enqueue_order_request(payload: dict, request_id: str | None = None) -> str:
    request_id = request_id or str(uuid.uuid4())
    body = {"request_id": request_id, **payload}

    try:
        conn = pika.BlockingConnection(_connection_params())
        ch = conn.channel()
        ch.queue_declare(queue=settings.rabbitmq_queue_orders, durable=True)
        ch.basic_publish(
            exchange="",
            routing_key=settings.rabbitmq_queue_orders,
            body=json.dumps(body).encode("utf-8"),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        from .observability import log_rabbitmq
        log_rabbitmq(request_id, "mensaje enviado")
        conn.close()
    except Exception as exc:  # noqa: BLE001
        raise QueueConnectionError(str(exc)) from exc

    return request_id


def consume_order_requests(callback) -> None:
    conn = pika.BlockingConnection(_connection_params())
    ch = conn.channel()
    ch.queue_declare(queue=settings.rabbitmq_queue_orders, durable=True)
    ch.basic_qos(prefetch_count=1)

    def _wrapped(chx, method, properties, body):
        callback(chx, method, properties, body)

    ch.basic_consume(queue=settings.rabbitmq_queue_orders, on_message_callback=_wrapped)
    print(f"[*] Worker escuchando cola: {settings.rabbitmq_queue_orders}")
    ch.start_consuming()
