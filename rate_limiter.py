"""Rate limiter to comply with WhatsApp/Bird.com API policies."""

import asyncio
import time
import os
from collections import deque
from typing import Deque


class RateLimiter:
    """
    Token-bucket based rate limiter that enforces per-second and per-minute limits.

    Attributes:
        messages_per_second: Maximum messages allowed per second.
        messages_per_minute: Maximum messages allowed per minute.
    """

    def __init__(
        self,
        messages_per_second: int | None = None,
        messages_per_minute: int | None = None,
    ) -> None:
        self.messages_per_second = messages_per_second or int(
            os.getenv("RATE_LIMIT_MESSAGES_PER_SECOND", "10")
        )
        self.messages_per_minute = messages_per_minute or int(
            os.getenv("RATE_LIMIT_MESSAGES_PER_MINUTE", "100")
        )

        # Sliding window queues storing timestamps of sent messages
        self._second_window: Deque[float] = deque()
        self._minute_window: Deque[float] = deque()
        self._lock = asyncio.Lock()

    def _clean_windows(self, now: float) -> None:
        """Remove expired timestamps from sliding windows."""
        while self._second_window and self._second_window[0] <= now - 1:
            self._second_window.popleft()
        while self._minute_window and self._minute_window[0] <= now - 60:
            self._minute_window.popleft()

    async def acquire(self) -> None:
        """
        Wait until a send token is available, then consume one.

        This method blocks asynchronously until rate limits allow the next send.
        """
        async with self._lock:
            while True:
                now = time.monotonic()
                self._clean_windows(now)

                per_second_ok = len(self._second_window) < self.messages_per_second
                per_minute_ok = len(self._minute_window) < self.messages_per_minute

                if per_second_ok and per_minute_ok:
                    self._second_window.append(now)
                    self._minute_window.append(now)
                    return

                # Calculate wait time
                wait = 0.0
                if not per_second_ok:
                    wait = max(wait, self._second_window[0] + 1 - now)
                if not per_minute_ok:
                    wait = max(wait, self._minute_window[0] + 60 - now)

                # Release lock while sleeping so other coroutines can check
                self._lock.release()
                try:
                    await asyncio.sleep(wait)
                finally:
                    await self._lock.acquire()

    @property
    def current_second_count(self) -> int:
        """Return the number of messages sent in the current second window."""
        now = time.monotonic()
        self._clean_windows(now)
        return len(self._second_window)

    @property
    def current_minute_count(self) -> int:
        """Return the number of messages sent in the current minute window."""
        now = time.monotonic()
        self._clean_windows(now)
        return len(self._minute_window)
