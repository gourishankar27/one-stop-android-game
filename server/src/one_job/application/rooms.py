"""Single-process discovery/indexes; admissions are serialized across room owners."""

import asyncio
import math
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from one_job.application.room_service import RoomClosed, RoomService
from one_job.application.sessions import Peer, TokenIssuer, token_digest
from one_job.application.timing import Clock
from one_job.protocol.envelopes import (
    ClientMessage,
    CreateRoomEnvelope,
    JoinRoomEnvelope,
    PingEnvelope,
    ReservedEnvelope,
    ResumeSessionEnvelope,
    error_message,
    pong,
)
from one_job.protocol.messages import ROOM_CODE_ALPHABET, ErrorCode


@dataclass(frozen=True, slots=True)
class RoomSettings:
    max_rooms: int = 100
    max_players: int = 3
    disconnect_grace: float = 30.0
    idle_timeout: float = 1800.0

    def __post_init__(self) -> None:
        if type(self.max_rooms) is not int or self.max_rooms < 1:
            raise ValueError("room capacity must be positive")
        if type(self.max_players) is not int or self.max_players not in (2, 3):
            raise ValueError("player capacity must be two or three")
        for value in (self.disconnect_grace, self.idle_timeout):
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError("room deadlines must be positive and finite")


def secure_room_code() -> str:
    return "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(6))


class RoomRegistry:
    def __init__(
        self,
        clock: Clock,
        settings: RoomSettings | None = None,
        *,
        code_factory: Callable[[], str] = secure_room_code,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self.clock = clock
        self.settings = settings or RoomSettings()
        self.issuer = TokenIssuer()
        self._code_factory = code_factory
        self._id_factory = id_factory
        self._rooms: dict[str, RoomService] = {}
        self._sessions: dict[bytes, tuple[RoomService, UUID]] = {}
        self._bindings: dict[int, tuple[RoomService, UUID]] = {}
        self._ids: set[UUID] = set()
        self._admission_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[None]] = set()
        self._stopping = False

    @property
    def room_count(self) -> int:
        return len(self._rooms)

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def task_count(self) -> int:
        return sum(not task.done() for task in self._tasks)

    def new_id(self) -> UUID | None:
        for _ in range(10):
            candidate = self._id_factory()
            if candidate not in self._ids:
                return candidate
        return None

    def bind(self, room: RoomService, player_id: UUID, digest: bytes, peer: Peer) -> None:
        self._sessions[digest] = (room, player_id)
        self._ids.add(player_id)
        self._bindings[peer.generation] = (room, player_id)

    def unbind(self, peer: Peer) -> None:
        self._bindings.pop(peer.generation, None)

    def forget_member(self, digest: bytes, player_id: UUID, peer: Peer | None) -> None:
        self._sessions.pop(digest, None)
        self._ids.discard(player_id)
        if peer is not None:
            self.unbind(peer)

    def forget_room(self, room: RoomService) -> None:
        if self._rooms.get(room.code) is room:
            del self._rooms[room.code]

    @staticmethod
    def reject(
        peer: Peer, message: ClientMessage, code: ErrorCode, fatal: bool = False
    ) -> ErrorCode:
        reply = error_message(code, message.request_id)
        if fatal:
            peer.finish(reply, 1008)
        else:
            peer.offer(reply)
        return code

    async def dispatch(self, peer: Peer, message: ClientMessage) -> ErrorCode | None:
        if not peer.active or self._stopping:
            return ErrorCode.SESSION_EXPIRED
        binding = self._bindings.get(peer.generation)
        if binding is not None:
            room, player_id = binding
            try:
                return await room.submit(lambda: room.command(player_id, peer, message))
            except RoomClosed:
                return self.reject(peer, message, ErrorCode.SESSION_EXPIRED, True)
        if isinstance(message, PingEnvelope):
            peer.offer(pong(message))
            return None
        if isinstance(message, ReservedEnvelope):
            return self.reject(peer, message, ErrorCode.FEATURE_UNAVAILABLE)
        if not isinstance(message, (CreateRoomEnvelope, JoinRoomEnvelope, ResumeSessionEnvelope)):
            return self.reject(peer, message, ErrorCode.NOT_AUTHENTICATED)
        async with self._admission_lock:
            if not peer.active or self._stopping:
                return ErrorCode.SESSION_EXPIRED
            # Recheck expiry at the boundary, even before the timer task is scheduled.
            await self.synchronize()
            if isinstance(message, CreateRoomEnvelope):
                if self.room_count >= self.settings.max_rooms:
                    return self.reject(peer, message, ErrorCode.CAPACITY)
                code = None
                for _ in range(10):
                    candidate = self._code_factory()
                    if candidate not in self._rooms:
                        code = candidate
                        break
                if code is None:
                    return self.reject(peer, message, ErrorCode.CAPACITY)
                room = RoomService(self, code)
                self._rooms[code] = room
                task = asyncio.create_task(room.run(), name=f"one_job:room:{code}:owner")
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
                result = await room.submit(lambda: room.join(peer, message, message.payload.name))
                return result
            if isinstance(message, JoinRoomEnvelope):
                joined_room = self._rooms.get(message.payload.room_code)
                if joined_room is None:
                    return self.reject(peer, message, ErrorCode.ROOM_NOT_FOUND)
                try:
                    return await joined_room.submit(
                        lambda: joined_room.join(peer, message, message.payload.name)
                    )
                except RoomClosed:
                    return self.reject(peer, message, ErrorCode.ROOM_NOT_FOUND)
            digest = token_digest(message.payload.resume_token)
            found = self._sessions.get(digest)
            if found is None:
                return self.reject(peer, message, ErrorCode.SESSION_EXPIRED, True)
            room, player_id = found
            try:
                return await room.submit(lambda: room.resume(player_id, peer, message, digest))
            except RoomClosed:
                return self.reject(peer, message, ErrorCode.SESSION_EXPIRED, True)

    async def disconnect(self, peer: Peer) -> None:
        binding = self._bindings.get(peer.generation)
        if binding is not None:
            room, player_id = binding
            try:
                await room.submit(lambda: room.disconnect(player_id, peer))
            except RoomClosed:
                pass

    async def synchronize(self) -> None:
        for room in tuple(self._rooms.values()):
            try:
                await room.submit(lambda: None)
            except RoomClosed:
                pass

    async def aclose(self) -> None:
        self._stopping = True
        async with self._admission_lock:
            for room in tuple(self._rooms.values()):
                try:
                    await room.submit(room.shutdown)
                except RoomClosed:
                    pass
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
            self._rooms.clear()
            self._sessions.clear()
            self._bindings.clear()
            self._ids.clear()
