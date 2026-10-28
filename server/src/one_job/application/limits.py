"""Small per-connection token buckets; no account or room state."""

from collections import deque


class TokenBucket:
    def __init__(self, rate: float, capacity: int, now: float) -> None:
        self._rate = rate
        self._capacity = capacity
        self._tokens = float(capacity)
        self._updated = now

    def take(self, now: float) -> bool:
        self._tokens = min(
            self._capacity, self._tokens + max(0.0, now - self._updated) * self._rate
        )
        self._updated = now
        if self._tokens < 1:
            return False
        self._tokens -= 1
        return True


class MessageBudget:
    def __init__(self, now: float) -> None:
        self._commands = TokenBucket(20, 40, now)
        self._pings = TokenBucket(1, 3, now)
        self._violations: deque[float] = deque(maxlen=5)

    def take(self, now: float, ping: bool) -> tuple[bool, bool]:
        if (self._pings if ping else self._commands).take(now):
            return True, False
        while self._violations and now - self._violations[0] >= 10:
            self._violations.popleft()
        self._violations.append(now)
        return False, len(self._violations) == 5
