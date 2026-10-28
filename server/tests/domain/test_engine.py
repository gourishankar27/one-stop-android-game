import random
from dataclasses import FrozenInstanceError, replace
from uuid import UUID

import pytest

from one_job.domain import GameConfig, GameEngine, GameState, PlayerId, Role, RoleAssignment
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
from one_job.domain.engine import ActionCode, ActionResult
from one_job.domain.types import Lane, MoveDirection, Outcome, RoundId, RoundStage, ShieldFacing


def make_engine(state: GameState, config: GameConfig | None = None) -> GameEngine:
    return GameEngine(
        config or state.config,
        12345,
        state.players,
        state.assignments,
        round_id=state.round.round_id,
    )


@pytest.fixture
def engine(game_state: GameState) -> GameEngine:
    return make_engine(game_state)


def test_start_and_prestart_validation(engine: GameEngine) -> None:
    before = engine.snapshot()
    assert before.round.stage == RoundStage.BRIEFING and before.tick_index == 0
    assert (
        engine.apply_action(before.assignments.owners[Role.ENGINEER], Coolant()).code
        == ActionCode.INVALID_STAGE
    )
    with pytest.raises(ValueError):
        engine.tick()
    assert engine.snapshot() is before and engine.accepted_actions == ()
    running = engine.start()
    assert running.round.stage == RoundStage.RUNNING and running.tick_index == 0
    with pytest.raises(ValueError):
        engine.start()
    assert engine.snapshot() is running


def test_default_round_wins_at_exactly_900_ticks(engine: GameEngine) -> None:
    engine.start()
    update = engine.tick(899)
    assert update.events == () and update.state.round.remaining_ms == 100
    assert update.state.ship.hull == 1000 and update.state.ship.temperature == 0
    terminal = engine.tick()
    assert terminal.state.tick_index == 900 and terminal.state.elapsed_ms == 90_000
    assert terminal.state.round.stage == RoundStage.FINISHED
    assert terminal.state.round.result.outcome == Outcome.VICTORY
    assert len(terminal.events) == 1 and terminal.events[0].result == terminal.state.round.result
    assert terminal.state.emergencies == ()


@pytest.mark.parametrize("duration", [60_000, 120_000])
def test_duration_and_batch_overshoot(game_state: GameState, duration: int) -> None:
    engine = make_engine(game_state, replace(game_state.config, round_duration_ms=duration))
    engine.start()
    update = engine.tick(duration // 100 + 50)
    assert update.state.elapsed_ms == duration and len(update.events) == 1
    assert update.state.round.result.outcome == Outcome.VICTORY


@pytest.mark.parametrize(
    "steps", [0, -1, True, False, 1.0, 0.1, float("nan"), float("inf"), "1", None]
)
def test_invalid_steps_are_atomic(engine: GameEngine, steps: object) -> None:
    before = engine.start()
    with pytest.raises(ValueError):
        engine.tick(steps)
    assert engine.snapshot() is before and engine.accepted_actions == ()


def test_batch_matches_single_steps_without_delta_api(game_state: GameState) -> None:
    one, batch = make_engine(game_state), make_engine(game_state)
    one.start()
    batch.start()
    with pytest.raises(TypeError):
        one.tick(delta_ms=100)
    for _ in range(125):
        one.tick()
    assert one.snapshot() == batch.tick(125).state


@pytest.mark.parametrize(("output", "heat"), [(0, 299), (59, 299), (60, 302), (100, 302)])
def test_heat_uses_accepted_output_before_effects(
    engine: GameEngine, output: int, heat: int
) -> None:
    state = engine.start()
    assert engine.apply_action(
        state.assignments.owners[Role.ENGINEER], SetEnginePower(output)
    ).accepted
    assert engine.tick().state.ship.temperature == heat


def test_critical_heat_defeat_and_clamping(game_state: GameState) -> None:
    engine = make_engine(
        game_state,
        replace(
            game_state.config, initial_temperature=999, initial_engine_output=60, initial_hull=11
        ),
    )
    engine.start()
    assert engine.tick().state.ship.hull == 6
    assert engine.tick().state.ship.hull == 1
    ended = engine.tick(100)
    assert (ended.state.tick_index, ended.state.ship.hull, ended.state.ship.temperature) == (
        3,
        0,
        1000,
    )
    assert ended.state.round.result.outcome == Outcome.DEFEAT and len(ended.events) == 1


def test_cooling_before_damage_and_zero_clamp(game_state: GameState) -> None:
    engine = make_engine(
        game_state, replace(game_state.config, initial_temperature=1000, cooling_per_tick=1000)
    )
    engine.start()
    state = engine.tick().state
    assert state.ship.temperature == 0 and state.ship.hull == 1000
    assert engine.tick().state.ship.temperature == 0


def test_hull_loss_wins_timer_tie(game_state: GameState) -> None:
    config = replace(
        game_state.config,
        round_duration_ms=60_000,
        initial_hull=600,
        initial_engine_output=60,
        initial_temperature=1000,
        critical_heat_hull_damage=1,
    )
    engine = make_engine(game_state, config)
    engine.start()
    assert engine.tick(599).state.ship.hull == 1
    terminal = engine.tick()
    assert terminal.state.round.remaining_ms == 0 and terminal.state.ship.hull == 0
    assert terminal.state.round.result.outcome == Outcome.DEFEAT


@pytest.mark.parametrize("defeat", [False, True])
def test_terminal_idempotence(game_state: GameState, defeat: bool) -> None:
    config = (
        replace(
            game_state.config, initial_hull=1, initial_temperature=1000, initial_engine_output=60
        )
        if defeat
        else game_state.config
    )
    engine = make_engine(game_state, config)
    engine.start()
    terminal = engine.tick(2000)
    assert len(terminal.events) == 1
    for _ in range(3):
        later = engine.tick(2000)
        assert later.state is terminal.state and later.events == ()
        for action in (SetEnginePower(0), MoveLane(MoveDirection.LEFT), Coolant()):
            assert (
                engine.apply_action(terminal.state.assignments.owners[action.role], action).code
                == ActionCode.INVALID_STAGE
            )
    with pytest.raises(ValueError):
        engine.start()
    assert engine.snapshot() is terminal.state and engine.accepted_actions == ()


@pytest.mark.parametrize("action", [SetEnginePower(60), MoveLane(MoveDirection.LEFT), Coolant()])
def test_ownership(engine: GameEngine, action: PlayerAction) -> None:
    state = engine.start()
    owner = state.assignments.owners[action.role]
    for player in state.players:
        if player.player_id != owner:
            assert engine.apply_action(player.player_id, action).code == ActionCode.NOT_ROLE_OWNER
            assert engine.snapshot() is state and engine.accepted_actions == ()
    result = engine.apply_action(owner, action)
    assert result.accepted and result.code == ActionCode.ACCEPTED and len(result.events) == 1


@pytest.mark.parametrize("actor", [PlayerId(UUID(int=999)), "claimed-id", True, None])
def test_unknown_actor(engine: GameEngine, actor: object) -> None:
    state = engine.start()
    assert engine.apply_action(actor, Coolant()).code == ActionCode.NOT_PARTICIPANT
    assert engine.snapshot() is state and engine.accepted_actions == ()


@pytest.mark.parametrize("action", [None, {}, "coolant", 1])
def test_unknown_action(engine: GameEngine, action: object) -> None:
    state = engine.start()
    assert engine.apply_action(state.players[0].player_id, action).code == ActionCode.INVALID_ACTION
    assert engine.snapshot() is state and engine.accepted_actions == ()


@pytest.mark.parametrize("value", [-1, 101, True, 1.0, float("nan"), float("inf"), "60"])
def test_revalidate_action_before_changes(engine: GameEngine, value: object) -> None:
    state = engine.start()
    action = SetEnginePower(40)
    object.__setattr__(action, "value", value)
    assert (
        engine.apply_action(state.assignments.owners[Role.ENGINEER], action).code
        == ActionCode.INVALID_ACTION
    )
    assert engine.snapshot() is state and engine.accepted_actions == ()


@pytest.mark.parametrize("direction", ["left", "up", True, None])
def test_revalidate_lane_direction_before_changes(engine: GameEngine, direction: object) -> None:
    state = engine.start()
    action = MoveLane(MoveDirection.LEFT)
    object.__setattr__(action, "direction", direction)
    result = engine.apply_action(state.assignments.owners[Role.PILOT], action)
    assert result.code == ActionCode.INVALID_ACTION and result.events == ()
    assert engine.snapshot() is state and engine.accepted_actions == ()


def test_lane_steps_edges_and_exact_cooldown(engine: GameEngine) -> None:
    actor = engine.start().assignments.owners[Role.PILOT]
    left, right = MoveLane(MoveDirection.LEFT), MoveLane(MoveDirection.RIGHT)
    assert engine.apply_action(actor, left).accepted
    assert (
        engine.snapshot().ship.lane == Lane.LEFT and engine.snapshot().ship.cooldowns.move_lane == 2
    )
    assert engine.apply_action(actor, right).code == ActionCode.COOLDOWN
    engine.tick()
    assert engine.apply_action(actor, right).code == ActionCode.COOLDOWN
    engine.tick()
    before = engine.snapshot()
    assert engine.apply_action(actor, left).code == ActionCode.LANE_BOUNDARY
    assert engine.snapshot() is before
    assert engine.apply_action(actor, right).accepted
    engine.tick(2)
    assert engine.apply_action(actor, right).accepted
    engine.tick(2)
    assert engine.snapshot().ship.lane == Lane.RIGHT
    assert engine.apply_action(actor, right).code == ActionCode.LANE_BOUNDARY


def test_coolant_clamp_and_cooldown_boundary(engine: GameEngine) -> None:
    actor = engine.start().assignments.owners[Role.ENGINEER]
    assert engine.apply_action(actor, SetEnginePower(60)).accepted
    assert engine.apply_action(actor, Coolant()).accepted
    assert (
        engine.snapshot().ship.temperature == 100 and engine.snapshot().ship.cooldowns.coolant == 30
    )
    assert engine.tick(29).state.ship.temperature == 158
    before = engine.snapshot()
    assert engine.apply_action(actor, Coolant()).code == ActionCode.COOLDOWN
    assert engine.snapshot() is before
    engine.tick()
    assert engine.apply_action(actor, Coolant()).accepted
    assert engine.snapshot().ship.temperature == 0
    assert engine.tick().state.ship.temperature == 2


def test_coolant_precedes_critical_damage(game_state: GameState) -> None:
    engine = make_engine(
        game_state, replace(game_state.config, initial_temperature=1000, initial_engine_output=60)
    )
    assert engine.apply_action(engine.start().assignments.owners[Role.ENGINEER], Coolant()).accepted
    assert engine.tick().state.ship.hull == 1000


def test_existing_power_reservation_validation(game_state: GameState) -> None:
    engine = make_engine(game_state, replace(game_state.config, initial_shield_active=True))
    state = engine.start()
    actor = state.assignments.owners[Role.ENGINEER]
    assert engine.apply_action(actor, SetEnginePower(14)).code == ActionCode.INSUFFICIENT_POWER
    assert engine.snapshot() is state and engine.accepted_actions == ()
    assert engine.apply_action(actor, SetEnginePower(15)).accepted
    assert engine.snapshot().ship.available_power(state.config) == 0


@pytest.mark.parametrize(
    "action",
    [
        Evade(),
        EngineBoost(),
        EmergencyShutdown(),
        SetShield(True, ShieldFacing.LEFT),
        RechargeShield(),
        ShieldBoost(),
    ],
)
def test_future_actions_are_unavailable(engine: GameEngine, action: PlayerAction) -> None:
    state = engine.start()
    result = engine.apply_action(state.assignments.owners[action.role], action)
    assert (
        result.code == ActionCode.FEATURE_UNAVAILABLE
        and not result.accepted
        and result.events == ()
    )
    assert engine.snapshot() is state and engine.accepted_actions == ()


def test_order_and_immutable_action_trace(engine: GameEngine) -> None:
    state = engine.start()
    actor = state.assignments.owners[Role.ENGINEER]
    action = SetEnginePower(60)
    first = engine.apply_action(actor, action)
    old_trace = engine.accepted_actions
    assert (
        engine.apply_action(state.assignments.owners[Role.PILOT], Coolant()).code
        == ActionCode.NOT_ROLE_OWNER
    )
    second = engine.apply_action(actor, SetEnginePower(40))
    assert [(item.tick_index, item.order) for item in engine.accepted_actions] == [(0, 1), (0, 2)]
    assert first.events + second.events == engine.accepted_actions and old_trace == first.events
    assert engine.tick().state.ship.temperature == 299
    object.__setattr__(action, "value", 0)
    assert old_trace[0].action.value == 60


def test_snapshot_and_roster_isolation(game_state: GameState) -> None:
    incoming = list(game_state.players)
    engine = GameEngine(
        game_state.config, 123, incoming, game_state.assignments, round_id=game_state.round.round_id
    )
    before = engine.snapshot()
    incoming.clear()
    engine.start()
    with pytest.raises(AttributeError):
        engine.players = ()
    with pytest.raises(FrozenInstanceError):
        before.ship.hull = 0
    with pytest.raises(TypeError):
        before.assignments.owners[Role.PILOT] = before.players[1].player_id
    assert engine.tick().state.ship.temperature == 299 and before.ship.temperature == 300
    assert len(engine.snapshot().players) == 3


@pytest.mark.parametrize("seed", [True, 1.0, "123", None])
def test_invalid_seed(game_state: GameState, seed: object) -> None:
    with pytest.raises(ValueError):
        GameEngine(
            game_state.config,
            seed,
            game_state.players,
            game_state.assignments,
            round_id=game_state.round.round_id,
        )


def test_invalid_roster_or_round_id(game_state: GameState) -> None:
    for players in ((), game_state.players[:1], (game_state.players[0],) * 3):
        with pytest.raises(ValueError):
            GameEngine(
                game_state.config,
                1,
                players,
                game_state.assignments,
                round_id=game_state.round.round_id,
            )
    with pytest.raises(ValueError):
        GameEngine(
            game_state.config, 1, game_state.players, game_state.assignments, round_id="bad-id"
        )


def test_two_player_ownership(game_state: GameState) -> None:
    players = game_state.players[:2]
    ids = tuple(player.player_id for player in players)
    roles = RoleAssignment(ids, {Role.PILOT: ids[0], Role.ENGINEER: ids[1], Role.SHIELDS: ids[1]})
    engine = GameEngine(game_state.config, -42, players, roles, round_id=RoundId(UUID(int=99)))
    engine.start()
    assert engine.apply_action(ids[0], MoveLane(MoveDirection.RIGHT)).accepted
    assert engine.apply_action(ids[1], SetEnginePower(60)).accepted
    assert engine.apply_action(ids[1], Coolant()).accepted
    assert engine.apply_action(ids[0], Coolant()).code == ActionCode.NOT_ROLE_OWNER


def test_private_rng_and_global_random_are_not_consumed(
    game_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[random.Random] = []

    def seeded(seed: int) -> random.Random:
        assert seed == 12345
        rng = random.Random(seed)
        captured.append(rng)
        return rng

    monkeypatch.setattr("one_job.domain.engine.Random", seeded)
    global_before = random.getstate()
    engine = make_engine(game_state)
    rng_before = captured[0].getstate()
    actor = engine.start().assignments.owners[Role.ENGINEER]
    engine.apply_action(actor, Coolant())
    engine.apply_action(actor, Coolant())
    engine.apply_action(actor, EngineBoost())
    engine.tick(900)
    assert captured[0].getstate() == rng_before and random.getstate() == global_before
    assert len(captured) == 1


def test_action_result_requires_an_acceptance_event() -> None:
    with pytest.raises(ValueError):
        ActionResult(ActionCode.ACCEPTED)
