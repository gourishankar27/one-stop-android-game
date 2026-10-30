"""Nonblocking bounded enqueue, coalescing only unsolicited public snapshots."""

import asyncio
from collections import deque
from dataclasses import dataclass

from one_job.protocol.envelopes import (
    LobbyStateEnvelope,
    PublicStateEnvelope,
    RoleStateEnvelope,
    ServerMessage,
)


@dataclass(frozen=True, slots=True)
class Outgoing:
    message: ServerMessage
    delivered: asyncio.Event | None = None


class Outbox:
    def __init__(self, capacity: int = 32) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("outbox capacity must be positive")
        self._capacity = capacity
        self._items: deque[Outgoing] = deque()
        self._ready = asyncio.Event()
        self._closed = False

    @property
    def size(self) -> int:
        return len(self._items)

    def offer(self, message: ServerMessage, delivered: asyncio.Event | None = None) -> bool:
        if self._closed:
            return False
        if (
            isinstance(message, (PublicStateEnvelope, LobbyStateEnvelope, RoleStateEnvelope))
            and message.reply_to is None
            and not (
                isinstance(message, RoleStateEnvelope) and message.payload.public.result is not None
            )
        ):
            for item in tuple(self._items):
                old = item.message
                if (
                    isinstance(old, (PublicStateEnvelope, LobbyStateEnvelope, RoleStateEnvelope))
                    and type(old) is type(message)
                    and old.reply_to is None
                    and self._snapshot_key(old) == self._snapshot_key(message)
                ):
                    if message.room_revision < old.room_revision:
                        return True
                    self._items.remove(item)
                    break
        if len(self._items) >= self._capacity:
            return False
        self._items.append(Outgoing(message, delivered))
        self._ready.set()
        return True

    @staticmethod
    def _snapshot_key(message: PublicStateEnvelope | LobbyStateEnvelope | RoleStateEnvelope) -> str:
        if isinstance(message, (PublicStateEnvelope, RoleStateEnvelope)):
            return message.payload.public.round_id
        return message.payload.room_code

    async def get(self) -> Outgoing:
        while not self._items:
            if self._closed:
                raise EOFError("outbox closed")
            self._ready.clear()
            await self._ready.wait()
        return self._items.popleft()

    def close(self) -> None:
        self._closed = True
        self._items.clear()
        self._ready.set()
