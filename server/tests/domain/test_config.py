from dataclasses import FrozenInstanceError, fields, replace

import pytest

from one_job.domain.config import DEFAULT_CONFIG, TICK_MS, GameConfig
from one_job.domain.models import ShipState
from one_job.domain.types import Lane, ShieldFacing


def test_defaults_match_initial_spaceship_values() -> None:
    config = GameConfig()
    ship = ShipState.from_config(config)
    assert config.version == "spaceship-v1"
    assert (TICK_MS, config.round_duration_ms, config.duration_ticks) == (100, 90_000, 900)
    assert (ship.hull, ship.shield_energy, ship.engine_output, ship.temperature) == (
        1000,
        600,
        40,
        300,
    )
    assert (ship.lane, ship.shield_facing, ship.shield_active) == (
        Lane.CENTER,
        ShieldFacing.FRONT,
        False,
    )
    assert ship.available_power(config) == 40


@pytest.mark.parametrize("duration", [60_000, 60_100, 90_000, 119_900, 120_000])
def test_config_accepts_supported_whole_tick_durations(duration: int) -> None:
    assert GameConfig(round_duration_ms=duration).duration_ticks == duration // 100


@pytest.mark.parametrize("duration", [59_900, 120_100, 60_001, 90_050])
def test_config_rejects_unsupported_durations(duration: int) -> None:
    with pytest.raises(ValueError):
        GameConfig(round_duration_ms=duration)


INTEGER_FIELDS = tuple(
    item.name for item in fields(GameConfig) if type(getattr(DEFAULT_CONFIG, item.name)) is int
)
TICK_FIELDS = tuple(
    name for name in INTEGER_FIELDS if name.endswith("_ticks") or name == "first_emergency_tick"
)


@pytest.mark.parametrize("name", INTEGER_FIELDS)
@pytest.mark.parametrize("value", [True, 1.0, "1", -1])
def test_all_numeric_settings_reject_coercion_and_negative_values(name: str, value: object) -> None:
    with pytest.raises(ValueError):
        replace(DEFAULT_CONFIG, **{name: value})


@pytest.mark.parametrize("name", TICK_FIELDS)
def test_durations_cooldowns_and_intervals_must_be_positive(name: str) -> None:
    with pytest.raises(ValueError):
        replace(DEFAULT_CONFIG, **{name: 0})


def test_equal_interval_endpoints_and_resource_edges_are_valid() -> None:
    config = GameConfig(
        initial_shield_energy=0,
        initial_engine_output=0,
        initial_temperature=1000,
        early_interval_min_ticks=120,
        middle_interval_max_ticks=60,
        late_interval_max_ticks=40,
        coolant_amount=1000,
        critical_heat_hull_damage=0,
        shield_hold_power_cost=0,
        engine_boost_power_cost=100,
        overheat_target_max_output=0,
        overload_target_max_output=100,
    )
    assert ShipState.from_config(config).available_power(config) == 0
    assert config.early_interval_min_ticks == config.early_interval_max_ticks


@pytest.mark.parametrize(
    "changes",
    [
        {"initial_hull": 0},
        {"initial_hull": 1001},
        {"initial_shield_energy": 1001},
        {"initial_engine_output": 101},
        {"initial_temperature": 1001},
        {"engine_boost_power_cost": 101},
        {"coolant_amount": 1001},
        {"recharge_energy_per_tick": 1001},
        {"shield_boost_energy_per_tick": 1001},
        {"critical_heat_hull_damage": 1001},
        {"asteroid_hull_damage": 1001},
        {"overheat_hull_damage": 1001},
        {"overload_hull_damage": 1001},
        {"max_active_emergencies": 0},
        {"max_active_emergencies": 3},
        {"move_lane_cooldown_ticks": 0},
        {"evade_duration_ticks": 0},
        {"overload_hold_ticks": 71},
        {"early_interval_min_ticks": 121},
        {"middle_interval_max_ticks": 59},
        {"late_interval_min_ticks": 81},
        {"overheat_target_temperature": 801},
        {"overheat_failure_temperature": 800},
        {"overheat_trigger_temperature": 1000, "critical_temperature": 999},
        {"initial_shield_active": 1},
        {"initial_shield_active": True, "initial_shield_energy": 0},
        {"initial_shield_active": True, "initial_engine_output": 14},
        {"initial_lane": "center"},
        {"initial_shield_facing": "front"},
        {"version": ""},
        {"version": "  v1"},
        {"version": None},
    ],
)
def test_config_rejects_out_of_range_and_incoherent_settings(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        GameConfig(**changes)


def test_custom_config_initializes_ship_without_mutating_defaults() -> None:
    config = GameConfig(
        version="custom-v1",
        round_duration_ms=60_000,
        initial_hull=1,
        initial_shield_energy=1000,
        initial_engine_output=100,
        initial_temperature=0,
        initial_lane=Lane.RIGHT,
        initial_shield_facing=ShieldFacing.REAR,
        initial_shield_active=True,
    )
    ship = ShipState.from_config(config)
    assert (ship.hull, ship.shield_energy, ship.engine_output, ship.temperature) == (
        1,
        1000,
        100,
        0,
    )
    assert ship.lane == Lane.RIGHT and ship.shield_facing == ShieldFacing.REAR
    assert ship.shield_active and ship.available_power(config) == 85
    assert DEFAULT_CONFIG == GameConfig()
    with pytest.raises(FrozenInstanceError):
        config.round_duration_ms = 90_000
