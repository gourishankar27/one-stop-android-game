"""Disposable local seed harness, with no remotely selectable seed or rule bypass."""

import argparse
from itertools import count

import uvicorn

from one_job.domain.config import GameConfig
from one_job.main import create_app


def verification_config() -> GameConfig:
    """Longer UI windows/lower damage for scripted device inspection, not balance."""
    return GameConfig(
        version="spaceship-ui-verification-v1",
        round_duration_ms=120_000,
        initial_temperature=799,
        initial_engine_output=60,
        initial_shield_energy=1000,
        heat_gain_per_tick=4,
        cooling_per_tick=4,
        coolant_amount=300,
        critical_heat_hull_damage=0,
        asteroid_hull_damage=60,
        overheat_hull_damage=60,
        overload_hull_damage=60,
        asteroid_deadline_ticks=160,
        overheat_deadline_ticks=160,
        overload_deadline_ticks=140,
        early_interval_min_ticks=80,
        early_interval_max_ticks=80,
        middle_interval_min_ticks=80,
        middle_interval_max_ticks=80,
        late_interval_min_ticks=80,
        late_interval_max_ticks=80,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=71)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--profile", choices=("default", "verification", "lifecycle"), default="default"
    )
    args = parser.parse_args()
    config = verification_config() if args.profile == "verification" else GameConfig()
    if args.profile == "lifecycle":
        config = GameConfig(round_duration_ms=60_000, emergencies_enabled=False)
    seeds = count(args.seed)
    app = create_app(game_config=config, seed_factory=lambda: next(seeds))
    uvicorn.run(
        app, host=args.host, port=args.port, workers=1, ws_max_size=16384, log_config="logging.json"
    )
