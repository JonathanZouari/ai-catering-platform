"""Limits per client address. Counts live in memory, which suits the single pilot server;
more than one server would need a shared store."""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError

MAX_TRACKED_KEYS = 50_000

_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = Lock()


def reset() -> None:
    with _lock:
        _hits.clear()


def client_address(request: Request) -> str:
    """Behind Railway, the proxy appends the real address last. Earlier entries are whatever
    the client sent, and locally the header isn't trusted at all."""
    forwarded = request.headers.getlist("x-forwarded-for")
    if forwarded and get_settings().is_deployed:
        return forwarded[-1].rsplit(",", 1)[-1].strip()
    return request.client.host if request.client else "unknown"


def _exceeded(name: str, address: str, limit: int, window: float) -> bool:
    now = monotonic()
    with _lock:
        if len(_hits) > MAX_TRACKED_KEYS:
            _hits.clear()
        hits = _hits[(name, address)]
        while hits and now - hits[0] >= window:
            hits.popleft()
        if len(hits) >= limit:
            return True
        hits.append(now)
        return False


def _enforce(request: Request, name: str, limit: int, window: float) -> None:
    if _exceeded(name, client_address(request), limit, window):
        raise AppError(429, "rate_limited", "יותר מדי בקשות. נסו שוב בעוד כמה דקות")


def limit_order_creation(request: Request) -> None:
    _enforce(request, "order_creation", 20, 3600)


def limit_order_writes(request: Request) -> None:
    if request.method != "GET":
        _enforce(request, "order_writes", 120, 60)


def limit_chat(request: Request) -> None:
    _enforce(request, "chat", 15, 60)
