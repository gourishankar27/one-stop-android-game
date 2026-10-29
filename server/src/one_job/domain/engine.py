"""Single-owner synchronous spaceship baseline, independent of transport and clocks."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from random import Random
from uuid import UUID

from one_job.domain._validation import enumeration, frozen_sequence, integer
from one_job.domain.actions import (
    Coolant,
    EmergencyShutdown,
    EngineBoost,
    Evade,
    MoveLane,
    PlayerAction,
    RechargeShield,
    SetEnginePower,
    SetShield,
    ShieldBoost,
)
from one_job.domain.config import TICK_MS, GameConfig
from one_job.domain.models import (
    GameResult,
    GameState,
    Player,
    RoleAssignment,
    RoundState,
    ShipState,
)
from one_job.domain.rules import advance_ship
from one_job.domain.types import (
    Lane,
    MoveDirection,
    Outcome,
    PlayerId,
    ResultReason,
    RoundId,
    RoundStage,
)

ENGINE_VERSION = "spaceship-engine-v1"
type EngineAction = SetEnginePower | MoveLane | Coolant


class ActionCode(StrEnum):
    ACCEPTED = "accepted"
    INVALID_STAGE = "invalid_stage"
    NOT_PARTICIPANT = "not_participant"
    INVALID_ACTION = "invalid_action"
    FEATURE_UNAVAILABLE = "feature_unavailable"
    NOT_ROLE_OWNER = "not_role_owner"
    INSUFFICIENT_POWER = "insufficient_power"
    COOLDOWN = "cooldown"
    LANE_BOUNDARY = "lane_boundary"


@dataclass(frozen=True, slots=True)
class ActionApplied:
    """Accepted-command trace/event at a boundary, before the next tick's effects."""

    tick_index: int
    order: int
    actor_id: PlayerId
    action: EngineAction


@dataclass(frozen=True, slots=True)
class ActionResult:
    code: ActionCode
    events: tuple[ActionApplied, ...] = ()

    def __post_init__(self) -> None:
        enumeration(self.code, ActionCode, "code")
        events = frozen_sequence(self.events, ActionApplied, "events")
        if len(events) != (1 if self.code == ActionCode.ACCEPTED else 0):
            raise ValueError("accepted actions emit one event; rejected actions emit none")
        object.__setattr__(self, "events", events)

    @property
    def accepted(self) -> bool:
        return self.code == ActionCode.ACCEPTED


@dataclass(frozen=True, slots=True)
class RoundEnded:
    result: GameResult


@dataclass(frozen=True, slots=True)
class TickResult:
    state: GameState
    events: tuple[RoundEnded, ...] = ()


class GameEngine:
    """Own one round. Call actions in authoritative order, then tick whole steps."""

    __slots__ = ("_state", "_rng", "_accepted_actions")

    def __init__(
        self,
        config: GameConfig,
        seed: int,
        players: Sequence[Player],
        assignments: RoleAssignment,
        *,
        round_id: RoundId,
        rng: Random | None = None,
    ) -> None:
        if not isinstance(config, GameConfig):
            raise ValueError("config must be a GameConfig value")
        if type(seed) is not int:
            raise ValueError("seed must be an integer, not a coerced value")
        # GameState validates and freezes roster/assignments before engine ownership begins.
        self._state = GameState(
            config=config,
            players=frozen_sequence(players, Player, "players"),
            assignments=assignments,
            ship=ShipState.from_config(config),
            round=RoundState(round_id, duration_ms=config.round_duration_ms),
        )
        self._rng = Random(seed)
        if rng is not None:
            if not isinstance(rng, Random):
                raise ValueError("rng must be a Random")
            self._rng.setstate(rng.getstate())
        self._accepted_actions: list[ActionApplied] = []

    def snapshot(self) -> GameState:
        """Return the immutable internal snapshot; callers must project it for transport."""
        return self._state

    @property
    def accepted_actions(self) -> tuple[ActionApplied, ...]:
        return tuple(self._accepted_actions)

    def start(self) -> GameState:
        if self._state.round.stage != RoundStage.BRIEFING:
            raise ValueError("a round can only be started once")
        self._state = replace(
            self._state, round=replace(self._state.round, stage=RoundStage.RUNNING)
        )
        return self._state

    def authorize_action(self, actor_id: PlayerId, action: PlayerAction) -> ActionCode:
        """Check every typed station intent independently of simulation stage."""
        if not isinstance(actor_id, UUID) or actor_id not in self._state.assignments.player_ids:
            return ActionCode.NOT_PARTICIPANT
        if type(action) not in (
            MoveLane,
            Evade,
            SetEnginePower,
            EngineBoost,
            Coolant,
            EmergencyShutdown,
            SetShield,
            RechargeShield,
            ShieldBoost,
        ):
            return ActionCode.INVALID_ACTION
        try:
            action = replace(action)
        except (ValueError, AttributeError):
            return ActionCode.INVALID_ACTION
        if self._state.assignments.owners[action.role] != actor_id:
            return ActionCode.NOT_ROLE_OWNER
        return ActionCode.ACCEPTED

    def pause(self) -> GameState:
        stage = self._state.round.stage
        if stage not in (RoundStage.BRIEFING, RoundStage.COUNTDOWN, RoundStage.RUNNING):
            raise ValueError("only active rounds can pause")
        self._state = replace(
            self._state,
            round=replace(
                self._state.round,
                stage=RoundStage.PAUSED,
                paused_from=stage,
            ),
        )
        return self._state

    def resume(self) -> GameState:
        previous = self._state.round.paused_from
        if self._state.round.stage != RoundStage.PAUSED or previous is None:
            raise ValueError("only a paused round can resume")
        self._state = replace(
            self._state,
            round=replace(
                self._state.round,
                stage=previous,
                paused_from=None,
            ),
        )
        return self._state

    def abort(self, reason: ResultReason) -> GameState:
        enumeration(reason, ResultReason, "reason")
        if reason not in (
            ResultReason.DISCONNECT_TIMEOUT,
            ResultReason.PLAYER_LEFT,
            ResultReason.BRIEFING_TIMEOUT,
            ResultReason.SERVER_OVERLOAD,
        ):
            raise ValueError("an abort needs an abort reason")
        if self._state.round.stage in (RoundStage.FINISHED, RoundStage.ABORTED):
            return self._state
        result = GameResult(
            Outcome.ABORTED,
            reason,
            self._state.tick_index * TICK_MS,
            self._state.ship.hull,
            players=self._state.players,
        )
        self._state = replace(
            self._state,
            round=replace(
                self._state.round,
                stage=RoundStage.ABORTED,
                paused_from=None,
                countdown_remaining_ms=None,
                result=result,
            ),
        )
        return self._state

    def apply_action(self, actor_id: PlayerId, action: PlayerAction) -> ActionResult:
        """Apply supported intents immediately at the current completed-tick boundary."""
        state = self._state
        if state.round.stage != RoundStage.RUNNING:
            return ActionResult(ActionCode.INVALID_STAGE)
        authorization = self.authorize_action(actor_id, action)
        if authorization != ActionCode.ACCEPTED:
            return ActionResult(authorization)
        if type(action) in (
            Evade,
            EngineBoost,
            EmergencyShutdown,
            SetShield,
            RechargeShield,
            ShieldBoost,
        ):
            return ActionResult(ActionCode.FEATURE_UNAVAILABLE)
        if type(action) not in (SetEnginePower, MoveLane, Coolant):
            return ActionResult(ActionCode.INVALID_ACTION)
        # Revalidate the value object before any mutation, even if a caller bypassed freezing.
        try:
            action = replace(action)
        except (ValueError, AttributeError):
            return ActionResult(ActionCode.INVALID_ACTION)
        if state.assignments.owners[action.role] != actor_id:
            return ActionResult(ActionCode.NOT_ROLE_OWNER)
        ship = state.ship
        applied: EngineAction
        if isinstance(action, SetEnginePower):
            ship = replace(ship, engine_output=action.value)
            if ship.available_power(state.config) < 0:
                return ActionResult(ActionCode.INSUFFICIENT_POWER)
            applied = action
        elif isinstance(action, MoveLane):
            if ship.cooldowns.move_lane:
                return ActionResult(ActionCode.COOLDOWN)
            lanes = (Lane.LEFT, Lane.CENTER, Lane.RIGHT)
            index = lanes.index(ship.lane) + (-1 if action.direction == MoveDirection.LEFT else 1)
            if not 0 <= index < len(lanes):
                return ActionResult(ActionCode.LANE_BOUNDARY)
            ship = replace(
                ship,
                lane=lanes[index],
                cooldowns=replace(ship.cooldowns, move_lane=state.config.move_lane_cooldown_ticks),
            )
            applied = action
        elif isinstance(action, Coolant):
            if ship.cooldowns.coolant:
                return ActionResult(ActionCode.COOLDOWN)
            ship = replace(
                ship,
                temperature=max(0, ship.temperature - state.config.coolant_amount),
                cooldowns=replace(ship.cooldowns, coolant=state.config.coolant_cooldown_ticks),
            )
            applied = action
        else:
            return ActionResult(ActionCode.INVALID_ACTION)
        candidate = replace(state, ship=ship)
        event = ActionApplied(state.tick_index, len(self._accepted_actions) + 1, actor_id, applied)
        self._state = candidate
        self._accepted_actions.append(event)
        return ActionResult(ActionCode.ACCEPTED, (event,))

    def tick(self, steps: int = 1) -> TickResult:
        """Advance positive whole 100ms steps, stopping at the first terminal tick."""
        integer(steps, "steps", 1)
        if self._state.round.stage == RoundStage.BRIEFING:
            raise ValueError("start the round before ticking")
        events: list[RoundEnded] = []
        for _ in range(steps):
            if self._state.round.stage != RoundStage.RUNNING:
                break
            state = self._state
            ship = advance_ship(state.ship, state.config)
            tick_index = state.tick_index + 1
            result: GameResult | None = None
            if ship.hull == 0 or tick_index == state.config.duration_ticks:
                outcome = Outcome.DEFEAT if ship.hull == 0 else Outcome.VICTORY
                result = GameResult(
                    outcome=outcome,
                    reason=ResultReason.HULL_DESTROYED if ship.hull == 0 else ResultReason.SURVIVED,
                    survived_ms=tick_index * TICK_MS,
                    final_hull=ship.hull,
                    players=state.players,
                )
            round_state = replace(
                state.round,
                stage=RoundStage.FINISHED if result is not None else RoundStage.RUNNING,
                tick_index=tick_index,
                result=result,
            )
            self._state = replace(state, ship=ship, round=round_state)
            if result is not None:
                events.append(RoundEnded(result))
                break
        return TickResult(self._state, tuple(events))
