"""Synchronous fixed-step scheduling policy, called only by the room owner."""

import math
from dataclasses import dataclass

from one_job.domain.config import TICK_MS
from one_job.domain.emergencies import EmergencyChanged
from one_job.domain.engine import GameEngine
from one_job.domain.types import ResultReason


@dataclass(frozen=True, slots=True)
class Advance:
    steps: int = 0
    publish: bool = False
    terminal: bool = False
    events: tuple[EmergencyChanged, ...] = ()


class RoomRunner:
    def __init__(self, engine: GameEngine) -> None:
        self.engine = engine
        self._origin: float | None = None
        self._origin_tick = 0
        self._origin_countdown_ms = 0
        self._published_tick = 0
        self._catching_up = False

    def reset(self, now: float) -> None:
        self._origin = now
        self._origin_tick = self.engine.snapshot().tick_index
        self._origin_countdown_ms = self.engine.snapshot().round.countdown_remaining_ms or 0
        self._published_tick = 0
        self._catching_up = False

    def suspend(self) -> None:
        self._origin = None
        self._catching_up = False

    @property
    def next_deadline(self) -> float | None:
        if self._origin is None or self.engine.snapshot().round.stage not in (
            "countdown",
            "running",
        ):
            return None
        return self._origin + (self._progress() + 1) * TICK_MS / 1000

    def _progress(self) -> int:
        state = self.engine.snapshot()
        return (
            self._origin_countdown_ms - (state.round.countdown_remaining_ms or 0)
        ) // TICK_MS + (state.tick_index - self._origin_tick)

    def advance(self, now: float) -> Advance:
        if self.next_deadline is None or self._origin is None:
            return Advance()
        before = self.engine.snapshot().round.stage
        due = math.floor((now - self._origin) * 1000 / TICK_MS + 1e-7) - self._progress()
        if due <= 0:
            return Advance()
        if due > 5 and self._catching_up:
            self.engine.abort(ResultReason.SERVER_OVERLOAD)
            self.suspend()
            return Advance(publish=True, terminal=True)
        self._catching_up = due > 5
        events: list[EmergencyChanged] = []
        processed = 0
        for _ in range(min(due, 5)):
            if self.engine.snapshot().round.stage == "countdown":
                self.engine.advance_countdown(TICK_MS)
            else:
                result = self.engine.tick()
                events.extend(
                    event for event in result.events if isinstance(event, EmergencyChanged)
                )
            processed += 1
            if self.engine.snapshot().round.result is not None:
                break
        state = self.engine.snapshot()
        terminal = state.round.result is not None
        publish = (
            terminal or state.round.stage != before or self._progress() - self._published_tick >= 2
        )
        if publish:
            self._published_tick = self._progress()
        if terminal:
            self.suspend()
        return Advance(
            processed,
            publish,
            terminal,
            tuple(events),
        )
