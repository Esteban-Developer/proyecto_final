from __future__ import annotations

import redis

from .settings import get_settings


settings = get_settings()


def _redis_client() -> redis.Redis:
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password,
        decode_responses=True,
    )


def set_order_status(request_id: str, status: str, ttl_seconds: int = 3600) -> None:
    key = f"order_status:{request_id}"
    client = _redis_client()
    client.setex(key, ttl_seconds, status)
    from .observability import log_redis
    log_redis(request_id, "lock creado" if status == "PENDING" else f"estado actualizado a {status}")


def get_order_status(request_id: str) -> str | None:
    key = f"order_status:{request_id}"
    client = _redis_client()
    value = client.get(key)
    return value if isinstance(value, str) else None
