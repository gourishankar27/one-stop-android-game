"""Run the Phase 02 engine with fixed IDs/seed and no server or wall-clock waits."""

import argparse
from uuid import UUID

from one_job.domain import GameConfig, GameEngine, Player, PlayerId, Role, RoleAssignment
from one_job.domain.actions import SetEnginePower
from one_job.domain.types import RoundId


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=int, choices=range(101), default=40)
    args = parser.parse_args()
    config = GameConfig(emergencies_enabled=False)
    players = tuple(Player(PlayerId(UUID(int=index)), f"Crew {index}") for index in range(1, 4))
    ids = tuple(player.player_id for player in players)
    assignments = RoleAssignment(ids, dict(zip(Role, ids, strict=True)))
    engine = GameEngine(config, 12345, players, assignments, round_id=RoundId(UUID(int=10)))
    engine.start()
    action = engine.apply_action(ids[1], SetEnginePower(args.output))
    assert action.accepted
    end_events = 0
    for _ in range(config.duration_ticks):
        update = engine.tick()
        end_events += len(update.events)
        if update.state.round.result is not None:
            break
    state = engine.snapshot()
    assert state.round.result is not None
    print(
        f"seed=12345 output={args.output} outcome={state.round.result.outcome} "
        f"tick={state.tick_index} elapsed_ms={state.elapsed_ms} hull={state.ship.hull} "
        f"temperature={state.ship.temperature} end_events={end_events}"
    )


if __name__ == "__main__":
    main()
