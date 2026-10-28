"""Private connection bindings and bounded replay records, outside the domain."""

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from one_job.protocol.envelopes import (
    AckEnvelope,
    ClientMessage,
    ErrorEnvelope,
    LobbyStateEnvelope,
    PongEnvelope,
    ServerMessage,
)


class Peer(Protocol):
    generation: int

    @property
    def active(self) -> bool: ...
    def admit(self) -> bool: ...
    def offer(self, message: ServerMessage, delivered: asyncio.Event | None = None) -> bool: ...
    def finish(self, message: ServerMessage, code: int) -> None: ...
    def request_close(self, code: int | None) -> None: ...


class TokenIssuer:
    """A lifespan secret reconstructs credentials only for targeted transmission."""

    def __init__(self) -> None:
        self._key = secrets.token_bytes(32)

    def token(self, player_id: UUID) -> str:
        value = hmac.digest(self._key, b"one-job/session/v1/" + player_id.bytes, "sha256")
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def command_signature(message: ClientMessage) -> bytes:
    canonical = json.dumps(message.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).digest()


@dataclass(frozen=True, slots=True)
class AdmissionReceipt:
    room_code: str
    player_id: UUID
    request_id: str
    revision: int


type ReplayReply = (
    AckEnvelope | ErrorEnvelope | LobbyStateEnvelope | PongEnvelope | AdmissionReceipt
)


@dataclass(frozen=True, slots=True)
class CachedReply:
    signature: bytes = field(repr=False)
    expires_at: float
    reply: ReplayReply


@dataclass(slots=True)
class Session:
    digest: bytes = field(repr=False)
    peer: Peer | None = field(default=None, repr=False)
    generation: int | None = None
    disconnect_deadline: float | None = None
    replies: OrderedDict[str, CachedReply] = field(default_factory=OrderedDict, repr=False)

    def prune(self, now: float) -> None:
        for request_id in tuple(self.replies):
            if self.replies[request_id].expires_at <= now:
                del self.replies[request_id]

    def remember(self, message: ClientMessage, reply: ReplayReply, now: float) -> None:
        self.prune(now)
        self.replies[message.request_id] = CachedReply(command_signature(message), now + 30, reply)
        while len(self.replies) > 128:
            self.replies.popitem(last=False)
