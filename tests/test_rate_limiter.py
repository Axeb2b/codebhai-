"""Unit tests for the rate limiter (rate_limiter.py)."""

import asyncio
import time
import pytest

from rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_acquire_within_limits():
    """Acquiring tokens within the limits should not block."""
    limiter = RateLimiter(messages_per_second=5, messages_per_minute=60)
    start = time.monotonic()
    for _ in range(5):
        await limiter.acquire()
    elapsed = time.monotonic() - start
    # Should complete well under 1 second
    assert elapsed < 0.5


@pytest.mark.asyncio
async def test_per_second_limit_enforced():
    """Exceeding the per-second limit should introduce a delay."""
    limiter = RateLimiter(messages_per_second=2, messages_per_minute=100)
    start = time.monotonic()
    for _ in range(3):
        await limiter.acquire()
    elapsed = time.monotonic() - start
    # 3rd token should have waited ~1 second
    assert elapsed >= 0.9


@pytest.mark.asyncio
async def test_current_second_count():
    """current_second_count should reflect sent messages in the last second."""
    limiter = RateLimiter(messages_per_second=10, messages_per_minute=100)
    assert limiter.current_second_count == 0
    await limiter.acquire()
    await limiter.acquire()
    assert limiter.current_second_count == 2


@pytest.mark.asyncio
async def test_current_minute_count():
    """current_minute_count should reflect sent messages in the last minute."""
    limiter = RateLimiter(messages_per_second=10, messages_per_minute=100)
    assert limiter.current_minute_count == 0
    await limiter.acquire()
    assert limiter.current_minute_count == 1


@pytest.mark.asyncio
async def test_multiple_coroutines_respect_limits():
    """Concurrent acquires should not exceed the per-second limit."""
    limiter = RateLimiter(messages_per_second=3, messages_per_minute=100)
    results = []

    async def acquire_and_record():
        await limiter.acquire()
        results.append(time.monotonic())

    tasks = [asyncio.create_task(acquire_and_record()) for _ in range(6)]
    await asyncio.gather(*tasks)

    # First 3 should be in the first second, next 3 in the second
    assert len(results) == 6
    # The 4th result should be at least ~1 second after the 1st
    results.sort()
    assert results[3] - results[0] >= 0.9


@pytest.mark.asyncio
async def test_clean_windows_removes_old_entries():
    """After waiting, old timestamps should be purged from the window."""
    limiter = RateLimiter(messages_per_second=2, messages_per_minute=100)
    await limiter.acquire()
    await limiter.acquire()
    assert limiter.current_second_count == 2

    # Manually age the timestamps
    now = time.monotonic()
    while limiter._second_window:
        limiter._second_window.popleft()
    limiter._second_window.append(now - 2)  # expired

    assert limiter.current_second_count == 0
