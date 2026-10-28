"""One mailbox owns each lobby; all socket offers are nonblocking."""

from __future__ import annotations

import asyncio
import hmac
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast
from uuid import UUID

from one_job.application.sessions import (
    AdmissionReceipt,
    Peer,
    ReplayReply,
    Session,
    command_signature,
    token_digest,
)
from one_job.protocol.envelopes import (
    ClientMessage,
    CreateRoomEnvelope,
    ErrorEnvelope,
    JoinRoomEnvelope,
    LeaveRoomEnvelope,
    PingEnvelope,
    PlayerReadyEnvelope,
    RequestStateEnvelope,
    ResumeSessionEnvelope,
    ServerMessage,
    StartGameEnvelope,
    ack,
    error_message,
    lobby_state,
    pong,
    session_accepted,
)
from one_job.protocol.messages import (
    ErrorCode,
    LobbyPlayer,
    LobbyStage,
    LobbyStatePayload,
    SessionAcceptedPayload,
)

if TYPE_CHECKING:
    from one_job.application.rooms import RoomRegistry


class RoomClosed(Exception):
    pass


@dataclass(slots=True)
class Member:
    player_id: UUID
    name: str
    joined_order: int
    session: Session = field(repr=False)
    ready: bool = False


def start_eligibility(stage: LobbyStage, members: tuple[Member, ...]) -> bool:
    return (
        stage == "lobby"
        and len(members) in (2, 3)
        and all(
            member.session.peer is not None and member.session.peer.active and member.ready
            for member in members
        )
    )


@dataclass(slots=True)
class _Call:
    operation: Callable[[], object] = field(repr=False)
    future: asyncio.Future[object] = field(repr=False)


class RoomService:
    def __init__(self, registry: RoomRegistry, code: str) -> None:
        self.registry = registry
        self.code = code
        self.members: dict[UUID, Member] = {}
        self.host_id: UUID | None = None
        self.stage: LobbyStage = "lobby"
        self.revision = 0
        self.idle_deadline = registry.clock.now() + registry.settings.idle_timeout
        self._joined_order = 0
        self._mailbox: asyncio.Queue[_Call] = asyncio.Queue()
        self._closed = False

    async def submit[T](self, operation: Callable[[], T]) -> T:
        if self._closed:
            raise RoomClosed
        future: asyncio.Future[object] = asyncio.get_running_loop().create_future()
        self._mailbox.put_nowait(_Call(operation, future))
        try:
            return cast(T, await asyncio.shield(future))
        except asyncio.CancelledError:
            future.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            raise

    async def run(self) -> None:
        try:
            while not self._closed:
                deadline = min(
                    [self.idle_deadline]
                    + [
                        member.session.disconnect_deadline
                        for member in self.members.values()
                        if member.session.disconnect_deadline is not None
                    ]
                )
                incoming = asyncio.create_task(
                    self._mailbox.get(), name=f"one_job:room:{self.code}:in"
                )
                timer = asyncio.create_task(
                    self.registry.clock.wait_until(deadline),
                    name=f"one_job:room:{self.code}:expiry",
                )
                try:
                    await asyncio.wait((incoming, timer), return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for task in (incoming, timer):
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(incoming, timer, return_exceptions=True)
                self.expire()
                if incoming.done() and not incoming.cancelled():
                    call = incoming.result()
                    if not call.future.done():
                        try:
                            if self._closed:
                                raise RoomClosed
                            result = call.operation()
                        except Exception as error:
                            call.future.set_exception(error)
                        else:
                            call.future.set_result(result)
        finally:
            self.delete()
            while not self._mailbox.empty():
                call = self._mailbox.get_nowait()
                if not call.future.done():
                    call.future.set_exception(RoomClosed())

    def touch(self) -> None:
        self.idle_deadline = self.registry.clock.now() + self.registry.settings.idle_timeout

    def reset_ready(self) -> None:
        for member in self.members.values():
            member.ready = False

    def choose_host(self) -> None:
        eligible = [
            member
            for member in self.members.values()
            if member.session.peer is not None and member.session.peer.active
        ]
        self.host_id = (
            min(eligible, key=lambda member: (member.joined_order, member.player_id.int)).player_id
            if eligible
            else None
        )

    def view(self) -> LobbyStatePayload:
        return LobbyStatePayload(
            room_code=self.code,
            stage=self.stage,
            host_player_id=str(self.host_id) if self.host_id is not None else None,
            players=tuple(
                LobbyPlayer(
                    player_id=str(member.player_id),
                    name=member.name,
                    connected=member.session.peer is not None,
                    ready=member.ready,
                )
                for member in self.members.values()
            ),
            can_start=start_eligibility(self.stage, tuple(self.members.values())),
        )

    def broadcast(self) -> None:
        message = lobby_state(self.view(), self.revision)
        for member in self.members.values():
            if member.session.peer is not None:
                member.session.peer.offer(message)

    def admission(self, member: Member, message: ClientMessage) -> AdmissionReceipt:
        return AdmissionReceipt(self.code, member.player_id, message.request_id, self.revision)

    def materialize(self, receipt: ReplayReply) -> ServerMessage:
        if isinstance(receipt, AdmissionReceipt):
            return session_accepted(
                receipt.request_id,
                receipt.revision,
                SessionAcceptedPayload(
                    room_code=receipt.room_code,
                    player_id=str(receipt.player_id),
                    resume_token=self.registry.issuer.token(receipt.player_id),
                ),
            )
        return receipt

    def error(self, peer: Peer, message: ClientMessage, code: ErrorCode) -> ErrorCode:
        peer.offer(error_message(code, message.request_id, self.revision))
        return code

    def join(
        self, peer: Peer, message: CreateRoomEnvelope | JoinRoomEnvelope, name: str
    ) -> ErrorCode | None:
        if self.stage != "lobby":
            return self.registry.reject(peer, message, ErrorCode.ROOM_STARTED)
        if len(self.members) >= self.registry.settings.max_players:
            return self.registry.reject(peer, message, ErrorCode.ROOM_FULL)
        player_id = self.registry.new_id()
        if player_id is None:
            if not self.members:
                self.delete()
            return self.registry.reject(peer, message, ErrorCode.CAPACITY)
        if not peer.admit():
            peer.finish(error_message(ErrorCode.NOT_AUTHENTICATED, message.request_id), 1008)
            if not self.members:
                self.delete()
            return ErrorCode.NOT_AUTHENTICATED
        digest = token_digest(self.registry.issuer.token(player_id))
        self._joined_order += 1
        member = Member(player_id, name, self._joined_order, Session(digest, peer, peer.generation))
        self.members[player_id] = member
        self.registry.bind(self, player_id, digest, peer)
        if self.host_id is None:
            self.choose_host()
        self.reset_ready()
        self.revision += 1
        self.touch()
        receipt = self.admission(member, message)
        member.session.remember(message, receipt, self.registry.clock.now())
        peer.offer(self.materialize(receipt))
        self.broadcast()
        return None

    def resume(
        self, player_id: UUID, peer: Peer, message: ResumeSessionEnvelope, digest: bytes
    ) -> ErrorCode | None:
        member = self.members.get(player_id)
        if member is None or not hmac.compare_digest(member.session.digest, digest):
            peer.finish(error_message(ErrorCode.SESSION_EXPIRED, message.request_id), 1008)
            return ErrorCode.SESSION_EXPIRED
        session = member.session
        session.prune(self.registry.clock.now())
        cached = session.replies.get(message.request_id)
        if cached is not None and not hmac.compare_digest(
            cached.signature, command_signature(message)
        ):
            return self.registry.reject(peer, message, ErrorCode.REQUEST_ID_CONFLICT)
        if cached is not None and not isinstance(cached.reply, AdmissionReceipt):
            peer.offer(cached.reply)
            return cached.reply.payload.code if isinstance(cached.reply, ErrorEnvelope) else None
        if not peer.admit():
            peer.finish(error_message(ErrorCode.NOT_AUTHENTICATED, message.request_id), 1008)
            return ErrorCode.NOT_AUTHENTICATED
        old = session.peer
        if old is not None:
            self.registry.unbind(old)
        session.peer, session.generation, session.disconnect_deadline = peer, peer.generation, None
        self.registry.bind(self, player_id, digest, peer)
        if old is not None:
            old.request_close(1008)
        if self.host_id is None:
            self.choose_host()
        self.reset_ready()
        self.revision += 1
        self.touch()
        receipt = cached.reply if cached is not None else self.admission(member, message)
        if cached is None:
            session.remember(message, receipt, self.registry.clock.now())
        peer.offer(self.materialize(receipt))
        self.broadcast()
        return None

    def command(self, player_id: UUID, peer: Peer, message: ClientMessage) -> ErrorCode | None:
        member = self.members.get(player_id)
        if (
            member is None
            or member.session.peer is not peer
            or member.session.generation != peer.generation
        ):
            peer.finish(error_message(ErrorCode.SESSION_EXPIRED, message.request_id), 1008)
            return ErrorCode.SESSION_EXPIRED
        if not peer.active:
            return ErrorCode.SESSION_EXPIRED
        session = member.session
        now = self.registry.clock.now()
        session.prune(now)
        cached = session.replies.get(message.request_id)
        if cached is not None:
            if not hmac.compare_digest(cached.signature, command_signature(message)):
                return self.error(peer, message, ErrorCode.REQUEST_ID_CONFLICT)
            peer.offer(self.materialize(cached.reply))
            return cached.reply.payload.code if isinstance(cached.reply, ErrorEnvelope) else None
        code: ErrorCode | None = None
        changed = False
        if isinstance(message, PingEnvelope):
            reply: ReplayReply = pong(message).model_copy(update={"room_revision": self.revision})
        elif isinstance(message, RequestStateEnvelope):
            self.touch()
            reply = lobby_state(self.view(), self.revision, message.request_id)
        elif isinstance(message, PlayerReadyEnvelope):
            if self.stage != "lobby":
                code = ErrorCode.INVALID_STAGE
                reply = error_message(code, message.request_id, self.revision)
            else:
                changed = member.ready != message.payload.ready
                member.ready = message.payload.ready
                if changed:
                    self.revision += 1
                self.touch()
                reply = ack(message.request_id, self.revision, "player_ready")
        elif isinstance(message, LeaveRoomEnvelope):
            self._remove(member)
            self.reset_ready()
            if self.host_id == player_id:
                self.choose_host()
            self.revision += 1
            self.touch()
            peer.finish(ack(message.request_id, self.revision, "leave_room"), 1000)
            if self.members:
                self.broadcast()
            else:
                self.delete()
            return None
        elif isinstance(message, StartGameEnvelope):
            if self.host_id != player_id:
                code = ErrorCode.NOT_HOST
            elif self.stage != "lobby":
                code = ErrorCode.INVALID_STAGE
            elif not start_eligibility(self.stage, tuple(self.members.values())):
                code = ErrorCode.NOT_READY
            else:
                code = ErrorCode.FEATURE_UNAVAILABLE
            reply = error_message(code, message.request_id, self.revision)
        elif isinstance(message, (CreateRoomEnvelope, JoinRoomEnvelope, ResumeSessionEnvelope)):
            code = ErrorCode.INVALID_STAGE
            reply = error_message(code, message.request_id, self.revision)
        else:
            code = ErrorCode.FEATURE_UNAVAILABLE
            reply = error_message(code, message.request_id, self.revision)
        session.remember(message, reply, now)
        peer.offer(self.materialize(reply))
        if changed:
            self.broadcast()
        return code

    def disconnect(self, player_id: UUID, peer: Peer) -> None:
        member = self.members.get(player_id)
        if (
            member is None
            or member.session.peer is not peer
            or member.session.generation != peer.generation
        ):
            return
        self.registry.unbind(peer)
        member.session.peer = None
        member.session.generation = None
        member.session.disconnect_deadline = (
            self.registry.clock.now() + self.registry.settings.disconnect_grace
        )
        self.reset_ready()
        self.revision += 1
        self.broadcast()

    def _remove(self, member: Member) -> None:
        self.registry.forget_member(member.session.digest, member.player_id, member.session.peer)
        member.session.replies.clear()
        del self.members[member.player_id]

    def expire(self) -> None:
        now = self.registry.clock.now()
        if now >= self.idle_deadline:
            for member in self.members.values():
                if member.session.peer is not None:
                    member.session.peer.finish(
                        error_message(ErrorCode.SESSION_EXPIRED, room_revision=self.revision), 1008
                    )
            self.delete()
            return
        expired = [
            member
            for member in self.members.values()
            if member.session.disconnect_deadline is not None
            and member.session.disconnect_deadline <= now
        ]
        if not expired:
            return
        for member in expired:
            self._remove(member)
        if self.host_id not in self.members:
            self.choose_host()
        self.reset_ready()
        self.revision += 1
        if self.members:
            self.broadcast()
        else:
            self.delete()

    def delete(self) -> None:
        if self._closed:
            return
        self._closed = True
        for member in tuple(self.members.values()):
            self._remove(member)
        self.registry.forget_room(self)

    def shutdown(self) -> None:
        for member in self.members.values():
            if member.session.peer is not None:
                member.session.peer.request_close(1001)
        self.delete()
