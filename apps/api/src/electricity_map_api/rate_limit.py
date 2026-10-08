"""Public API quotas by client address, without authentication."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from fastapi import Request, Response

from electricity_map_api.config import Settings
from electricity_map_api.exceptions import APIError
from electricity_map_api.schemas import ErrorResponse

RATE_LIMIT_RESPONSES = {
    429: {
        "model": ErrorResponse,
        "description": "Request quota exhausted",
        "headers": {
            "Retry-After": {"description": "Seconds until the quota resets", "schema": {"type": "integer"}},
        },
    },
}


class QuotaExhausted(APIError):
    status_code = 429
    detail = "Request quota exhausted"

    def __init__(self, reset_seconds: int) -> None:
        super().__init__(self.detail)
        self.headers = {"Retry-After": str(reset_seconds)}


@dataclass(slots=True)
class RateLimitWindow:
    started_at: float
    requests: int


class InMemoryRateLimiter:
    """Single-process limiter; distributed deployments need a shared store."""

    def __init__(self, window_seconds: int) -> None:
        self._window_seconds = window_seconds
        self._windows: dict[str, RateLimitWindow] = {}
        self._lock = asyncio.Lock()

    async def consume(self, address: str, limit: int) -> tuple[int, int]:
        """Consume one request and return remaining requests and reset seconds."""
        now = time.monotonic()
        async with self._lock:
            window = self._windows.get(address)
            if window is None or now - window.started_at >= self._window_seconds:
                window = RateLimitWindow(started_at=now, requests=0)
                self._windows[address] = window
            reset_seconds = max(1, int(self._window_seconds - (now - window.started_at)))
            if window.requests >= limit:
                raise QuotaExhausted(reset_seconds)
            window.requests += 1
            return limit - window.requests, reset_seconds


async def enforce_rate_limit(request: Request, response: Response) -> None:
    settings: Settings = request.app.state.settings
    if settings.development_mode:
        return
    limiter: InMemoryRateLimiter = request.app.state.rate_limiter
    address = request.client.host if request.client else "unknown"
    remaining, reset_seconds = await limiter.consume(address, settings.request_limit)
    response.headers["X-RateLimit-Limit"] = str(settings.request_limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_seconds)
