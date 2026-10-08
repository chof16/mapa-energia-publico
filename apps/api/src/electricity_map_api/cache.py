"""Optional shared Redis cache of validated responses, independent of SQL sessions."""

import json
import logging
from collections.abc import Callable
from hashlib import sha256
from threading import Lock
from time import monotonic
from typing import Annotated

from fastapi import Depends, Request, Response
from pydantic import BaseModel, ValidationError
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

logger = logging.getLogger(__name__)
MAX_RESPONSE_BYTES = 1_048_576


class RedisResponseCache:
    def __init__(self, client: Redis, source: str, ttl_seconds: int = 300) -> None:
        self.client = client
        self.ttl_seconds = ttl_seconds
        self.prefix = f"electricity-map:responses:v1:{sha256(source.encode()).hexdigest()}:"
        # Bounded locks coalesce concurrent misses within the single API process.
        self.locks = [Lock() for _ in range(64)]
        self.unavailable_until = 0.0

    def load[T: BaseModel](self, key: str, model: type[T], loader: Callable[[], T]) -> tuple[T, str]:
        if monotonic() < self.unavailable_until:
            return loader(), "BYPASS"
        digest = sha256(key.encode()).hexdigest()
        with self.locks[int(digest[:8], 16) % len(self.locks)]:
            if monotonic() < self.unavailable_until:
                return loader(), "BYPASS"
            cache_key = self.prefix + digest
            try:
                payload = self.client.get(cache_key)
                if payload and len(payload) <= MAX_RESPONSE_BYTES and payload.lstrip().startswith(b"{"):
                    try:
                        return model.model_validate_json(payload), "HIT"
                    except ValidationError:
                        pass
            except RedisError:
                self._unavailable()
                return loader(), "BYPASS"
            # Exceptions from the database or response validation are never cached.
            result = loader()
            payload = result.model_dump_json().encode()
            if len(payload) <= MAX_RESPONSE_BYTES:
                try:
                    self.client.set(cache_key, payload, ex=self.ttl_seconds)
                except RedisError:
                    self._unavailable()
            return result, "MISS"

    def _unavailable(self) -> None:
        self.unavailable_until = monotonic() + 30
        # Never log a connection URL, password or the exception containing them.
        logger.warning("Redis response cache unavailable; bypassing it for 30 seconds")

    def close(self) -> None:
        self.client.close()


def create_response_cache(url: str | None, source: str, ttl_seconds: int) -> RedisResponseCache | None:
    if not url:
        return None
    client = Redis.from_url(
        url,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
        max_connections=16,
        retry=Retry(NoBackoff(), 0),
        decode_responses=False,
    )
    return RedisResponseCache(client, source, ttl_seconds)


class ResponseCache:
    def __init__(self, backend: RedisResponseCache | None, response: Response) -> None:
        self.backend = backend
        self.response = response

    def load[T: BaseModel](
        self, operation: str, query: BaseModel, model: type[T], loader: Callable[[], T], **path: str
    ) -> T:
        if self.backend is None:
            self.response.headers["X-Cache"] = "BYPASS"
            return loader()
        key = json.dumps([operation, query.model_dump(mode="json"), path], sort_keys=True, separators=(",", ":"))
        result, status = self.backend.load(key, model, loader)
        self.response.headers["X-Cache"] = status
        return result


def get_response_cache(request: Request, response: Response) -> ResponseCache:
    return ResponseCache(request.app.state.response_cache, response)


CachedResponse = Annotated[ResponseCache, Depends(get_response_cache)]
