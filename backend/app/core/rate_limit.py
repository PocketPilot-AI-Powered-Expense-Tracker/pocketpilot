"""Tiny in-memory per-user rate limiter for AI endpoints (single-instance deployments)."""
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, status

from app.core.config import get_settings
from app.core.deps import get_current_user

WINDOW_SECONDS = 600
_hits: dict[str, deque] = defaultdict(deque)


def reset() -> None:
    _hits.clear()


def hit(key: str, limit: int, window: int = WINDOW_SECONDS) -> bool:
    """Record one attempt for `key`. Returns False if the limit is exceeded."""
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


async def ai_rate_limit(user=Depends(get_current_user)) -> dict:
    if not hit(f"ai:{user['_id']}", get_settings().AI_RATE_LIMIT_PER_10_MIN):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many AI requests. Please wait a few minutes.")
    return user


LOGIN_ATTEMPTS_PER_10_MIN = 10


def check_login_rate(email: str, client_ip: str) -> None:
    """Slow down password guessing: max 10 attempts per email+IP per 10 minutes."""
    if not hit(f"login:{email.lower()}:{client_ip}", LOGIN_ATTEMPTS_PER_10_MIN):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts. Please wait 10 minutes and try again.")
