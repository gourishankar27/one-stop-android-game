import asyncio
import logging

import anyio
import pytest
from starlette.websockets import WebSocket

from one_job.application.connections import Connection, ConnectionManager, ConnectionSettings
from one_job.protocol.envelopes import error_message
from one_job.protocol.messages import ErrorCode
from tests.support import owned_tasks


class SocketHarness:
    def __init__(
        self,
        *,
        block_send=False,
        block_accept=False,
        broken_send=False,
        block_close=False,
        broken_close=False,
    ):
        self.incoming = asyncio.Queue()
        self.incoming.put_nowait({"type": "websocket.connect"})
        self.outgoing = asyncio.Queue()
        self.accept_started = asyncio.Event()
        self.accepted = asyncio.Event()
        self.send_started = asyncio.Event()
        self.send_cancelled = asyncio.Event()
        self.block_send = block_send
        self.block_accept = block_accept
        self.broken_send = broken_send
        self.block_close = block_close
        self.broken_close = broken_close
        self.socket = WebSocket({"type": "websocket", "path": "/ws"}, self.incoming.get, self.send)

    async def send(self, message):
        if message["type"] == "websocket.close":
            if self.broken_close:
                raise ValueError("SECRET_CLOSE_SENTINEL")
            if self.block_close:
                await asyncio.Event().wait()
        if message["type"] == "websocket.accept":
            self.accept_started.set()
            if self.block_accept:
                await asyncio.Event().wait()
            self.accepted.set()
        if message["type"] == "websocket.send":
            self.send_started.set()
            if self.broken_send:
                raise RuntimeError("SECRET_SEND_SENTINEL")
            if self.block_send:
                try:
                    await asyncio.Event().wait()
                finally:
                    self.send_cancelled.set()
        await self.outgoing.put(message)

    async def close_message(self):
        while True:
            message = await self.outgoing.get()
            if message["type"] == "websocket.close":
                return message


async def test_blocked_send_expires_without_stalling_owner_and_awaits_children(clock):
    harness = SocketHarness(block_send=True)
    connection = Connection(harness.socket, 1, clock, ConnectionSettings())
    supervisor = asyncio.create_task(connection.run())
    await harness.accepted.wait()
    assert connection.offer(error_message(ErrorCode.INVALID_ACTION, "request"))
    await harness.send_started.wait()
    await clock.wait_registered(5)
    await clock.advance(5)
    await supervisor
    assert (await harness.close_message())["code"] == 1013
    assert harness.send_cancelled.is_set()
    assert connection.closed.is_set()
    assert connection.task_count == 0
    assert clock.waiters == []
    assert owned_tasks() == []


async def test_full_queue_closes_instead_of_dropping_critical_replies(clock):
    harness = SocketHarness(block_send=True)
    connection = Connection(harness.socket, 1, clock, ConnectionSettings(queue_capacity=2))
    supervisor = asyncio.create_task(connection.run())
    await harness.accepted.wait()
    assert connection.offer(error_message(ErrorCode.INVALID_ACTION, "in-flight"))
    await harness.send_started.wait()
    assert connection.offer(error_message(ErrorCode.COOLDOWN, "queued-1"))
    assert connection.offer(error_message(ErrorCode.COOLDOWN, "queued-2"))
    assert not connection.offer(error_message(ErrorCode.INTERNAL_ERROR, "overflow"))
    await supervisor
    assert (await harness.close_message())["code"] == 1013
    assert owned_tasks() == []
    assert clock.waiters == []


@pytest.mark.parametrize("block_accept", [False, True])
async def test_manager_shutdown_also_cancels_incomplete_handshake(clock, block_accept):
    harness = SocketHarness(block_accept=block_accept)
    manager = ConnectionManager(clock, ConnectionSettings())
    serving = asyncio.create_task(manager.serve(harness.socket))
    await harness.accept_started.wait()
    assert manager.active_count == 1
    await manager.aclose()
    await serving
    assert (await harness.close_message())["code"] == 1001
    assert manager.active_count == manager.task_count == 0
    assert owned_tasks() == []


async def test_asgi_level_cancellation_shields_cleanup(clock):
    harness = SocketHarness(block_send=True)
    connection = Connection(harness.socket, 1, clock, ConnectionSettings())
    async with anyio.create_task_group() as group:
        group.start_soon(connection.run)
        await harness.accepted.wait()
        connection.offer(error_message(ErrorCode.INVALID_ACTION))
        await harness.send_started.wait()
        group.cancel_scope.cancel()
    assert connection.closed.is_set()
    assert harness.send_cancelled.is_set()
    assert connection.task_count == 0
    assert clock.waiters == []
    assert owned_tasks() == []


async def test_disconnect_cancels_deadline_and_in_flight_send(clock):
    harness = SocketHarness(block_send=True)
    connection = Connection(harness.socket, 1, clock, ConnectionSettings())
    supervisor = asyncio.create_task(connection.run())
    await harness.accepted.wait()
    connection.offer(error_message(ErrorCode.INVALID_ACTION))
    await harness.send_started.wait()
    await harness.incoming.put({"type": "websocket.disconnect", "code": 1000})
    await supervisor
    assert harness.send_cancelled.is_set()
    assert clock.waiters == []
    assert owned_tasks() == []


async def test_writer_failure_is_redacted_and_closes_1011(clock, caplog):
    caplog.set_level(logging.INFO, logger="one_job.connections")
    harness = SocketHarness(broken_send=True)
    connection = Connection(harness.socket, 1, clock, ConnectionSettings())
    supervisor = asyncio.create_task(connection.run())
    await harness.accepted.wait()
    connection.offer(error_message(ErrorCode.INVALID_ACTION))
    await supervisor
    assert (await harness.close_message())["code"] == 1011
    assert "SECRET_SEND_SENTINEL" not in str([r.__dict__ for r in caplog.records])
    assert any(r.message == "writer_failure" for r in caplog.records)
    assert owned_tasks() == []


async def test_stopped_manager_cannot_admit_new_connection(clock):
    harness = SocketHarness()
    manager = ConnectionManager(clock, ConnectionSettings())
    await manager.aclose()
    await manager.serve(harness.socket)
    assert (await harness.close_message())["code"] == 1001
    assert manager.active_count == 0
    assert owned_tasks() == []


@pytest.mark.parametrize("mode", ["block_close", "broken_close"])
async def test_bounded_close_failure_still_releases_connection_and_redacts(clock, caplog, mode):
    caplog.set_level(logging.INFO, logger="one_job.connections")
    harness = SocketHarness(**{mode: True})
    manager = ConnectionManager(clock, ConnectionSettings(close_timeout=0.01))
    serving = asyncio.create_task(manager.serve(harness.socket))
    await harness.accepted.wait()
    await manager.aclose()
    await serving
    assert manager.active_count == manager.task_count == 0
    assert owned_tasks() == []
    assert clock.waiters == []
    assert "SECRET_CLOSE_SENTINEL" not in str([r.__dict__ for r in caplog.records])
    if mode == "broken_close":
        assert any(r.message == "close_failure" for r in caplog.records)


@pytest.mark.parametrize(
    "field,value",
    [
        ("queue_capacity", 0),
        ("queue_capacity", True),
        ("admission_timeout", 0),
        ("send_timeout", -1),
        ("send_timeout", float("inf")),
        ("close_timeout", float("nan")),
    ],
)
def test_invalid_settings(field, value):
    with pytest.raises(ValueError):
        ConnectionSettings(**{field: value})
