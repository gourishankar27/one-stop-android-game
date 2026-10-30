"""One mailbox owns each lobby; all socket offers are nonblocking."""

from __future__ import annotations

import asyncio
import hmac
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast
from uuid import UUID

from one_job.application.round_service import RoundService
from one_job.application.sessions import (
    AdmissionReceipt,
    Peer,
    ReplayReply,
    Session,
    command_signature,
    token_digest,
)
from one_job.domain.models import Player
from one_job.domain.types import PlayerId, ResultReason, RoundId
from one_job.protocol.envelopes import (
    AckEnvelope,
    ActionRejectedEnvelope,
    BriefingReadyEnvelope,
    ClientMessage,
    CreateRoomEnvelope,
    EmergencyEventEnvelope,
    ErrorEnvelope,
    GameOverEnvelope,
    JoinDisplayEnvelope,
    JoinRoomEnvelope,
    LeaveRoomEnvelope,
    PingEnvelope,
    PlayAgainEnvelope,
    PlayerActionEnvelope,
    PlayerReadyEnvelope,
    PublicStateEnvelope,
    RequestStateEnvelope,
    ResumeSessionEnvelope,
    ReturnToLobbyEnvelope,
    RoleAssignedEnvelope,
    RoleStateEnvelope,
    ServerMessage,
    StartGameEnvelope,
    ack,
    error_message,
    lobby_state,
    pong,
    session_accepted,
)
from one_job.protocol.mapping import public_view
from one_job.protocol.messages import (
    ERROR_MESSAGES,
    ActionAckPayload,
    ErrorCode,
    LobbyPlayer,
    LobbyStage,
    LobbyStatePayload,
    PublicStatePayload,
    SessionAcceptedPayload,
)
from one_job.protocol.role_messages import (
    ActionRejectedPayload,
    EmergencyEventPayload,
    GameOverPayload,
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


@dataclass(slots=True)
class Display:
    display_id: UUID
    session: Session = field(repr=False)


def start_eligibility(stage: LobbyStage, members: tuple[Member, ...]) -> bool:
    return (
        stage in ("lobby", "finished", "aborted")
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
        self.displays: dict[UUID, Display] = {}
        self.host_id: UUID | None = None
        self.stage: LobbyStage = "lobby"
        self.round: RoundService | None = None
        self._last_round: tuple[RoundId, int] | None = None
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
                    + (
                        [self.round.deadline]
                        if self.round is not None and self.round.deadline is not None
                        else []
                    )
                    + (
                        [self.round.runner.next_deadline]
                        if self.round is not None and self.round.runner.next_deadline is not None
                        else []
                    )
                    + [
                        member.session.disconnect_deadline
                        for member in self.members.values()
                        if member.session.disconnect_deadline is not None
                    ]
                    + [
                        display.session.disconnect_deadline
                        for display in self.displays.values()
                        if display.session.disconnect_deadline is not None
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
                if not self._closed:
                    self.advance()
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

    def broadcast(self, assignments: bool = False, include_lobby: bool = True) -> None:
        message = lobby_state(self.view(), self.revision)
        for member in self.members.values():
            if member.session.peer is not None:
                if include_lobby:
                    member.session.peer.offer(message)
                if self.round is not None:
                    if assignments:
                        member.session.peer.offer(self.assignment(member.player_id))
                    member.session.peer.offer(self.role_state(member.player_id))
        for display in self.displays.values():
            if display.session.peer is not None:
                if include_lobby:
                    display.session.peer.offer(message)
                display.session.peer.offer(self.public_state())
        if self.round is not None and self.round.terminal and not self.round.result_announced:
            result = public_view(self.round.engine.snapshot()).result
            assert result is not None
            self.round.result_announced = True
            event = GameOverEnvelope(
                room_revision=self.revision,
                payload=GameOverPayload(round_id=str(self.round.round_id), result=result),
            )
            for member in self.members.values():
                if member.session.peer is not None:
                    member.session.peer.offer(event)

    def new_round(self, now: float) -> bool:
        """Build the replacement before discarding the prior terminal context."""
        previous = self.round
        for _ in range(8):
            seed = self.registry.seed_factory()
            identity = RoundId(self.registry.round_id_factory())
            if self._last_round is None or (
                identity != self._last_round[0] and seed != self._last_round[1]
            ):
                replacement = RoundService(
                    self.registry.game_config,
                    seed,
                    tuple(
                        Player(PlayerId(item.player_id), item.name)
                        for item in self.members.values()
                    ),
                    identity,
                    now,
                    self.registry.settings.briefing_timeout,
                )
                if previous is not None:
                    previous.runner.suspend()
                self._discard_round_views()
                self.round = replacement
                self._last_round = (identity, seed)
                self.stage = replacement.stage
                self.reset_ready()
                return True
        return False

    def _discard_round_views(self) -> None:
        for session in self.all_sessions():
            for request_id, cached in tuple(session.replies.items()):
                if isinstance(cached.reply, (RoleStateEnvelope, PublicStateEnvelope)):
                    del session.replies[request_id]

    def all_sessions(self) -> tuple[Session, ...]:
        return tuple(m.session for m in self.members.values()) + tuple(
            d.session for d in self.displays.values()
        )

    def advance(self) -> None:
        if self.round is None:
            return
        advance = self.round.runner.advance(self.registry.clock.now())
        if advance.steps or advance.terminal:
            self.stage = self.round.stage
            self.revision += max(1, advance.steps)
            for event in advance.events:
                message = EmergencyEventEnvelope(
                    room_revision=self.revision,
                    payload=EmergencyEventPayload.model_validate(
                        {
                            "round_id": str(self.round.round_id),
                            "emergency_id": event.emergency_id,
                            "kind": event.kind.value,
                            "status": event.status,
                        }
                    ),
                )
                for member in self.members.values():
                    if member.session.peer is not None:
                        member.session.peer.offer(message)
            if advance.publish:
                self.broadcast(include_lobby=advance.terminal)

    def assignment(self, player_id: UUID) -> RoleAssignedEnvelope:
        assert self.round is not None
        return RoleAssignedEnvelope(
            reply_to=None,
            room_revision=self.revision,
            payload=self.round.assigned(PlayerId(player_id)),
        )

    def role_state(self, player_id: UUID, reply_to: str | None = None) -> RoleStateEnvelope:
        assert self.round is not None
        return RoleStateEnvelope(
            reply_to=reply_to,
            room_revision=self.revision,
            payload=self.round.view(PlayerId(player_id), self.registry.clock.now()),
        )

    def public_state(self, reply_to: str | None = None) -> PublicStateEnvelope:
        return PublicStateEnvelope(
            reply_to=reply_to,
            room_revision=self.revision,
            payload=PublicStatePayload(
                public=(
                    public_view(self.round.engine.snapshot()) if self.round is not None else None
                )
            ),
        )

    def admission(self, member: Member, message: ClientMessage) -> AdmissionReceipt:
        return AdmissionReceipt(self.code, member.player_id, message.request_id, self.revision)

    def materialize(self, receipt: ReplayReply) -> ServerMessage:
        if isinstance(receipt, AdmissionReceipt):
            return session_accepted(
                receipt.request_id,
                receipt.revision,
                SessionAcceptedPayload(
                    room_code=receipt.room_code,
                    player_id=str(receipt.player_id) if receipt.kind == "player" else None,
                    kind=receipt.kind,
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
        if player_id in self.displays:
            return self.resume_display(player_id, peer, message, digest)
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
            return (
                cached.reply.payload.code
                if isinstance(cached.reply, (ErrorEnvelope, ActionRejectedEnvelope))
                else None
            )
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
        if self.round is not None:
            if not self.round.terminal and self.all_participants_connected():
                self.round.resume(self.registry.clock.now())
            self.stage = self.round.stage
            peer.offer(self.assignment(player_id))
        self.broadcast()
        return None

    def all_participants_connected(self) -> bool:
        assert self.round is not None
        for participant in self.round.engine.snapshot().players:
            member = self.members.get(participant.player_id)
            peer = member.session.peer if member is not None else None
            if peer is None or not peer.active:
                return False
        return True

    def command(self, player_id: UUID, peer: Peer, message: ClientMessage) -> ErrorCode | None:
        if player_id in self.displays:
            return self.display_command(player_id, peer, message)
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
            return (
                cached.reply.payload.code
                if isinstance(cached.reply, (ErrorEnvelope, ActionRejectedEnvelope))
                else None
            )
        code: ErrorCode | None = None
        changed = False
        if isinstance(message, PingEnvelope):
            reply: ReplayReply = pong(message).model_copy(update={"room_revision": self.revision})
        elif isinstance(message, RequestStateEnvelope):
            self.touch()
            if self.round is None:
                reply = lobby_state(self.view(), self.revision, message.request_id)
            else:
                peer.offer(lobby_state(self.view(), self.revision))
                peer.offer(self.assignment(player_id))
                reply = self.role_state(player_id, message.request_id)
        elif isinstance(message, PlayerReadyEnvelope):
            if self.stage not in ("lobby", "finished", "aborted"):
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
            if self.round is not None and not self.round.terminal:
                self.round.abort(ResultReason.PLAYER_LEFT)
                self.stage = self.round.stage
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
        elif isinstance(message, (StartGameEnvelope, PlayAgainEnvelope)):
            allowed = (
                ("lobby",) if isinstance(message, StartGameEnvelope) else ("finished", "aborted")
            )
            if self.host_id != player_id:
                code = ErrorCode.NOT_HOST
            elif self.stage not in allowed:
                code = ErrorCode.INVALID_STAGE
            elif not start_eligibility(self.stage, tuple(self.members.values())):
                code = ErrorCode.NOT_READY
            else:
                if self.new_round(now):
                    self.revision += 1
                    self.touch()
                    reply = ack(message.request_id, self.revision, message.type)
                    session.remember(message, reply, now)
                    peer.offer(reply)
                    self.broadcast(assignments=True)
                    return None
                code = ErrorCode.INTERNAL_ERROR
            reply = error_message(code, message.request_id, self.revision)
        elif isinstance(message, ReturnToLobbyEnvelope):
            if self.host_id != player_id:
                code = ErrorCode.NOT_HOST
            elif self.stage not in ("finished", "aborted"):
                code = ErrorCode.INVALID_STAGE
            if code is None:
                assert self.round is not None
                self.round.runner.suspend()
                self._discard_round_views()
                self.round = None
                self.stage = "lobby"
                self.reset_ready()
                self.revision += 1
                self.touch()
                changed = True
                reply = ack(message.request_id, self.revision, "return_to_lobby")
            else:
                reply = error_message(code, message.request_id, self.revision)
        elif isinstance(message, BriefingReadyEnvelope):
            if self.round is None:
                code = ErrorCode.INVALID_STAGE
            else:
                was_terminal = self.round.terminal
                code, changed = self.round.acknowledge(
                    PlayerId(player_id), message.payload.round_id, now
                )
                self.stage = self.round.stage
                if not was_terminal and self.round.terminal:
                    # Expiry may be crossed after the owner's earlier deadline check.
                    self.revision += 1
                    self.broadcast()
            if code is None:
                if changed:
                    self.revision += 1
                self.touch()
                reply = ack(message.request_id, self.revision, "briefing_ready")
            else:
                reply = error_message(code, message.request_id, self.revision)
        elif isinstance(message, PlayerActionEnvelope):
            event = None
            if self.round is None:
                code = ErrorCode.INVALID_STAGE
            else:
                code, event = self.round.submit_action(
                    PlayerId(player_id),
                    message.payload.round_id,
                    message.payload.client_action_seq,
                    message.payload.action,
                )
            if code is None:
                assert event is not None
                self.revision += 1
                reply = AckEnvelope(
                    reply_to=message.request_id,
                    room_revision=self.revision,
                    payload=ActionAckPayload(
                        client_action_seq=message.payload.client_action_seq,
                        applied_tick=event.tick_index,
                    ),
                )
            else:
                reply = ActionRejectedEnvelope(
                    reply_to=message.request_id,
                    room_revision=self.revision,
                    payload=ActionRejectedPayload(
                        code=code,
                        message=ERROR_MESSAGES[code],
                        client_action_seq=message.payload.client_action_seq,
                        round_id=message.payload.round_id,
                    ),
                )
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
        display = self.displays.get(player_id)
        if display is not None:
            if display.session.peer is peer and display.session.generation == peer.generation:
                self.registry.unbind(peer)
                display.session.peer = None
                display.session.generation = None
                display.session.disconnect_deadline = (
                    self.registry.clock.now() + self.registry.settings.disconnect_grace
                )
            return
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
        if self.round is not None:
            self.round.pause(self.registry.clock.now())
            self.stage = self.round.stage
        self.revision += 1
        self.broadcast()

    def _remove(self, member: Member) -> None:
        self.registry.forget_member(member.session.digest, member.player_id, member.session.peer)
        member.session.replies.clear()
        del self.members[member.player_id]

    def expire(self) -> None:
        now = self.registry.clock.now()
        for display in tuple(self.displays.values()):
            deadline = display.session.disconnect_deadline
            if deadline is not None and deadline <= now:
                self._remove_display(display)
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
        round_expired = self.round.expire(now) if self.round is not None else False
        if not expired:
            if round_expired:
                assert self.round is not None
                self.stage = self.round.stage
                self.revision += 1
                self.broadcast()
            return
        if self.round is not None and not self.round.terminal:
            self.round.abort(ResultReason.DISCONNECT_TIMEOUT)
            self.stage = self.round.stage
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

    def delete(self, close_displays: bool = True) -> None:
        if self._closed:
            return
        self._closed = True
        for display in tuple(self.displays.values()):
            if close_displays and display.session.peer is not None:
                display.session.peer.finish(
                    error_message(ErrorCode.SESSION_EXPIRED, room_revision=self.revision), 1008
                )
            self._remove_display(display)
        for member in tuple(self.members.values()):
            self._remove(member)
        self.registry.forget_room(self)

    def shutdown(self) -> None:
        for session in self.all_sessions():
            if session.peer is not None:
                session.peer.request_close(1001)
        self.delete(close_displays=False)

    def join_display(self, peer: Peer, message: JoinDisplayEnvelope) -> ErrorCode | None:
        if len(self.displays) >= 2:
            return self.registry.reject(peer, message, ErrorCode.DISPLAY_FULL)
        identity = self.registry.new_id()
        if identity is None:
            return self.registry.reject(peer, message, ErrorCode.CAPACITY)
        if not peer.admit():
            peer.finish(error_message(ErrorCode.NOT_AUTHENTICATED, message.request_id), 1008)
            return ErrorCode.NOT_AUTHENTICATED
        digest = token_digest(self.registry.issuer.token(identity))
        display = Display(identity, Session(digest, peer, peer.generation))
        self.displays[identity] = display
        self.registry.bind(self, identity, digest, peer)
        receipt = AdmissionReceipt(
            self.code, identity, message.request_id, self.revision, "display"
        )
        display.session.remember(message, receipt, self.registry.clock.now())
        peer.offer(self.materialize(receipt))
        self.display_snapshots(peer)
        return None

    def display_snapshots(self, peer: Peer) -> None:
        peer.offer(lobby_state(self.view(), self.revision))
        peer.offer(self.public_state())

    def resume_display(
        self, identity: UUID, peer: Peer, message: ResumeSessionEnvelope, digest: bytes
    ) -> ErrorCode | None:
        display = self.displays[identity]
        session = display.session
        if not hmac.compare_digest(session.digest, digest):
            peer.finish(error_message(ErrorCode.SESSION_EXPIRED, message.request_id), 1008)
            return ErrorCode.SESSION_EXPIRED
        now = self.registry.clock.now()
        session.prune(now)
        cached = session.replies.get(message.request_id)
        if cached is not None and not hmac.compare_digest(
            cached.signature, command_signature(message)
        ):
            return self.error(peer, message, ErrorCode.REQUEST_ID_CONFLICT)
        if cached is not None and not isinstance(cached.reply, AdmissionReceipt):
            peer.offer(self.materialize(cached.reply))
            return cached.reply.payload.code if isinstance(cached.reply, ErrorEnvelope) else None
        if not peer.admit():
            peer.finish(error_message(ErrorCode.NOT_AUTHENTICATED, message.request_id), 1008)
            return ErrorCode.NOT_AUTHENTICATED
        old = session.peer
        if old is not None:
            self.registry.unbind(old)
        session.peer, session.generation, session.disconnect_deadline = peer, peer.generation, None
        self.registry.bind(self, identity, digest, peer)
        if old is not None and old is not peer:
            old.request_close(1008)
        receipt = (
            cached.reply
            if cached is not None
            else AdmissionReceipt(self.code, identity, message.request_id, self.revision, "display")
        )
        if cached is None:
            session.remember(message, receipt, now)
        peer.offer(self.materialize(receipt))
        self.display_snapshots(peer)
        return None

    def display_command(
        self, identity: UUID, peer: Peer, message: ClientMessage
    ) -> ErrorCode | None:
        display = self.displays[identity]
        session = display.session
        if session.peer is not peer or session.generation != peer.generation:
            peer.finish(error_message(ErrorCode.SESSION_EXPIRED, message.request_id), 1008)
            return ErrorCode.SESSION_EXPIRED
        if not peer.active:
            return ErrorCode.SESSION_EXPIRED
        if isinstance(message, ResumeSessionEnvelope):
            return self.resume_display(
                identity, peer, message, token_digest(message.payload.resume_token)
            )
        now = self.registry.clock.now()
        session.prune(now)
        cached = session.replies.get(message.request_id)
        if cached is not None:
            if not hmac.compare_digest(cached.signature, command_signature(message)):
                return self.error(peer, message, ErrorCode.REQUEST_ID_CONFLICT)
            peer.offer(self.materialize(cached.reply))
            return cached.reply.payload.code if isinstance(cached.reply, ErrorEnvelope) else None
        code = None
        if isinstance(message, PingEnvelope):
            reply: ReplayReply = pong(message).model_copy(update={"room_revision": self.revision})
        elif isinstance(message, RequestStateEnvelope):
            peer.offer(lobby_state(self.view(), self.revision))
            reply = self.public_state(message.request_id)
        elif isinstance(message, LeaveRoomEnvelope):
            self._remove_display(display)
            peer.finish(ack(message.request_id, self.revision, "leave_room"), 1000)
            return None
        else:
            code = ErrorCode.NOT_CONTROLLER
            reply = error_message(code, message.request_id, self.revision)
        session.remember(message, reply, now)
        peer.offer(self.materialize(reply))
        return code

    def _remove_display(self, display: Display) -> None:
        self.registry.forget_member(
            display.session.digest, display.display_id, display.session.peer
        )
        display.session.replies.clear()
        del self.displays[display.display_id]
