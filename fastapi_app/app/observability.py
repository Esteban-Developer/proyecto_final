from __future__ import annotations

import logging
import uuid

from fastapi import Request


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def new_request_id() -> str:
    return str(uuid.uuid4())


def request_id_from_request(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if isinstance(rid, str) and rid.strip():
        return rid
    return new_request_id()


def log_api(request: Request, message: str) -> None:
    rid = request_id_from_request(request)
    logging.info("[API][%s] %s", rid, message)


def log_worker(request_id: str, message: str) -> None:
    logging.info("[WORKER][%s] %s", request_id, message)


def log_rabbitmq(request_id: str, message: str) -> None:
    logging.info("[RABBITMQ][%s] %s", request_id, message)


def log_redis(request_id: str, message: str) -> None:
    logging.info("[REDIS][%s] %s", request_id, message)

