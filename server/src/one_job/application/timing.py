"""Injected monotonic deadlines and a pull-driven fixed-step tick source."""

import asyncio
from collections.abc import Coroutine
from typing import Protocol

from one_job.domain.config import TICK_MS


class Clock(Protocol):
    def now(self) -> float: ...
    async def wait_until(self, deadline: float) -> None: ...


class SystemClock:
    def now(self) -> float:
        return asyncio.get_running_loop().time()

    async def wait_until(self, deadline: float) -> None:
        await asyncio.sleep(max(0.0, deadline - self.now()))


class TickSource(Protocol):
    async def wait_next(self) -> None: ...


class FixedStepTicker:
    """One awaited deadline per request; creates no background game task."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._deadline = clock.now()

    async def wait_next(self) -> None:
        self._deadline += TICK_MS / 1000
        await self._clock.wait_until(self._deadline)


async def with_deadline[T](
    operation: Coroutine[object, object, T], clock: Clock, seconds: float, name: str
) -> T:
    work = asyncio.create_task(operation, name=f"one_job:{name}:io")
    timer = asyncio.create_task(
        clock.wait_until(clock.now() + seconds), name=f"one_job:{name}:timer"
    )
    try:
        await asyncio.wait((work, timer), return_when=asyncio.FIRST_COMPLETED)
        if work.done():
            return work.result()
        timer.result()
        raise TimeoutError("I/O deadline expired")
    finally:
        for task in (work, timer):
            if not task.done():
                task.cancel()
        await asyncio.gather(work, timer, return_exceptions=True)
