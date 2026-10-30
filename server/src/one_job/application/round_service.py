"""Synchronous briefing context, mutated only by its existing room mailbox."""

import math
from collections.abc import Sequence
from random import Random

from one_job.application.projections import assigned_view, player_view
from one_job.application.room_runner import RoomRunner
from one_job.domain.config import GameConfig
from one_job.domain.engine import ActionApplied, ActionCode, GameEngine
from one_job.domain.models import Player
from one_job.domain.roles import assign_roles
from one_job.domain.types import PlayerId, ResultReason, RoundId
from one_job.protocol.mapping import ACTION_ERRORS, domain_action
from one_job.protocol.messages import ActionInput, ErrorCode, LobbyStage
from one_job.protocol.role_messages import BriefingStatus, RoleAssignedPayload, RoleStatePayload


class RoundService:
    def __init__(
        self,
        config: GameConfig,
        seed: int,
        players: Sequence[Player],
        round_id: RoundId,
        now: float,
        briefing_timeout: float = 60.0,
    ) -> None:
        if (
            isinstance(briefing_timeout, bool)
            or not math.isfinite(briefing_timeout)
            or briefing_timeout <= 0
        ):
            raise ValueError("briefing timeout must be positive and finite")
        rng = Random(seed)
        self._seed = seed
        roster = tuple(players)
        assignments = assign_roles(roster, rng)
        self.engine = GameEngine(config, seed, roster, assignments, round_id=round_id, rng=rng)
        self.runner = RoomRunner(self.engine)
        self._sequences: dict[PlayerId, int] = {}
        self._acknowledged: set[PlayerId] = set()
        self._remaining = briefing_timeout
        self.result_announced = False
        self.deadline: float | None = now + briefing_timeout

    @property
    def seed(self) -> int:
        """Private reproduction identity, used only by the room's rematch guard."""
        return self._seed

    @property
    def round_id(self) -> RoundId:
        return self.engine.snapshot().round.round_id

    @property
    def stage(self) -> LobbyStage:
        return self.engine.snapshot().round.stage.value

    @property
    def terminal(self) -> bool:
        return self.stage in ("aborted", "finished")

    @property
    def complete(self) -> bool:
        return len(self._acknowledged) == len(self.engine.snapshot().players)

    def assigned(self, player_id: PlayerId) -> RoleAssignedPayload:
        return assigned_view(self.engine.snapshot(), player_id)

    def view(self, player_id: PlayerId, now: float) -> RoleStatePayload:
        remaining = self._remaining if self.deadline is None else max(0.0, self.deadline - now)
        return player_view(
            self.engine.snapshot(),
            player_id,
            BriefingStatus(
                acknowledged=player_id in self._acknowledged,
                waiting_player_ids=tuple(
                    str(player.player_id)
                    for player in self.engine.snapshot().players
                    if player.player_id not in self._acknowledged
                ),
                remaining_ms=int(remaining * 1000),
                complete=self.complete,
                held_for_gameplay=False,
            ),
        )

    def acknowledge(
        self, player_id: PlayerId, round_id: str, now: float
    ) -> tuple[ErrorCode | None, bool]:
        self.expire(now)
        if round_id.lower() != str(self.round_id):
            return ErrorCode.STALE_ROUND, False
        if player_id not in self.engine.snapshot().assignments.player_ids:
            return ErrorCode.NOT_AUTHENTICATED, False
        if self.complete and self.stage in ("countdown", "running"):
            return None, False
        if self.stage != "briefing":
            return ErrorCode.INVALID_STAGE, False
        changed = player_id not in self._acknowledged
        self._acknowledged.add(player_id)
        if self.complete:
            self.deadline = None
            self._remaining = 0
            self.engine.begin_countdown()
            self.runner.reset(now)
        return None, changed

    def submit_action(
        self, player_id: PlayerId, round_id: str, sequence: int, action: ActionInput
    ) -> tuple[ErrorCode | None, ActionApplied | None]:
        if round_id.lower() != str(self.round_id):
            return ErrorCode.STALE_ROUND, None
        if player_id not in self.engine.snapshot().assignments.player_ids:
            return ErrorCode.NOT_AUTHENTICATED, None
        if sequence <= self._sequences.get(player_id, 0):
            return ErrorCode.STALE_ACTION, None
        self._sequences[player_id] = sequence
        authorization = self.engine.authorize_action(player_id, domain_action(action))
        if authorization != ActionCode.ACCEPTED:
            return ACTION_ERRORS[authorization], None
        result = self.engine.apply_action(player_id, domain_action(action))
        if not result.accepted:
            return ACTION_ERRORS[result.code], None
        return None, result.events[0]

    def pause(self, now: float) -> None:
        if self.terminal or self.stage == "paused":
            return
        if self.deadline is not None:
            self._remaining = max(0.0, self.deadline - now)
            self.deadline = None
        self.engine.pause()
        self.runner.suspend()

    def resume(self, now: float) -> None:
        if self.stage != "paused":
            return
        self.engine.resume()
        if self.engine.snapshot().round.stage in ("countdown", "running"):
            self.runner.reset(now)
        elif not self.complete:
            self.deadline = now + self._remaining

    def abort(self, reason: ResultReason) -> None:
        self.engine.abort(reason)
        self.runner.suspend()
        self.deadline = None
        self._remaining = 0

    def expire(self, now: float) -> bool:
        if self.deadline is not None and now >= self.deadline:
            self.abort(ResultReason.BRIEFING_TIMEOUT)
            return True
        return False
