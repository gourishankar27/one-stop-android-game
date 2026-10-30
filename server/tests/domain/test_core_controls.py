"""Full station catalog: atomic permissions, reservations and exact fixed-step effects."""

from dataclasses import replace

import pytest

from one_job.domain.actions import (
    Coolant,
    EmergencyShutdown,
    EngineBoost,
    Evade,
    MoveLane,
    RechargeShield,
    SetEnginePower,
    SetShield,
    ShieldBoost,
)
from one_job.domain.engine import ActionCode, GameEngine
from one_job.domain.types import MoveDirection, ResultReason, RoundStage, ShieldFacing

ACTIONS = (
    MoveLane(MoveDirection.LEFT),
    Evade(),
    SetEnginePower(80),
    EngineBoost(),
    Coolant(),
    EmergencyShutdown(),
    SetShield(True, ShieldFacing.REAR),
    RechargeShield(),
    ShieldBoost(),
)


def construct(state, **config):
    return GameEngine(
        replace(state.config, emergencies_enabled=False, **config),
        123,
        state.players,
        state.assignments,
        round_id=state.round.round_id,
    )


def apply(engine, action):
    return engine.apply_action(engine.snapshot().assignments.owners[action.role], action)


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("stage", ["briefing", "countdown", "paused", "finished", "aborted"])
def test_every_action_rejects_nonrunning_without_any_mutation(game_state, action, stage):
    engine = construct(game_state, initial_engine_output=100)
    if stage == "countdown":
        engine._state = replace(
            engine.snapshot(),
            round=replace(
                engine.snapshot().round, stage=RoundStage.COUNTDOWN, countdown_remaining_ms=3000
            ),
        )
    elif stage != "briefing":
        engine.start()
        if stage == "paused":
            engine.pause()
        elif stage == "finished":
            engine.tick(900)
        else:
            engine.abort(ResultReason.PLAYER_LEFT)
    before, random_state = engine.snapshot(), engine._rng.getstate()
    assert apply(engine, action).code == ActionCode.INVALID_STAGE
    assert engine.snapshot() is before and engine.accepted_actions == ()
    assert engine._rng.getstate() == random_state


@pytest.mark.parametrize("action", ACTIONS)
def test_every_action_accepts_owned_and_rejects_foreign_atomically(game_state, action):
    engine = construct(game_state, initial_engine_output=100)
    before = engine.start()
    foreign = next(
        owner for role, owner in before.assignments.owners.items() if role != action.role
    )
    assert engine.apply_action(foreign, action).code == ActionCode.NOT_ROLE_OWNER
    assert engine.snapshot() is before and engine.accepted_actions == ()
    accepted = apply(engine, action)
    assert accepted.accepted
    assert accepted.events[0].tick_index == 0 and accepted.events[0].order == 1


@pytest.mark.parametrize(
    "action",
    [Evade(), EngineBoost(), RechargeShield(), ShieldBoost(), SetShield(True, ShieldFacing.FRONT)],
)
def test_power_rejections_do_not_partially_apply(game_state, action):
    engine = construct(game_state, initial_engine_output=0)
    before = engine.start()
    assert apply(engine, action).code == ActionCode.INSUFFICIENT_POWER
    assert engine.snapshot() is before and not engine.accepted_actions


def test_cross_station_reservations_and_effects_at_exact_boundaries(game_state):
    engine = construct(game_state, initial_engine_output=60)
    engine.start()
    for action in (EngineBoost(), SetShield(True, ShieldFacing.LEFT), RechargeShield(), Evade()):
        assert apply(engine, action).accepted
    before = engine.snapshot()
    assert before.ship.available_power(before.config) == 0
    assert apply(engine, ShieldBoost()).code == ActionCode.INSUFFICIENT_POWER
    assert apply(engine, SetEnginePower(59)).code == ActionCode.INSUFFICIENT_POWER
    assert engine.snapshot() is before
    ship = engine.tick().state.ship
    assert (ship.temperature, ship.shield_energy) == (306, 605)
    assert (
        ship.engine_boost_remaining_ticks,
        ship.recharge_remaining_ticks,
        ship.evade_remaining_ticks,
    ) == (19, 29, 9)
    ship = engine.tick(19).state.ship
    assert (ship.temperature, ship.shield_energy) == (420, 700)
    assert ship.engine_boost_remaining_ticks == 0 and ship.recharge_remaining_ticks == 10
    assert ship.available_power(before.config) == 25
    assert apply(engine, ShieldBoost()).accepted
    ship = engine.tick(10).state.ship
    assert (ship.temperature, ship.shield_energy) == (440, 950)
    assert ship.recharge_remaining_ticks == ship.shield_boost_remaining_ticks == 0
    assert (
        ship.cooldowns.engine_boost,
        ship.cooldowns.recharge_shield,
        ship.cooldowns.shield_boost,
    ) == (70, 30, 140)


@pytest.mark.parametrize(
    "action,duration,cooldown",
    [
        (Evade(), "evade_duration_ticks", "evade_cooldown_ticks"),
        (EngineBoost(), "engine_boost_duration_ticks", "engine_boost_cooldown_ticks"),
        (RechargeShield(), "recharge_duration_ticks", "recharge_cooldown_ticks"),
        (ShieldBoost(), "shield_boost_duration_ticks", "shield_boost_cooldown_ticks"),
    ],
)
def test_active_effect_cannot_stack_when_custom_cooldown_is_shorter(
    game_state, action, duration, cooldown
):
    engine = construct(game_state, initial_engine_output=100, **{duration: 3, cooldown: 1})
    engine.start()
    assert apply(engine, action).accepted
    engine.tick()
    before, trace = engine.snapshot(), engine.accepted_actions
    assert apply(engine, action).code == ActionCode.COOLDOWN
    assert engine.snapshot() is before and engine.accepted_actions == trace
    engine.tick(2)
    assert apply(engine, action).accepted


def test_shutdown_cancels_consumers_preserves_cooldowns_and_evade(game_state):
    engine = construct(game_state, initial_engine_output=100)
    engine.start()
    for action in (
        Evade(),
        EngineBoost(),
        RechargeShield(),
        ShieldBoost(),
        SetShield(True, ShieldFacing.RIGHT),
    ):
        assert apply(engine, action).accepted
    previous = engine.snapshot().ship
    assert apply(engine, EmergencyShutdown()).accepted
    ship = engine.snapshot().ship
    assert ship.engine_output == 0 and not ship.shield_active
    assert ship.engine_boost_remaining_ticks == ship.recharge_remaining_ticks == 0
    assert ship.shield_boost_remaining_ticks == 0
    assert ship.cooldowns == previous.cooldowns and ship.evade_remaining_ticks == 10
    assert ship.available_power(engine.snapshot().config) == 0
    assert engine.tick().state.ship.temperature == 299


def test_empty_shields_release_power_and_recharge_never_auto_activates(game_state):
    engine = construct(
        game_state, initial_shield_energy=1, initial_shield_active=True, initial_engine_output=15
    )
    engine.start()
    ship = engine.tick().state.ship
    assert ship.shield_energy == 0 and not ship.shield_active
    assert ship.available_power(engine.snapshot().config) == 15
    before = engine.snapshot()
    assert apply(engine, SetShield(True, ShieldFacing.LEFT)).code == ActionCode.INVALID_ACTION
    assert engine.snapshot() is before
    assert apply(engine, SetEnginePower(35)).accepted
    assert apply(engine, RechargeShield()).accepted
    ship = engine.tick().state.ship
    assert ship.shield_energy == 6 and not ship.shield_active
    assert apply(engine, SetShield(True, ShieldFacing.LEFT)).accepted
    assert engine.snapshot().ship.available_power(engine.snapshot().config) == 0


def test_combined_energy_update_clamps_once_and_zero_releases_after_effects(game_state):
    engine = construct(
        game_state, initial_shield_energy=999, initial_shield_active=True, initial_engine_output=100
    )
    engine.start()
    assert apply(engine, RechargeShield()).accepted
    assert engine.tick().state.ship.shield_energy == 1000
    engine = construct(
        game_state,
        initial_shield_energy=1,
        initial_shield_active=True,
        initial_engine_output=100,
        shield_drain_per_tick=7,
    )
    engine.start()
    assert apply(engine, RechargeShield()).accepted
    ship = engine.tick().state.ship
    assert ship.shield_energy == 0 and not ship.shield_active


def test_engine_boost_heat_clamps_then_damages_and_shutdown_keeps_cooldown(game_state):
    engine = construct(game_state, initial_temperature=999, initial_engine_output=40)
    engine.start()
    assert apply(engine, EngineBoost()).accepted
    ship = engine.tick().state.ship
    assert ship.temperature == 1000 and ship.hull == 995
    assert apply(engine, EmergencyShutdown()).accepted
    assert apply(engine, EngineBoost()).code == ActionCode.COOLDOWN
    ship = engine.tick().state.ship
    assert ship.temperature == 999 and ship.hull == 995


def test_full_catalog_trace_replays_without_rejected_requests_or_random_draws(game_state):
    engines = [construct(game_state, initial_engine_output=100) for _ in range(3)]
    for engine in engines:
        engine.start()
    rng = engines[0]._rng.getstate()
    requests = [(0, action) for action in ACTIONS[:5]] + [
        (1, SetShield(True, ShieldFacing.REAR)),
        (1, RechargeShield()),
        (2, SetEnginePower(100)),
        (2, ShieldBoost()),
        (3, EmergencyShutdown()),
        (4, SetEnginePower(100)),
        (5, EngineBoost()),
        (85, Evade()),
    ]
    for tick in range(100):
        for at, action in requests:
            if at != tick:
                continue
            one, two = (apply(engine, action) for engine in engines[:2])
            assert one == two
            if one.accepted:
                assert apply(engines[2], action).accepted
        assert engines[0].snapshot() == engines[1].snapshot() == engines[2].snapshot()
        for engine in engines:
            engine.tick()
    assert engines[0].accepted_actions == engines[1].accepted_actions == engines[2].accepted_actions
    assert engines[0]._rng.getstate() == rng
    assert {event.action.kind for event in engines[0].accepted_actions} == {
        action.kind for action in ACTIONS
    }
