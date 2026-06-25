"""Tiny in-process sliding-window rate limiter.

Sufficient for a single-worker event deployment. If you run multiple workers, move this
to Redis (the bank already requires one) so the window is shared.
"""
from __future__ import annotations

import time
from collections import defaultdict

_hits: dict[str, list[float]] = defaultdict(list)


def allow(key: str, limit: int, window_seconds: int) -> bool:
    """Record an attempt for `key`; return False if it exceeds `limit` within the window."""
    now = time.time()
    cutoff = now - window_seconds
    recent = [t for t in _hits[key] if t > cutoff]
    if len(recent) >= limit:
        _hits[key] = recent
        return False
    recent.append(now)
    _hits[key] = recent
    return True
