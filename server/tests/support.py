import asyncio
import math


class FakeClock:
    """Loop-local synchronization, advanced explicitly without simulated-time sleeps."""

    def __init__(self):
        self.time = 0.0
        self.waiters = []
        self.changed = asyncio.Condition()

    def now(self):
        return self.time

    async def wait_until(self, deadline):
        async with self.changed:
            if deadline <= self.time:
                return
            future = asyncio.get_running_loop().create_future()
            entry = (deadline, future)
            self.waiters.append(entry)
            self.changed.notify_all()
        try:
            await future
        finally:
            self.waiters.remove(entry)

    async def wait_registered(self, deadline):
        async with self.changed:
            await self.changed.wait_for(
                lambda: any(math.isclose(at, deadline) for at, _ in self.waiters)
            )

    async def advance(self, seconds):
        async with self.changed:
            self.time += seconds
            for deadline, future in self.waiters:
                if deadline <= self.time and not future.done():
                    future.set_result(None)


def frame(kind="ping", *, request_id="p-1", payload=None, version=1):
    return {
        "version": version,
        "type": kind,
        "request_id": request_id,
        "payload": ({"nonce": "hello"} if kind == "ping" else {}) if payload is None else payload,
    }


def owned_tasks():
    return [
        task
        for task in asyncio.all_tasks()
        if task.get_name().startswith("one_job:") and not task.done()
    ]
