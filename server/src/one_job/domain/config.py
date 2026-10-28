"""Immutable spaceship settings and the single source of provisional balance defaults."""

from dataclasses import dataclass

from one_job.domain._validation import boolean, enumeration, integer
from one_job.domain.types import Lane, ShieldFacing

TICK_MS = 100
RESOURCE_MAX = 1000
OUTPUT_MAX = 100
MIN_ROUND_MS = 60_000
MAX_ROUND_MS = 120_000
COUNTDOWN_MS = 3000


@dataclass(frozen=True, slots=True)
class GameConfig:
    version: str = "spaceship-v1"
    round_duration_ms: int = 90_000
    initial_hull: int = 1000
    initial_shield_energy: int = 600
    initial_engine_output: int = 40
    initial_temperature: int = 300
    initial_lane: Lane = Lane.CENTER
    initial_shield_facing: ShieldFacing = ShieldFacing.FRONT
    initial_shield_active: bool = False
    move_lane_cooldown_ticks: int = 2
    evade_min_output: int = 60
    evade_duration_ticks: int = 10
    evade_cooldown_ticks: int = 80
    engine_boost_power_cost: int = 25
    engine_boost_duration_ticks: int = 20
    engine_boost_heat_per_tick: int = 4
    engine_boost_cooldown_ticks: int = 100
    coolant_amount: int = 200
    coolant_cooldown_ticks: int = 30
    high_output_threshold: int = 60
    heat_gain_per_tick: int = 2
    cooling_per_tick: int = 1
    critical_temperature: int = 1000
    critical_heat_hull_damage: int = 5
    shield_hold_power_cost: int = 15
    shield_drain_per_tick: int = 1
    recharge_power_cost: int = 20
    recharge_duration_ticks: int = 30
    recharge_energy_per_tick: int = 6
    recharge_cooldown_ticks: int = 60
    shield_boost_power_cost: int = 25
    shield_boost_duration_ticks: int = 10
    shield_boost_energy_per_tick: int = 20
    shield_boost_cooldown_ticks: int = 150
    asteroid_deadline_ticks: int = 80
    asteroid_shield_cost: int = 200
    asteroid_hull_damage: int = 250
    overheat_trigger_temperature: int = 800
    overheat_target_temperature: int = 550
    overheat_target_max_output: int = 50
    overheat_deadline_ticks: int = 80
    overheat_hull_damage: int = 200
    overheat_failure_temperature: int = 650
    overload_target_max_output: int = 45
    overload_deadline_ticks: int = 70
    overload_hold_ticks: int = 20
    overload_hull_damage: int = 100
    max_active_emergencies: int = 2
    first_emergency_tick: int = 80
    early_interval_min_ticks: int = 80
    early_interval_max_ticks: int = 120
    middle_interval_min_ticks: int = 60
    middle_interval_max_ticks: int = 100
    late_interval_min_ticks: int = 40
    late_interval_max_ticks: int = 80

    def __post_init__(self) -> None:
        if (
            not isinstance(self.version, str)
            or not self.version
            or self.version.strip() != self.version
        ):
            raise ValueError("version must be a nonempty, trimmed string")
        integer(self.round_duration_ms, "round_duration_ms", MIN_ROUND_MS, MAX_ROUND_MS)
        if self.round_duration_ms % TICK_MS:
            raise ValueError("round_duration_ms must contain whole 100ms ticks")
        enumeration(self.initial_lane, Lane, "initial_lane")
        enumeration(self.initial_shield_facing, ShieldFacing, "initial_shield_facing")
        boolean(self.initial_shield_active, "initial_shield_active")
        integer(self.initial_hull, "initial_hull", 1, RESOURCE_MAX)
        for name in (
            "initial_shield_energy",
            "initial_temperature",
            "engine_boost_heat_per_tick",
            "coolant_amount",
            "heat_gain_per_tick",
            "cooling_per_tick",
            "critical_temperature",
            "critical_heat_hull_damage",
            "shield_drain_per_tick",
            "recharge_energy_per_tick",
            "shield_boost_energy_per_tick",
            "asteroid_shield_cost",
            "asteroid_hull_damage",
            "overheat_trigger_temperature",
            "overheat_target_temperature",
            "overheat_hull_damage",
            "overheat_failure_temperature",
            "overload_hull_damage",
        ):
            integer(getattr(self, name), name, 0, RESOURCE_MAX)
        for name in (
            "initial_engine_output",
            "evade_min_output",
            "engine_boost_power_cost",
            "high_output_threshold",
            "shield_hold_power_cost",
            "recharge_power_cost",
            "shield_boost_power_cost",
            "overheat_target_max_output",
            "overload_target_max_output",
        ):
            integer(getattr(self, name), name, 0, OUTPUT_MAX)
        for name in (
            "move_lane_cooldown_ticks",
            "evade_duration_ticks",
            "evade_cooldown_ticks",
            "engine_boost_duration_ticks",
            "engine_boost_cooldown_ticks",
            "coolant_cooldown_ticks",
            "recharge_duration_ticks",
            "recharge_cooldown_ticks",
            "shield_boost_duration_ticks",
            "shield_boost_cooldown_ticks",
            "asteroid_deadline_ticks",
            "overheat_deadline_ticks",
            "overload_deadline_ticks",
            "overload_hold_ticks",
            "first_emergency_tick",
            "early_interval_min_ticks",
            "early_interval_max_ticks",
            "middle_interval_min_ticks",
            "middle_interval_max_ticks",
            "late_interval_min_ticks",
            "late_interval_max_ticks",
        ):
            integer(getattr(self, name), name, 1)
        integer(self.max_active_emergencies, "max_active_emergencies", 1, 2)
        for period in ("early", "middle", "late"):
            if getattr(self, f"{period}_interval_min_ticks") > getattr(
                self, f"{period}_interval_max_ticks"
            ):
                raise ValueError(f"{period} interval minimum exceeds its maximum")
        if not (
            self.overheat_target_temperature
            <= self.overheat_failure_temperature
            < self.overheat_trigger_temperature
            <= self.critical_temperature
        ):
            raise ValueError(
                "overheat temperatures must be ordered target <= reset < trigger <= critical"
            )
        if self.overload_hold_ticks > self.overload_deadline_ticks:
            raise ValueError("overload hold cannot exceed its deadline")
        if self.initial_shield_active and (
            self.initial_shield_energy == 0
            or self.initial_engine_output < self.shield_hold_power_cost
        ):
            raise ValueError("initial active shields need energy and sufficient power")

    @property
    def duration_ticks(self) -> int:
        return self.round_duration_ms // TICK_MS


DEFAULT_CONFIG = GameConfig()
