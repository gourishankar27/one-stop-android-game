from dataclasses import FrozenInstanceError, replace
from uuid import UUID

import pytest

from one_job.domain import GameConfig, GameState, Player, PlayerId, Role, RoleAssignment
from one_job.domain.models import (
    AsteroidTarget,
    Cooldowns,
    Emergency,
    GameResult,
    RoundState,
    ShipState,
)
from one_job.domain.types import (
    EmergencyId,
    Lane,
    Outcome,
    ResultReason,
    RoundId,
    RoundStage,
    ShieldFacing,
)


def test_three_players_own_exactly_one_station(game_state: GameState) -> None:
    for role, player in zip(Role, game_state.players, strict=True):
        assert game_state.assignments.roles_for(player.player_id) == (role,)


@pytest.mark.parametrize("pilot_index", [0, 1])
def test_two_players_split_pilot_and_engineer_shields(
    players: tuple[Player, ...],
    pilot_index: int,
) -> None:
    ids = tuple(player.player_id for player in players[:2])
    pilot, systems = ids[pilot_index], ids[1 - pilot_index]
    assignment = RoleAssignment(
        ids, {Role.PILOT: pilot, Role.ENGINEER: systems, Role.SHIELDS: systems}
    )
    state = GameState(
        GameConfig(), players[:2], assignment, ShipState(), RoundState(RoundId(UUID(int=9)))
    )
    assert state.assignments.roles_for(pilot) == (Role.PILOT,)
    assert state.assignments.roles_for(systems) == (Role.ENGINEER, Role.SHIELDS)


@pytest.mark.parametrize("roster_size", [0, 1, 4])
def test_assignment_rejects_unsupported_rosters(roster_size: int) -> None:
    ids = tuple(PlayerId(UUID(int=index)) for index in range(roster_size))
    with pytest.raises(ValueError):
        RoleAssignment(ids, {})


def test_assignment_rejects_duplicate_foreign_missing_and_invalid_owners(
    game_state: GameState,
) -> None:
    ids = game_state.assignments.player_ids
    owners = dict(game_state.assignments.owners)
    invalid = [
        (ids + (ids[0],), owners),
        (ids, {Role.PILOT: ids[0], Role.ENGINEER: ids[1]}),
        (ids, {**owners, Role.SHIELDS: PlayerId(UUID(int=999))}),
        (ids, {**owners, Role.SHIELDS: ids[1]}),
        (ids, {**owners, "observer": ids[0]}),
        (ids, {**owners, Role.PILOT: str(ids[0])}),
        (ids[:2], {Role.PILOT: ids[0], Role.ENGINEER: ids[0], Role.SHIELDS: ids[1]}),
        (ids[:2], {Role.PILOT: ids[0], Role.ENGINEER: ids[1], Role.SHIELDS: ids[0]}),
        ((str(ids[0]), ids[1]), owners),
    ]
    for roster, mapping in invalid:
        with pytest.raises(ValueError):
            RoleAssignment(roster, mapping)
    with pytest.raises(ValueError):
        game_state.assignments.roles_for(PlayerId(UUID(int=999)))
    with pytest.raises(ValueError):
        RoleAssignment(ids, {str(role): owner for role, owner in owners.items()})


@pytest.mark.parametrize("name", ["a", "x" * 20, "  Crew  ", "🚀船員", "duplicate"])
def test_player_names_are_trimmed_unicode_values(name: str) -> None:
    assert Player(PlayerId(UUID(int=1)), name).name == name.strip()


@pytest.mark.parametrize(
    "name", ["", "   ", "x" * 21, "a\x00b", "a\nb", "\tCrew", "a\x7fb", 1, None]
)
def test_invalid_player_names_are_rejected(name: object) -> None:
    with pytest.raises(ValueError):
        Player(PlayerId(UUID(int=1)), name)


@pytest.mark.parametrize("identifier", ["not-a-uuid", str(UUID(int=1)), 1, True, None])
def test_identifiers_require_uuid_values(identifier: object) -> None:
    with pytest.raises(ValueError):
        Player(identifier, "Crew")
    with pytest.raises(ValueError):
        RoundState(identifier)


def test_duplicate_names_do_not_change_identity(players: tuple[Player, ...]) -> None:
    renamed = tuple(replace(player, name="Crew") for player in players)
    assert len({player.player_id for player in renamed}) == 3


@pytest.mark.parametrize(
    ("name", "maximum"),
    [("hull", 1000), ("shield_energy", 1000), ("temperature", 1000), ("engine_output", 100)],
)
def test_ship_resource_boundaries(name: str, maximum: int) -> None:
    for value in (0, maximum):
        assert getattr(ShipState(**{name: value}), name) == value
    for value in (-1, maximum + 1, True, 0.0, float("nan"), float("inf"), "0"):
        with pytest.raises(ValueError):
            ShipState(**{name: value})


@pytest.mark.parametrize(
    "changes",
    [
        {"lane": "center"},
        {"shield_facing": "front"},
        {"shield_active": 1},
        {"shield_active": True, "shield_energy": 0},
        {"cooldowns": {}},
        {"evade_remaining_ticks": -1},
        {"engine_boost_remaining_ticks": True},
        {"recharge_remaining_ticks": 0.5},
        {"shield_boost_remaining_ticks": "1"},
    ],
)
def test_ship_rejects_invalid_station_state(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ShipState(**changes)


@pytest.mark.parametrize(
    "name", ["move_lane", "evade", "engine_boost", "coolant", "recharge_shield", "shield_boost"]
)
def test_cooldowns_require_nonnegative_integer_ticks(name: str) -> None:
    assert getattr(Cooldowns(**{name: 1}), name) == 1
    for value in (-1, True, 1.0, "1"):
        with pytest.raises(ValueError):
            Cooldowns(**{name: value})


def test_power_is_derived_from_configuration_and_active_reservations(game_state: GameState) -> None:
    config = replace(game_state.config, shield_hold_power_cost=10, engine_boost_power_cost=20)
    ship = replace(
        game_state.ship,
        engine_output=100,
        shield_active=True,
        engine_boost_remaining_ticks=1,
        recharge_remaining_ticks=1,
        shield_boost_remaining_ticks=1,
    )
    assert ship.available_power(config) == 25
    assert replace(game_state, config=config, ship=ship).ship == ship
    with pytest.raises(ValueError):
        replace(game_state, ship=replace(ship, engine_output=1))


@pytest.mark.parametrize(
    "changes",
    [
        {"evade_remaining_ticks": 11},
        {"engine_boost_remaining_ticks": 21},
        {"recharge_remaining_ticks": 31},
        {"shield_boost_remaining_ticks": 11},
        {"cooldowns": Cooldowns(move_lane=3)},
        {"cooldowns": Cooldowns(coolant=31)},
        {"cooldowns": Cooldowns(evade=81)},
        {"cooldowns": Cooldowns(engine_boost=101)},
        {"cooldowns": Cooldowns(recharge_shield=61)},
        {"cooldowns": Cooldowns(shield_boost=151)},
    ],
)
def test_snapshot_bounds_effects_and_cooldowns_by_config(
    game_state: GameState,
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        replace(game_state, ship=replace(game_state.ship, **changes))


def test_result_and_snapshot_participants_are_consistent(game_state: GameState) -> None:
    with pytest.raises(ValueError):
        replace(game_state, players=game_state.players[:2])
    with pytest.raises(ValueError):
        replace(game_state, players=(game_state.players[0],) * 3)
    with pytest.raises(ValueError):
        replace(game_state, round=replace(game_state.round, duration_ms=60_000))
    with pytest.raises(ValueError):
        replace(game_state, ship=replace(game_state.ship, hull=0))
    result = GameResult(Outcome.DEFEAT, ResultReason.HULL_DESTROYED, 100, 0, game_state.players)
    round_state = replace(game_state.round, stage=RoundStage.FINISHED, tick_index=1, result=result)
    with pytest.raises(ValueError):
        replace(game_state, round=round_state)
    with pytest.raises(ValueError):
        replace(
            game_state,
            ship=replace(game_state.ship, hull=0),
            round=replace(round_state, result=replace(result, players=game_state.players[:2])),
        )
    state = replace(game_state, round=round_state, ship=replace(game_state.ship, hull=0))
    assert state.round.result == result and state.elapsed_ms == 100


@pytest.mark.parametrize(
    "changes",
    [
        {"config": {}},
        {"assignments": None},
        {"ship": {}},
        {"round": None},
        {"players": "crew"},
        {"players": [None, None]},
        {"emergencies": [{}]},
    ],
)
def test_snapshot_requires_typed_components(
    game_state: GameState, changes: dict[str, object]
) -> None:
    with pytest.raises(ValueError):
        replace(game_state, **changes)


def test_nested_snapshots_defensively_copy_mutable_constructor_inputs(
    game_state: GameState,
) -> None:
    players = list(game_state.players)
    owners = dict(game_state.assignments.owners)
    roster = list(game_state.assignments.player_ids)
    target = AsteroidTarget(Lane.LEFT, ShieldFacing.RIGHT)
    emergency = Emergency(EmergencyId(1), target, 0, 80)
    emergencies = [emergency]
    assignment = RoleAssignment(roster, owners)
    state = replace(game_state, players=players, assignments=assignment, emergencies=emergencies)
    players.clear()
    owners[Role.PILOT] = roster[1]
    roster.clear()
    emergencies.clear()
    assert state.players == game_state.players
    assert state.assignments.owners == game_state.assignments.owners
    assert state.emergencies == (emergency,)
    with pytest.raises(TypeError):
        state.assignments.owners[Role.PILOT] = state.players[1].player_id
    for value, attribute, replacement in [
        (state, "players", ()),
        (state.players[0], "name", "Changed"),
        (state.ship, "hull", 0),
        (state.ship.cooldowns, "coolant", 10),
        (state.round, "tick_index", 1),
        (state.emergencies[0], "deadline_tick", 100),
        (target, "impact_lane", Lane.RIGHT),
        (assignment, "player_ids", ()),
    ]:
        with pytest.raises(FrozenInstanceError):
            setattr(value, attribute, replacement)
    updated = replace(state, ship=replace(state.ship, temperature=500))
    assert state.ship.temperature == 300 and updated.ship.temperature == 500
