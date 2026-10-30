"""Exact event rules, seed draws, last-tick timing and complete pure round replay."""

import json
from dataclasses import asdict, replace
from pathlib import Path
from random import Random

import pytest

from one_job.domain.actions import Coolant, EmergencyShutdown, Evade, SetEnginePower
from one_job.domain.config import GameConfig
from one_job.domain.emergencies import advance_emergencies
from one_job.domain.engine import GameEngine, RoundEnded
from one_job.domain.models import (
    AsteroidTarget,
    Emergency,
    OverheatingTarget,
    ShieldOverloadTarget,
    ShipState,
)
from one_job.domain.scheduler import EmergencyScheduler
from one_job.domain.types import EmergencyId, EmergencyType, Lane, ResultReason, Role, ShieldFacing


def event(target, *, deadline=10, progress=0, identity=1):
    return Emergency(EmergencyId(identity), target, 0, deadline, progress_ticks=progress)


ASTEROID = AsteroidTarget(Lane.CENTER, ShieldFacing.LEFT)


@pytest.mark.parametrize("ticks", [1, 9])
def test_asteroid_never_resolves_early(ticks):
    item = event(ASTEROID)
    ship = ShipState(engine_output=100, lane=Lane.LEFT)
    step = advance_emergencies(ship, (item,), ticks, GameConfig())
    assert step.active == (item,) and step.events == () and step.ship is ship


@pytest.mark.parametrize(
    "lane,output,evade,active,facing,energy,resolved,spent",
    [
        (Lane.LEFT, 60, 0, False, ShieldFacing.FRONT, 600, True, 0),
        (Lane.LEFT, 59, 0, False, ShieldFacing.FRONT, 600, False, 0),
        (Lane.CENTER, 0, 1, False, ShieldFacing.FRONT, 600, True, 0),
        (Lane.CENTER, 100, 0, False, ShieldFacing.LEFT, 600, False, 0),
        (Lane.CENTER, 40, 0, True, ShieldFacing.LEFT, 200, True, 200),
        (Lane.CENTER, 40, 0, True, ShieldFacing.LEFT, 199, False, 0),
        (Lane.CENTER, 40, 0, True, ShieldFacing.RIGHT, 600, False, 0),
        (Lane.LEFT, 60, 0, True, ShieldFacing.LEFT, 600, True, 0),
        (Lane.CENTER, 40, 1, True, ShieldFacing.LEFT, 600, True, 0),
    ],
)
def test_asteroid_deadline_paths_and_maneuver_precedence(
    lane, output, evade, active, facing, energy, resolved, spent
):
    ship = ShipState(
        lane=lane,
        engine_output=output,
        evade_remaining_ticks=evade,
        shield_active=active,
        shield_facing=facing,
        shield_energy=energy,
    )
    step = advance_emergencies(ship, (event(ASTEROID),), 10, GameConfig())
    assert not step.active
    assert step.events[0].status == ("resolved" if resolved else "failed")
    assert step.ship.hull == (1000 if resolved else 750)
    assert step.ship.shield_energy == energy - spent
    if spent == energy:
        assert not step.ship.shield_active
    assert advance_emergencies(step.ship, step.active, 11, GameConfig()).events == ()


@pytest.mark.parametrize(
    "temperature,output,resolved", [(550, 50, True), (551, 50, False), (550, 51, False)]
)
def test_overheat_success_precedes_same_tick_timeout_and_failure_resets(
    temperature, output, resolved
):
    ship = ShipState(temperature=temperature, engine_output=output)
    step = advance_emergencies(ship, (event(OverheatingTarget()),), 10, GameConfig())
    assert step.events[0].status == ("resolved" if resolved else "failed")
    assert step.ship.temperature == (temperature if resolved else 650)
    assert step.ship.hull == (1000 if resolved else 800)


def test_overheat_can_resolve_early_but_wrong_output_is_not_success():
    item = event(OverheatingTarget())
    ship = ShipState(temperature=550, engine_output=51)
    assert advance_emergencies(ship, (item,), 1, GameConfig()).active == (item,)
    assert (
        advance_emergencies(replace(ship, engine_output=50), (item,), 1, GameConfig())
        .events[0]
        .status
        == "resolved"
    )


def test_overload_progress_requires_consecutive_conditions_and_success_wins_deadline():
    item = event(ShieldOverloadTarget(45, 3), deadline=7)
    ship = ShipState(engine_output=45)
    step = advance_emergencies(ship, (item,), 1, GameConfig())
    assert step.active[0].progress_ticks == 1
    step = advance_emergencies(ship, step.active, 2, GameConfig())
    assert step.active[0].progress_ticks == 2
    step = advance_emergencies(replace(ship, shield_active=True), step.active, 3, GameConfig())
    assert step.active[0].progress_ticks == 0
    step = advance_emergencies(replace(ship, engine_output=46), step.active, 4, GameConfig())
    assert step.active[0].progress_ticks == 0
    for tick in (5, 6):
        step = advance_emergencies(ship, step.active, tick, GameConfig())
    step = advance_emergencies(ship, step.active, 7, GameConfig())
    assert not step.active and step.events[0].status == "resolved" and step.ship.hull == 1000


def test_overload_failure_empty_energy_and_damage_clamp():
    ship = ShipState(hull=10, shield_active=True)
    step = advance_emergencies(
        ship, (event(ShieldOverloadTarget(), deadline=20),), 20, GameConfig()
    )
    assert step.events[0].status == "failed"
    assert (step.ship.hull, step.ship.shield_energy, step.ship.shield_active) == (0, 0, False)


def test_simultaneous_events_use_id_order_not_input_order():
    # Earlier overload empties shields, so the later asteroid cannot absorb.
    overload = event(ShieldOverloadTarget(), identity=1, deadline=20)
    asteroid = event(ASTEROID, identity=2, deadline=20)
    ship = ShipState(shield_active=True, shield_facing=ShieldFacing.LEFT)
    step = advance_emergencies(ship, (asteroid, overload), 20, GameConfig())
    assert [e.emergency_id for e in step.events] == [1, 2]
    assert [e.status for e in step.events] == ["failed", "failed"]
    assert step.ship.hull == 650
    inverse = advance_emergencies(
        ship,
        (
            replace(asteroid, emergency_id=EmergencyId(1)),
            replace(overload, emergency_id=EmergencyId(2)),
        ),
        20,
        GameConfig(),
    )
    assert [e.status for e in inverse.events] == ["resolved", "failed"]
    assert inverse.ship.hull == 900


class CountingRandom(Random):
    def __init__(self, seed):
        super().__init__(seed)
        self.calls = []

    def choice(self, seq):
        self.calls.append(("choice", tuple(seq)))
        return super().choice(seq)

    def randint(self, a, b):
        self.calls.append(("interval", a, b))
        return super().randint(a, b)


def test_slot_starts_at_80_and_threshold_does_not_draw_randomness():
    rng = CountingRandom(7)
    scheduler = EmergencyScheduler(GameConfig(), rng)
    hot = ShipState(temperature=800)
    active, events = scheduler.start_due(1, hot, ())
    assert [e.kind for e in events] == [EmergencyType.OVERHEATING] and rng.calls == []
    for tick in range(2, 80):
        active, events = scheduler.start_due(tick, hot, active)
        assert not events
    active, events = scheduler.start_due(80, hot, active)
    assert len(active) == 2 and len(events) == 1 and rng.calls[0][0] == "choice"
    assert rng.calls[-1] == ("interval", 80, 120)
    assert [e.emergency_id for e in active] == [1, 2]


@pytest.mark.parametrize(
    "tick,expected", [(299, (80, 120)), (300, (60, 100)), (599, (60, 100)), (600, (40, 80))]
)
def test_schedule_thirds_and_skip_full_capacity_without_per_tick_retry(tick, expected):
    cfg = GameConfig(first_emergency_tick=tick, max_active_emergencies=1)
    rng = CountingRandom(1)
    scheduler = EmergencyScheduler(cfg, rng)
    occupied = (Emergency(EmergencyId(100), ASTEROID, tick, tick + 80),)
    active, events = scheduler.start_due(tick, ShipState(), occupied)
    assert active == occupied and events == ()
    assert rng.calls == [("interval", *expected)]
    assert scheduler.start_due(tick + 1, ShipState(), ())[1] == ()
    assert len(rng.calls) == 1


def test_hot_event_waits_for_capacity_then_has_priority_and_does_not_duplicate():
    cfg = GameConfig(first_emergency_tick=1, max_active_emergencies=1)
    rng = CountingRandom(2)
    scheduler = EmergencyScheduler(cfg, rng)
    hot = ShipState(temperature=800)
    occupied = (event(ASTEROID),)
    assert scheduler.start_due(1, hot, occupied)[1] == ()
    calls = list(rng.calls)
    active, events = scheduler.start_due(2, hot, ())
    assert [e.kind for e in events] == [EmergencyType.OVERHEATING]
    assert scheduler.start_due(3, hot, active)[1] == () and rng.calls == calls
    rng2 = CountingRandom(2)
    active, events = EmergencyScheduler(cfg, rng2).start_due(1, hot, ())
    assert [e.kind for e in events] == [EmergencyType.OVERHEATING]
    assert rng2.calls == [("interval", 80, 120)]


def test_scheduled_choice_excludes_existing_kind_and_obeys_cap():
    scheduler = EmergencyScheduler(GameConfig(first_emergency_tick=1), Random(1))
    active, events = scheduler.start_due(1, ShipState(), (event(ASTEROID, identity=100),))
    assert len(active) == 2 and events[0].kind == EmergencyType.SHIELD_OVERLOAD
    assert len({e.kind for e in active}) == 2


def make_engine(state, seed=7, **changes):
    return GameEngine(
        replace(state.config, **changes),
        seed,
        state.players,
        state.assignments,
        round_id=state.round.round_id,
    )


def test_last_evade_tick_protects_then_ages_and_pause_freezes_schedule(game_state):
    cfg = dict(first_emergency_tick=1, asteroid_deadline_ticks=10)
    engine = make_engine(game_state, seed=1, **cfg)
    engine.start()
    # Seed 1 chooses asteroid. Its private target is deliberately matched.
    step = engine.tick()
    asteroid = step.state.emergencies[0]
    assert asteroid.kind == EmergencyType.ASTEROID
    engineer = game_state.assignments.owners[Role.ENGINEER]
    pilot = game_state.assignments.owners[Role.PILOT]
    engine.apply_action(engineer, SetEnginePower(60))
    engine.apply_action(pilot, Evade())
    engine.apply_action(engineer, EmergencyShutdown())
    before = engine.pause()
    random_state = engine._rng.getstate()
    assert engine.tick(100).state is before and engine._rng.getstate() == random_state
    engine.resume()
    step = engine.tick(10)
    assert step.events[-1].status == "resolved" and step.state.ship.hull == 1000
    assert step.state.ship.evade_remaining_ticks == 0 and not step.state.emergencies


def test_complete_seeded_round_and_accepted_only_replay(game_state):
    original = make_engine(game_state, seed=71)
    original.start()
    original.apply_action(game_state.assignments.owners[Role.ENGINEER], SetEnginePower(60))
    events = []
    snapshots = []
    while original.snapshot().round.result is None:
        state = original.snapshot()
        if any(e.kind == EmergencyType.OVERHEATING for e in state.emergencies):
            original.apply_action(state.assignments.owners[Role.ENGINEER], SetEnginePower(40))
            original.apply_action(state.assignments.owners[Role.ENGINEER], Coolant())
        snapshots.append(original.snapshot())
        events.extend(original.tick().events)
    final = original.snapshot()
    replay = make_engine(game_state, seed=71)
    replay.start()
    replay_events = []
    for snapshot in snapshots:
        for record in original.accepted_actions:
            if record.tick_index == replay.snapshot().tick_index:
                assert replay.apply_action(record.actor_id, record.action).accepted
        assert replay.snapshot() == snapshot
        replay_events.extend(replay.tick().events)
    assert replay.snapshot() == final and replay_events == events
    assert sum(isinstance(e, RoundEnded) for e in events) == 1
    changes = [e for e in events if not isinstance(e, RoundEnded)]
    fixture = json.loads(
        (Path(__file__).parents[1] / "fixtures/engine/emergency-seed71.json").read_text()
    )
    assert [asdict(e) for e in changes] == fixture["events"]
    assert json.loads(json.dumps(asdict(final.round.result), default=str)) == fixture["result"]
    assert final.round.result.resolved_count == sum(e.status == "resolved" for e in changes)
    assert final.round.result.failed_count == sum(e.status == "failed" for e in changes)
    assert final.round.result.resolved_count > 0 and final.round.result.failed_count > 0
    before = final
    rng = original._rng.getstate()
    assert original.tick(100).state is before and original.tick().events == ()
    assert original._rng.getstate() == rng and final.emergencies == ()


def test_abort_preserves_completed_counts_and_clears_active(game_state):
    engine = make_engine(game_state, seed=7, first_emergency_tick=1)
    engine.start()
    engine.tick(21)
    assert engine.snapshot().emergencies == ()
    ended = engine.abort(ResultReason.PLAYER_LEFT)
    assert ended.round.result.resolved_count == 1 and ended.round.result.failed_count == 0
    assert engine.tick(100).state is ended


@pytest.mark.parametrize("temperature,started", [(799, False), (800, True)])
def test_threshold_is_inclusive_without_random_draws(temperature, started):
    rng = CountingRandom(1)
    scheduler = EmergencyScheduler(GameConfig(), rng)
    active, events = scheduler.start_due(1, ShipState(temperature=temperature), ())
    assert bool(active) == started and bool(events) == started and rng.calls == []


def test_emergency_hull_loss_wins_timer_tie_and_no_terminal_spawn(game_state):
    engine = make_engine(
        game_state, seed=1, round_duration_ms=60_000, initial_hull=250, first_emergency_tick=520
    )
    engine.start()
    update = engine.tick(600)
    assert update.state.tick_index == 600 and update.state.round.result.outcome == "defeat"
    assert update.state.round.result.failed_count == 1 and update.state.ship.hull == 0
    assert not update.state.emergencies and isinstance(update.events[-1], RoundEnded)
    assert not any(
        e.tick_index == 600 and e.status == "started"
        for e in update.events
        if not isinstance(e, RoundEnded)
    )


def test_shield_absorption_uses_post_drain_energy_and_releases_power(game_state):
    from one_job.domain.actions import SetShield

    engine = make_engine(
        game_state,
        seed=1,
        first_emergency_tick=1,
        asteroid_deadline_ticks=1,
        initial_shield_active=True,
        initial_shield_energy=202,
    )
    engine.start()
    asteroid = engine.tick().state.emergencies[0]
    assert asteroid.kind == "asteroid"
    engine.apply_action(
        game_state.assignments.owners[Role.SHIELDS],
        SetShield(True, asteroid.target.required_facing),
    )
    update = engine.tick()
    assert (update.state.ship.shield_energy, update.state.ship.shield_active) == (0, False)
    assert update.state.ship.available_power(update.state.config) == 40
    assert update.events[0].status == "resolved" and update.state.ship.hull == 1000


def test_abort_drops_unfinished_events_without_counting_failure(game_state):
    engine = make_engine(game_state, first_emergency_tick=1)
    engine.start()
    engine.tick()
    assert engine.snapshot().emergencies
    ended = engine.abort(ResultReason.PLAYER_LEFT)
    assert ended.emergencies == () and ended.round.result.failed_count == 0
    assert engine.tick().events == ()
