"""Immutable domain snapshots with constructor invariants, without simulation."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields
from types import MappingProxyType
from typing import ClassVar, Self
from unicodedata import category

from one_job.domain._validation import (
    boolean,
    enumeration,
    frozen_sequence,
    identifier,
    integer,
    mapping,
)
from one_job.domain.config import (
    COUNTDOWN_MS,
    DEFAULT_CONFIG,
    MAX_ROUND_MS,
    MIN_ROUND_MS,
    OUTPUT_MAX,
    RESOURCE_MAX,
    TICK_MS,
    GameConfig,
)
from one_job.domain.types import (
    EmergencyId,
    EmergencyState,
    EmergencyType,
    Lane,
    Outcome,
    PlayerId,
    ResultReason,
    Role,
    RoundId,
    RoundStage,
    ShieldFacing,
)


def _participant_ids(values: Sequence[PlayerId]) -> tuple[PlayerId, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError("participant IDs must be a sequence")
    ids = tuple(values)
    for value in ids:
        identifier(value, "player_id")
    if len(ids) not in (2, 3) or len(set(ids)) != len(ids):
        raise ValueError("a round needs exactly two or three distinct participants")
    return ids


@dataclass(frozen=True, slots=True)
class Player:
    """A frozen round participant; room connectivity/readiness are not domain state."""

    player_id: PlayerId
    name: str

    def __post_init__(self) -> None:
        identifier(self.player_id, "player_id")
        if not isinstance(self.name, str) or any(category(char) == "Cc" for char in self.name):
            raise ValueError("name must be a string without control characters")
        name = self.name.strip()
        if not 1 <= len(name) <= 20:
            raise ValueError("trimmed name must contain 1 to 20 Unicode characters")
        object.__setattr__(self, "name", name)


@dataclass(frozen=True, slots=True)
class RoleAssignment:
    player_ids: tuple[PlayerId, ...]
    owners: Mapping[Role, PlayerId]

    def __post_init__(self) -> None:
        ids = _participant_ids(self.player_ids)
        mapping(self.owners, "owners")
        owners = dict(self.owners)
        for role, owner in owners.items():
            enumeration(role, Role, "role")
            identifier(owner, "owner")
        if set(owners) != set(Role) or not set(owners.values()) <= set(ids):
            raise ValueError("every station needs exactly one owner from the participant roster")
        if len(ids) == 3 and set(owners.values()) != set(ids):
            raise ValueError("three players must own one station each")
        if len(ids) == 2 and (
            owners[Role.PILOT] == owners[Role.ENGINEER]
            or owners[Role.ENGINEER] != owners[Role.SHIELDS]
        ):
            raise ValueError("two players must split Pilot / Engineer+Shields")
        object.__setattr__(self, "player_ids", ids)
        object.__setattr__(self, "owners", MappingProxyType(owners))

    def roles_for(self, player_id: PlayerId) -> tuple[Role, ...]:
        identifier(player_id, "player_id")
        if player_id not in self.player_ids:
            raise ValueError("player_id is not a participant")
        return tuple(role for role in Role if self.owners[role] == player_id)


@dataclass(frozen=True, slots=True)
class Cooldowns:
    move_lane: int = 0
    evade: int = 0
    engine_boost: int = 0
    coolant: int = 0
    recharge_shield: int = 0
    shield_boost: int = 0

    def __post_init__(self) -> None:
        for item in fields(self):
            integer(getattr(self, item.name), item.name)


@dataclass(frozen=True, slots=True)
class ShipState:
    hull: int = DEFAULT_CONFIG.initial_hull
    shield_energy: int = DEFAULT_CONFIG.initial_shield_energy
    engine_output: int = DEFAULT_CONFIG.initial_engine_output
    temperature: int = DEFAULT_CONFIG.initial_temperature
    lane: Lane = DEFAULT_CONFIG.initial_lane
    shield_facing: ShieldFacing = DEFAULT_CONFIG.initial_shield_facing
    shield_active: bool = DEFAULT_CONFIG.initial_shield_active
    cooldowns: Cooldowns = field(default_factory=Cooldowns)
    evade_remaining_ticks: int = 0
    engine_boost_remaining_ticks: int = 0
    recharge_remaining_ticks: int = 0
    shield_boost_remaining_ticks: int = 0

    def __post_init__(self) -> None:
        for name in ("hull", "shield_energy", "temperature"):
            integer(getattr(self, name), name, 0, RESOURCE_MAX)
        integer(self.engine_output, "engine_output", 0, OUTPUT_MAX)
        enumeration(self.lane, Lane, "lane")
        enumeration(self.shield_facing, ShieldFacing, "shield_facing")
        boolean(self.shield_active, "shield_active")
        if not isinstance(self.cooldowns, Cooldowns):
            raise ValueError("cooldowns must be a Cooldowns value")
        for name in (
            "evade_remaining_ticks",
            "engine_boost_remaining_ticks",
            "recharge_remaining_ticks",
            "shield_boost_remaining_ticks",
        ):
            integer(getattr(self, name), name)
        if self.shield_active and self.shield_energy == 0:
            raise ValueError("active shields need nonzero energy")

    @classmethod
    def from_config(cls, config: GameConfig) -> Self:
        if not isinstance(config, GameConfig):
            raise ValueError("config must be a GameConfig value")
        return cls(
            hull=config.initial_hull,
            shield_energy=config.initial_shield_energy,
            engine_output=config.initial_engine_output,
            temperature=config.initial_temperature,
            lane=config.initial_lane,
            shield_facing=config.initial_shield_facing,
            shield_active=config.initial_shield_active,
        )

    def available_power(self, config: GameConfig) -> int:
        if not isinstance(config, GameConfig):
            raise ValueError("config must be a GameConfig value")
        return self.engine_output - (
            config.shield_hold_power_cost * self.shield_active
            + config.engine_boost_power_cost * (self.engine_boost_remaining_ticks > 0)
            + config.recharge_power_cost * (self.recharge_remaining_ticks > 0)
            + config.shield_boost_power_cost * (self.shield_boost_remaining_ticks > 0)
        )


@dataclass(frozen=True, slots=True)
class AsteroidTarget:
    impact_lane: Lane
    required_facing: ShieldFacing
    kind: ClassVar[EmergencyType] = EmergencyType.ASTEROID

    def __post_init__(self) -> None:
        enumeration(self.impact_lane, Lane, "impact_lane")
        enumeration(self.required_facing, ShieldFacing, "required_facing")


@dataclass(frozen=True, slots=True)
class OverheatingTarget:
    max_output: int = DEFAULT_CONFIG.overheat_target_max_output
    max_temperature: int = DEFAULT_CONFIG.overheat_target_temperature
    kind: ClassVar[EmergencyType] = EmergencyType.OVERHEATING

    def __post_init__(self) -> None:
        integer(self.max_output, "max_output", 0, OUTPUT_MAX)
        integer(self.max_temperature, "max_temperature", 0, RESOURCE_MAX)


@dataclass(frozen=True, slots=True)
class ShieldOverloadTarget:
    max_output: int = DEFAULT_CONFIG.overload_target_max_output
    hold_ticks: int = DEFAULT_CONFIG.overload_hold_ticks
    kind: ClassVar[EmergencyType] = EmergencyType.SHIELD_OVERLOAD

    def __post_init__(self) -> None:
        integer(self.max_output, "max_output", 0, OUTPUT_MAX)
        integer(self.hold_ticks, "hold_ticks", 1)


type EmergencyTarget = AsteroidTarget | OverheatingTarget | ShieldOverloadTarget


@dataclass(frozen=True, slots=True)
class Emergency:
    emergency_id: EmergencyId
    target: EmergencyTarget
    start_tick: int
    deadline_tick: int
    state: EmergencyState = EmergencyState.ACTIVE
    progress_ticks: int = 0
    finished_tick: int | None = None

    def __post_init__(self) -> None:
        integer(self.emergency_id, "emergency_id", 1)
        if not isinstance(self.target, (AsteroidTarget, OverheatingTarget, ShieldOverloadTarget)):
            raise ValueError("target must be a typed emergency target")
        enumeration(self.state, EmergencyState, "state")
        integer(self.start_tick, "start_tick")
        integer(self.deadline_tick, "deadline_tick", self.start_tick + 1)
        integer(self.progress_ticks, "progress_ticks", 0, self.deadline_tick - self.start_tick)
        if isinstance(self.target, ShieldOverloadTarget):
            if self.target.hold_ticks > self.deadline_tick - self.start_tick:
                raise ValueError("overload hold cannot exceed the emergency window")
            integer(self.progress_ticks, "progress_ticks", 0, self.target.hold_ticks)
        elif self.progress_ticks != 0:
            raise ValueError("only shield overload has consecutive-tick progress")
        if self.state == EmergencyState.ACTIVE:
            if self.finished_tick is not None:
                raise ValueError("an active emergency cannot have a finished tick")
        else:
            integer(self.finished_tick, "finished_tick", self.start_tick, self.deadline_tick)
            if self.state == EmergencyState.FAILED and self.finished_tick != self.deadline_tick:
                raise ValueError("a failed emergency must finish at its deadline")
            if (
                self.finished_tick is not None
                and self.progress_ticks > self.finished_tick - self.start_tick
            ):
                raise ValueError("progress cannot exceed the emergency's elapsed ticks")

    @property
    def kind(self) -> EmergencyType:
        return self.target.kind


@dataclass(frozen=True, slots=True)
class GameResult:
    outcome: Outcome
    reason: ResultReason
    survived_ms: int
    final_hull: int
    players: tuple[Player, ...]
    resolved_count: int = 0
    failed_count: int = 0

    def __post_init__(self) -> None:
        enumeration(self.outcome, Outcome, "outcome")
        enumeration(self.reason, ResultReason, "reason")
        integer(self.survived_ms, "survived_ms", 0, MAX_ROUND_MS)
        if self.survived_ms % TICK_MS:
            raise ValueError("survived_ms must contain whole simulation ticks")
        integer(self.final_hull, "final_hull", 0, RESOURCE_MAX)
        integer(self.resolved_count, "resolved_count")
        integer(self.failed_count, "failed_count")
        players = frozen_sequence(self.players, Player, "players")
        _participant_ids(tuple(player.player_id for player in players))
        object.__setattr__(self, "players", players)
        if self.outcome == Outcome.VICTORY:
            if self.reason != ResultReason.SURVIVED or self.final_hull == 0:
                raise ValueError("victory requires survival with positive hull")
            if self.survived_ms < MIN_ROUND_MS:
                raise ValueError("victory cannot precede a valid round duration")
        elif self.outcome == Outcome.DEFEAT:
            if self.reason != ResultReason.HULL_DESTROYED or self.final_hull != 0:
                raise ValueError("defeat requires destroyed hull")
        else:
            if (
                self.reason in (ResultReason.SURVIVED, ResultReason.HULL_DESTROYED)
                or self.final_hull == 0
            ):
                raise ValueError("aborted results require an abort reason and surviving hull")
            if self.reason == ResultReason.BRIEFING_TIMEOUT and self.survived_ms != 0:
                raise ValueError("briefing timeout must precede gameplay")

    @property
    def final_hull_percent(self) -> int:
        return self.final_hull * 100 // RESOURCE_MAX


@dataclass(frozen=True, slots=True)
class RoundState:
    round_id: RoundId
    stage: RoundStage = RoundStage.BRIEFING
    duration_ms: int = DEFAULT_CONFIG.round_duration_ms
    tick_index: int = 0
    paused_from: RoundStage | None = None
    countdown_remaining_ms: int | None = None
    result: GameResult | None = None

    def __post_init__(self) -> None:
        identifier(self.round_id, "round_id")
        enumeration(self.stage, RoundStage, "stage")
        integer(self.duration_ms, "duration_ms", MIN_ROUND_MS, MAX_ROUND_MS)
        if self.duration_ms % TICK_MS:
            raise ValueError("duration_ms must contain whole simulation ticks")
        integer(self.tick_index, "tick_index", 0, self.duration_ms // TICK_MS)
        if self.stage == RoundStage.PAUSED:
            if self.paused_from not in (
                RoundStage.BRIEFING,
                RoundStage.COUNTDOWN,
                RoundStage.RUNNING,
            ):
                raise ValueError("pause must remember an active prior stage")
            enumeration(self.paused_from, RoundStage, "paused_from")
        elif self.paused_from is not None:
            raise ValueError("paused_from is only valid while paused")
        effective_stage = self.paused_from if self.stage == RoundStage.PAUSED else self.stage
        if effective_stage in (RoundStage.BRIEFING, RoundStage.COUNTDOWN) and self.tick_index != 0:
            raise ValueError("gameplay time cannot advance before running")
        if effective_stage == RoundStage.COUNTDOWN:
            integer(self.countdown_remaining_ms, "countdown_remaining_ms", 0, COUNTDOWN_MS)
        elif self.countdown_remaining_ms is not None:
            raise ValueError("countdown time is only valid during countdown or its pause")
        terminal = self.stage in (RoundStage.FINISHED, RoundStage.ABORTED)
        if not terminal:
            if self.result is not None or self.remaining_ms == 0:
                raise ValueError("a nonterminal round cannot have a result or an expired timer")
        else:
            if not isinstance(self.result, GameResult):
                raise ValueError("a terminal round requires a GameResult")
            if self.result.survived_ms != self.elapsed_ms:
                raise ValueError("result survival time must match the round tick")
            if (self.stage == RoundStage.ABORTED) != (self.result.outcome == Outcome.ABORTED):
                raise ValueError("terminal stage must match the result outcome")
            if self.result.outcome == Outcome.VICTORY and self.remaining_ms != 0:
                raise ValueError("victory requires the configured duration to have elapsed")
            if self.result.outcome == Outcome.ABORTED and self.remaining_ms == 0:
                raise ValueError("an expired timer with surviving hull is victory, not an abort")

    @property
    def elapsed_ms(self) -> int:
        return self.tick_index * TICK_MS

    @property
    def remaining_ms(self) -> int:
        return self.duration_ms - self.elapsed_ms


@dataclass(frozen=True, slots=True)
class GameState:
    """Internal snapshot, never a wire projection or serialization contract."""

    config: GameConfig
    players: tuple[Player, ...]
    assignments: RoleAssignment
    ship: ShipState
    round: RoundState
    emergencies: tuple[Emergency, ...] = ()

    def __post_init__(self) -> None:
        for value, expected in (
            (self.config, GameConfig),
            (self.assignments, RoleAssignment),
            (self.ship, ShipState),
            (self.round, RoundState),
        ):
            if not isinstance(value, expected):
                raise ValueError(f"snapshot requires a {expected.__name__} value")
        players = frozen_sequence(self.players, Player, "players")
        ids = _participant_ids(tuple(player.player_id for player in players))
        if set(ids) != set(self.assignments.player_ids):
            raise ValueError("assignment roster must match snapshot participants")
        if self.round.duration_ms != self.config.round_duration_ms:
            raise ValueError("round duration must match config")
        if self.ship.available_power(self.config) < 0:
            raise ValueError("active consumers exceed generated power")
        for name, maximum in (
            ("evade_remaining_ticks", self.config.evade_duration_ticks),
            ("engine_boost_remaining_ticks", self.config.engine_boost_duration_ticks),
            ("recharge_remaining_ticks", self.config.recharge_duration_ticks),
            ("shield_boost_remaining_ticks", self.config.shield_boost_duration_ticks),
        ):
            integer(getattr(self.ship, name), name, 0, maximum)
        for name, maximum in (
            ("move_lane", self.config.move_lane_cooldown_ticks),
            ("evade", self.config.evade_cooldown_ticks),
            ("engine_boost", self.config.engine_boost_cooldown_ticks),
            ("coolant", self.config.coolant_cooldown_ticks),
            ("recharge_shield", self.config.recharge_cooldown_ticks),
            ("shield_boost", self.config.shield_boost_cooldown_ticks),
        ):
            integer(getattr(self.ship.cooldowns, name), name, 0, maximum)
        if self.round.result is not None:
            if (
                self.round.result.players != players
                or self.round.result.final_hull != self.ship.hull
            ):
                raise ValueError("result roster and hull must match the snapshot")
        elif self.ship.hull == 0:
            raise ValueError("destroyed hull requires a terminal result")
        emergencies = frozen_sequence(self.emergencies, Emergency, "emergencies")
        if len(emergencies) > self.config.max_active_emergencies:
            raise ValueError("too many active emergencies")
        if len({item.emergency_id for item in emergencies}) != len(emergencies):
            raise ValueError("emergency IDs must be unique")
        if len({item.kind for item in emergencies}) != len(emergencies):
            raise ValueError("only one active emergency of each kind is allowed")
        effective_stage = self.round.paused_from or self.round.stage
        if emergencies and effective_stage in (RoundStage.BRIEFING, RoundStage.COUNTDOWN):
            raise ValueError("emergencies cannot exist before gameplay")
        for emergency in emergencies:
            if emergency.state != EmergencyState.ACTIVE:
                raise ValueError(
                    "snapshot emergencies must be active; results hold completed counts"
                )
            if not emergency.start_tick <= self.tick_index <= emergency.deadline_tick:
                raise ValueError("emergency window must include the current tick")
            if emergency.progress_ticks > self.tick_index - emergency.start_tick:
                raise ValueError("emergency progress cannot exceed elapsed ticks")
        object.__setattr__(self, "players", players)
        object.__setattr__(self, "emergencies", emergencies)

    @property
    def tick_index(self) -> int:
        return self.round.tick_index

    @property
    def elapsed_ms(self) -> int:
        return self.round.elapsed_ms
