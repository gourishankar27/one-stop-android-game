"""Lifespan-owned connection supervision; no membership or room behavior."""

import asyncio
import logging
import math
from dataclasses import dataclass

from anyio import CancelScope
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from one_job.application.limits import MessageBudget
from one_job.application.outbox import Outbox
from one_job.application.timing import Clock, with_deadline
from one_job.protocol.envelopes import (
    MAX_FRAME_BYTES,
    FrameError,
    PingEnvelope,
    ServerMessage,
    encode_message,
    error_message,
    parse_text,
    pong,
)
from one_job.protocol.messages import ErrorCode

LOGGER = logging.getLogger("one_job.connections")


@dataclass(frozen=True, slots=True)
class ConnectionSettings:
    queue_capacity: int = 32
    admission_timeout: float = 10.0
    send_timeout: float = 5.0
    close_timeout: float = 1.0

    def __post_init__(self) -> None:
        if type(self.queue_capacity) is not int or self.queue_capacity < 1:
            raise ValueError("queue capacity must be positive")
        for value in (self.admission_timeout, self.send_timeout, self.close_timeout):
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError("connection timeouts must be positive and finite")


class Connection:
    def __init__(
        self, socket: WebSocket, generation: int, clock: Clock, settings: ConnectionSettings
    ) -> None:
        self.socket = socket
        self.generation = generation
        self.clock = clock
        self.settings = settings
        self.outbox = Outbox(settings.queue_capacity)
        self.closed = asyncio.Event()
        self._closing = asyncio.Event()
        self._close_code: int | None = None
        self._tasks: set[asyncio.Task[None]] = set()
        self._budget = MessageBudget(clock.now())

    @property
    def task_count(self) -> int:
        return sum(not task.done() for task in self._tasks)

    def request_close(self, code: int | None) -> None:
        if not self._closing.is_set():
            self._close_code = code
            self._closing.set()

    def offer(self, message: ServerMessage, delivered: asyncio.Event | None = None) -> bool:
        if self._closing.is_set():
            return False
        if not self.outbox.offer(message, delivered):
            self.request_close(1013)
            return False
        return True

    async def _failure(self, failure: FrameError) -> None:
        receipt = asyncio.Event() if failure.close_code is not None else None
        queued = self.offer(error_message(failure.code, failure.reply_to), receipt)
        if queued and receipt is not None:
            await receipt.wait()
        if failure.close_code is not None:
            self.request_close(failure.close_code)

    def _log(
        self,
        event: str,
        start: float,
        request_id: str | None = None,
        operation: str | None = None,
        code: ErrorCode | None = None,
    ) -> None:
        LOGGER.info(
            event,
            extra={
                "generation": self.generation,
                "request_id": request_id,
                "operation": operation,
                "error_code": code.value if code else None,
                "close_code": self._close_code,
                "duration_ms": max(0, int((self.clock.now() - start) * 1000)),
            },
        )

    async def _reader(self) -> None:
        try:
            await self.socket.accept()
            self._log("connection_opened", self.clock.now())
            while not self._closing.is_set():
                frame = await self.socket.receive()
                if frame["type"] == "websocket.disconnect":
                    self.request_close(None)
                    return
                start = self.clock.now()
                request_id: str | None = None
                operation: str | None = None
                failure: FrameError | None = None
                try:
                    if frame.get("bytes") is not None:
                        close = 1009 if len(frame["bytes"]) > MAX_FRAME_BYTES else 1007
                        raise FrameError(ErrorCode.INVALID_MESSAGE, close_code=close)
                    message = parse_text(frame.get("text") or "")
                    request_id, operation = message.request_id, message.type
                except FrameError as error:
                    failure = error
                    request_id, operation = error.reply_to, error.operation
                if failure is None or failure.close_code is None:
                    allowed, sustained = self._budget.take(self.clock.now(), operation == "ping")
                    if not allowed:
                        failure = FrameError(
                            ErrorCode.RATE_LIMITED,
                            request_id,
                            1008 if sustained else None,
                            operation,
                        )
                if failure is not None:
                    await self._failure(failure)
                elif isinstance(message, PingEnvelope):
                    self.offer(pong(message))
                else:
                    failure = FrameError(
                        ErrorCode.FEATURE_UNAVAILABLE, request_id, operation=operation
                    )
                    await self._failure(failure)
                self._log(
                    "command_completed",
                    start,
                    request_id,
                    operation,
                    failure.code if failure else None,
                )
        except WebSocketDisconnect:
            self.request_close(None)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._log("connection_failure", self.clock.now(), code=ErrorCode.INTERNAL_ERROR)
            await self._failure(FrameError(ErrorCode.INTERNAL_ERROR, close_code=1011))

    async def _writer(self) -> None:
        try:
            while True:
                item = await self.outbox.get()
                await with_deadline(
                    self.socket.send_text(encode_message(item.message)),
                    self.clock,
                    self.settings.send_timeout,
                    f"{self.generation}:send",
                )
                if item.delivered is not None:
                    item.delivered.set()
        except TimeoutError:
            self.request_close(1013)
        except (WebSocketDisconnect, EOFError):
            self.request_close(None)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._log("writer_failure", self.clock.now(), code=ErrorCode.INTERNAL_ERROR)
            self.request_close(1011)

    async def _admission_deadline(self, deadline: float) -> None:
        await self.clock.wait_until(deadline)
        await self._failure(FrameError(ErrorCode.NOT_AUTHENTICATED, close_code=1008))

    async def _wait_close(self) -> None:
        await self._closing.wait()

    async def run(self) -> None:
        start = self.clock.now()
        try:
            self._tasks = {
                asyncio.create_task(self._reader(), name=f"one_job:{self.generation}:reader"),
                asyncio.create_task(self._writer(), name=f"one_job:{self.generation}:writer"),
                asyncio.create_task(
                    self._admission_deadline(start + self.settings.admission_timeout),
                    name=f"one_job:{self.generation}:admission",
                ),
                asyncio.create_task(self._wait_close(), name=f"one_job:{self.generation}:close"),
            }
            done, _ = await asyncio.wait(self._tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except asyncio.CancelledError:
            self.request_close(1001)
            raise
        except Exception:
            self._log("connection_failure", start, code=ErrorCode.INTERNAL_ERROR)
            self.request_close(1011)
        finally:
            with CancelScope(shield=True):
                await self._cleanup(start)

    async def _cleanup(self, start: float) -> None:
        for task in self._tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self.outbox.close()
        if self._close_code is not None and self.socket.client_state != WebSocketState.DISCONNECTED:
            try:
                await asyncio.wait_for(
                    self.socket.close(code=self._close_code), self.settings.close_timeout
                )
            except (TimeoutError, RuntimeError, WebSocketDisconnect):
                pass
            except Exception:
                self._log("close_failure", start, code=ErrorCode.INTERNAL_ERROR)
        self._log("connection_closed", start)
        self.closed.set()


class ConnectionManager:
    def __init__(self, clock: Clock, settings: ConnectionSettings) -> None:
        self.clock = clock
        self.settings = settings
        self._connections: set[Connection] = set()
        self._generation = 0
        self._stopping = False

    @property
    def active_count(self) -> int:
        return len(self._connections)

    @property
    def task_count(self) -> int:
        return sum(connection.task_count for connection in self._connections)

    async def serve(self, socket: WebSocket) -> None:
        if self._stopping:
            await socket.close(code=1001)
            return
        self._generation += 1
        connection = Connection(socket, self._generation, self.clock, self.settings)
        self._connections.add(connection)
        try:
            await connection.run()
        finally:
            self._connections.discard(connection)

    async def aclose(self) -> None:
        self._stopping = True
        connections = tuple(self._connections)
        for connection in connections:
            connection.request_close(1001)
        await asyncio.gather(*(connection.closed.wait() for connection in connections))
