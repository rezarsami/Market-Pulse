"""
Basic in-memory rate limiting per client key (IP or session id).

Two windows are enforced: a short per-minute burst limit and a daily cap,
to bound worst-case API spend from a single client. This is intentionally
simple in-process state -- fine for a single-instance deployment / demo.
For multi-instance production deployments this would move to Redis, but
that's out of scope for a portfolio project and would add an unneeded
dependency.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class RateLimitDecision:
    allowed: bool
    reason: str = ""
    retry_after_seconds: float = 0.0


class RateLimiter:
    def __init__(self, per_minute: int, per_day: int):
        self.per_minute = per_minute
        self.per_day = per_day
        self._minute_hits: dict[str, deque] = defaultdict(deque)
        self._day_hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check_and_record(self, client_key: str) -> RateLimitDecision:
        now = time.time()
        with self._lock:
            minute_q = self._minute_hits[client_key]
            day_q = self._day_hits[client_key]

            while minute_q and now - minute_q[0] > 60:
                minute_q.popleft()
            while day_q and now - day_q[0] > 86400:
                day_q.popleft()

            if len(minute_q) >= self.per_minute:
                retry_after = 60 - (now - minute_q[0])
                return RateLimitDecision(
                    allowed=False,
                    reason=f"rate limit exceeded: max {self.per_minute} requests/minute",
                    retry_after_seconds=max(retry_after, 1.0),
                )
            if len(day_q) >= self.per_day:
                retry_after = 86400 - (now - day_q[0])
                return RateLimitDecision(
                    allowed=False,
                    reason=f"daily rate limit exceeded: max {self.per_day} requests/day",
                    retry_after_seconds=max(retry_after, 1.0),
                )

            minute_q.append(now)
            day_q.append(now)
            return RateLimitDecision(allowed=True)
