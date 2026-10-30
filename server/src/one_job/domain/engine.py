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
from one_job.domain.config import COUNTDOWN_MS, TICK_MS, GameConfig
from one_job.domain.emergencies import EmergencyChanged, advance_emergencies
from one_job.domain.models import (
    GameResult,
    GameState,
    Player,
    RoleAssignment,
    RoundState,
    ShipState,
)
from one_job.domain.rules import advance_ship, age_ship
from one_job.domain.scheduler import EmergencyScheduler
from one_job.domain.types import (
    Lane,
    MoveDirection,
    Outcome,
    PlayerId,
    ResultReason,
    RoundId,
    RoundStage,
)

ENGINE_VERSION = "spaceship-engine-v3"
type EngineAction = PlayerAction


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
    events: tuple[EmergencyChanged | RoundEnded, ...] = ()


class GameEngine:
    """Own one round. Call actions in authoritative order, then tick whole steps."""

    __slots__ = ("_state", "_rng", "_accepted_actions", "_scheduler", "_resolved", "_failed")

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
        self._scheduler = EmergencyScheduler(config, self._rng)
        self._resolved = 0
        self._failed = 0

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

    def begin_countdown(self) -> GameState:
        """Enter a pure pre-game countdown; resources, ticks and RNG stay frozen."""
        if self._state.round.stage != RoundStage.BRIEFING:
            raise ValueError("only a briefing can enter countdown")
        self._state = replace(
            self._state,
            round=replace(
                self._state.round, stage=RoundStage.COUNTDOWN, countdown_remaining_ms=COUNTDOWN_MS
            ),
        )
        return self._state

    def advance_countdown(self, elapsed_ms: int) -> GameState:
        integer(elapsed_ms, "elapsed_ms", 1)
        if self._state.round.stage != RoundStage.COUNTDOWN:
            raise ValueError("only an active countdown can advance")
        remaining = max(0, (self._state.round.countdown_remaining_ms or 0) - elapsed_ms)
        self._state = replace(
            self._state,
            round=replace(
                self._state.round,
                stage=RoundStage.COUNTDOWN if remaining else RoundStage.RUNNING,
                countdown_remaining_ms=remaining if remaining else None,
            ),
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
            resolved_count=self._resolved,
            failed_count=self._failed,
        )
        self._state = replace(
            self._state,
            emergencies=(),
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
        elif isinstance(action, Evade):
            if ship.cooldowns.evade or ship.evade_remaining_ticks:
                return ActionResult(ActionCode.COOLDOWN)
            if ship.engine_output < state.config.evade_min_output:
                return ActionResult(ActionCode.INSUFFICIENT_POWER)
            ship = replace(
                ship,
                evade_remaining_ticks=state.config.evade_duration_ticks,
                cooldowns=replace(ship.cooldowns, evade=state.config.evade_cooldown_ticks),
            )
            applied = action
        elif isinstance(action, EmergencyShutdown):
            ship = replace(
                ship,
                engine_output=0,
                engine_boost_remaining_ticks=0,
                recharge_remaining_ticks=0,
                shield_boost_remaining_ticks=0,
                shield_active=False,
            )
            applied = action
        elif isinstance(action, SetShield):
            if action.active and ship.shield_energy == 0:
                return ActionResult(ActionCode.INVALID_ACTION)
            ship = replace(ship, shield_active=action.active, shield_facing=action.facing)
            if ship.available_power(state.config) < 0:
                return ActionResult(ActionCode.INSUFFICIENT_POWER)
            applied = action
        elif isinstance(action, (EngineBoost, RechargeShield, ShieldBoost)):
            if isinstance(action, EngineBoost):
                duration, cooldown = "engine_boost_remaining_ticks", "engine_boost"
                ticks = state.config.engine_boost_duration_ticks
                wait = state.config.engine_boost_cooldown_ticks
            elif isinstance(action, RechargeShield):
                duration, cooldown = "recharge_remaining_ticks", "recharge_shield"
                ticks = state.config.recharge_duration_ticks
                wait = state.config.recharge_cooldown_ticks
            else:
                duration, cooldown = "shield_boost_remaining_ticks", "shield_boost"
                ticks = state.config.shield_boost_duration_ticks
                wait = state.config.shield_boost_cooldown_ticks
            if getattr(ship, duration) or getattr(ship.cooldowns, cooldown):
                return ActionResult(ActionCode.COOLDOWN)
            cooldowns = replace(ship.cooldowns, **{cooldown: wait})
            if isinstance(action, EngineBoost):
                ship = replace(ship, engine_boost_remaining_ticks=ticks, cooldowns=cooldowns)
            elif isinstance(action, RechargeShield):
                ship = replace(ship, recharge_remaining_ticks=ticks, cooldowns=cooldowns)
            else:
                ship = replace(ship, shield_boost_remaining_ticks=ticks, cooldowns=cooldowns)
            if ship.available_power(state.config) < 0:
                return ActionResult(ActionCode.INSUFFICIENT_POWER)
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
        events: list[EmergencyChanged | RoundEnded] = []
        for _ in range(steps):
            if self._state.round.stage != RoundStage.RUNNING:
                break
            state = self._state
            tick_index = state.tick_index + 1
            continuous = advance_ship(state.ship, state.config, age_timers=False)
            emergencies = advance_emergencies(
                continuous, state.emergencies, tick_index, state.config
            )
            ship = age_ship(emergencies.ship)
            active = emergencies.active
            events.extend(emergencies.events)
            self._resolved += sum(event.status == "resolved" for event in emergencies.events)
            self._failed += sum(event.status == "failed" for event in emergencies.events)
            result: GameResult | None = None
            if ship.hull == 0 or tick_index == state.config.duration_ticks:
                outcome = Outcome.DEFEAT if ship.hull == 0 else Outcome.VICTORY
                result = GameResult(
                    outcome=outcome,
                    reason=ResultReason.HULL_DESTROYED if ship.hull == 0 else ResultReason.SURVIVED,
                    survived_ms=tick_index * TICK_MS,
                    final_hull=ship.hull,
                    players=state.players,
                    resolved_count=self._resolved,
                    failed_count=self._failed,
                )
                active = ()
            else:
                active, started = self._scheduler.start_due(tick_index, ship, active)
                events.extend(started)
            round_state = replace(
                state.round,
                stage=RoundStage.FINISHED if result is not None else RoundStage.RUNNING,
                tick_index=tick_index,
                result=result,
            )
            self._state = replace(state, ship=ship, round=round_state, emergencies=active)
            if result is not None:
                events.append(RoundEnded(result))
                break
        return TickResult(self._state, tuple(events))
