from uuid import UUID

import pytest

from one_job.domain import GameConfig, GameState, Player, PlayerId, Role, RoleAssignment
from one_job.domain.models import RoundState, ShipState
from one_job.domain.types import RoundId, RoundStage


@pytest.fixture
def players() -> tuple[Player, ...]:
    return tuple(Player(PlayerId(UUID(int=index)), f"Crew {index}") for index in range(1, 4))


@pytest.fixture
def game_state(players: tuple[Player, ...]) -> GameState:
    config = GameConfig()
    ids = tuple(player.player_id for player in players)
    return GameState(
        config=config,
        players=players,
        assignments=RoleAssignment(ids, dict(zip(Role, ids, strict=True))),
        ship=ShipState.from_config(config),
        round=RoundState(RoundId(UUID(int=10)), stage=RoundStage.RUNNING),
    )
