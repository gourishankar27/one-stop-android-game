from uuid import UUID

import pytest

from one_job.domain.config import GameConfig
from one_job.domain.engine import GameEngine
from one_job.domain.models import Player, RoleAssignment
from one_job.domain.types import PlayerId, Role, RoundId
from tests.support import FakeClock


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def engine():
    players = tuple(Player(PlayerId(UUID(int=i)), f"Crew {i}") for i in range(1, 4))
    ids = tuple(player.player_id for player in players)
    return GameEngine(
        GameConfig(emergencies_enabled=False),
        827364,
        players,
        RoleAssignment(ids, dict(zip(Role, ids, strict=True))),
        round_id=RoundId(UUID(int=10)),
    )
