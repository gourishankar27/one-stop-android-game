import subprocess
import sys
import textwrap


def test_domain_import_is_independent_of_transport_and_environment_configuration() -> None:
    code = textwrap.dedent("""\
        import sys
        from random import Random
        from uuid import UUID
        from one_job.domain import GameConfig, GameEngine, Player, PlayerId, RoleAssignment, Role
        from one_job.domain.types import RoundId
        from one_job.domain.roles import STATIONS, assign_roles
        config = GameConfig()
        ids = (PlayerId(UUID(int=1)), PlayerId(UUID(int=2)))
        players = (Player(ids[0], "A"), Player(ids[1], "B"))
        assert set(assign_roles(players, Random(123)).owners) == set(Role)
        assert set(STATIONS) == set(Role)
        roles = RoleAssignment(
            ids, {Role.PILOT: ids[0], Role.ENGINEER: ids[1], Role.SHIELDS: ids[1]}
        )
        engine = GameEngine(config, 123, players, roles, round_id=RoundId(UUID(int=10)))
        engine.start()
        assert engine.tick(900).state.round.result.outcome == "victory"
        forbidden = {"fastapi", "pydantic", "asyncio", "socket", "httpx", "uvicorn"}
        loaded = {name.split(".")[0] for name in sys.modules}
        assert not loaded & forbidden, sorted(loaded & forbidden)
        assert config.duration_ticks == 900
        assert roles.roles_for(players[1].player_id) == (Role.ENGINEER, Role.SHIELDS)
        print("pure domain import and construction passed")
        """)
    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        env={},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "pure domain import and construction passed"
