# One Job server

Current functionality: independent `GET /health` and `/ws` ping/pong/typed errors.
Phase 04 supports create/join/ready/leave/state, stable credentials, resume/fencing,
disconnect grace, host transfer, idle expiry and bounded reply replay. Eligible
start remains `feature_unavailable`; no room launches gameplay.
The package uses a `src/` layout and Python 3.12+. Phase 01 also provides pure,
immutable domain values with constructor validation; see the
[model API and construction example](../docs/GAME_STATE.md#implemented-python-api).
Phase 02 adds a synchronous fixed-step engine for power, lanes, coolant,
heat/damage and victory/defeat timing. It has no emergency scheduler,
live WebSocket gameplay or full control catalog yet. Phase 03 adds strict v1
DTOs, a bounded connection supervisor, redacted logs and a fixture-only engine
adapter. See the [implemented protocol subset](../docs/NETWORK_PROTOCOL.md#implemented-phase-04-subset).

From this directory:

```bash
uv sync --locked --extra dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
uv run uvicorn one_job.main:app --host 127.0.0.1 --port 8000 --workers 1 --ws-max-size 16384 --log-config logging.json
```

The checked-in `uv.lock` pins dependencies. Update it deliberately with `uv lock`
when changing `pyproject.toml`, then rerun checks. `uv sync --locked` must work on
a clean clone; do not commit `.venv/`. A pip alternative is
`python -m pip install -e '.[dev]'` in a Python 3.12 virtual environment; this
uses the declared ranges rather than the uv lock.

`uv build` produces a source distribution and wheel in ignored `dist/`.
Observed foundation results and tool versions are recorded in
[FOUNDATION_VALIDATION.md](../docs/FOUNDATION_VALIDATION.md).

`one_job.main.create_app()` creates an isolated app with lifespan-owned connections;
tests can inject a clock, `ConnectionSettings` and `RoomSettings`. The health route
uses a Pydantic response model and reports liveness only. `application/` owns
connection I/O/tasks; `protocol/` validates/maps allowlisted DTOs. The implemented
`domain/` package is independent of the health service and contains ordinary
dataclasses/enums, not Pydantic DTOs. `uv run pytest tests/domain` checks its bounds,
ownership, immutable snapshots, result invariants and isolated import. Observed
Phase 01 results are in [DOMAIN_MODEL_VALIDATION.md](../docs/DOMAIN_MODEL_VALIDATION.md).

Run a deterministic engine example without starting the web service:

```bash
uv run python examples/engine_round.py --output 40
uv run python examples/engine_round.py --output 60
uv run pytest tests/domain/test_engine.py tests/domain/test_engine_replay.py
```

With the example's fixed IDs/seed, output 40 wins at tick 900; output 60 loses to
critical heat at tick 549. Neither command sleeps. The engine API is documented
in [GAME_STATE.md](../docs/GAME_STATE.md#phase-02-engine-api); observed Phase 02
evidence is in [ENGINE_VALIDATION.md](../docs/ENGINE_VALIDATION.md).

Run one Uvicorn worker when in-memory rooms are introduced. Multiple workers
would own different room registries. Development reload also erases rooms.

With the local server running, use a second terminal:

```bash
uv run python examples/websocket_smoke.py
uv run python examples/lobby_smoke.py
uv run pytest tests/protocol tests/api tests/application
```

The client checks health, correlated pong, unavailable/unknown operations and
documented invalid JSON/version closes. The lobby client uses three sockets to
check admission, readiness, unavailable start, leave, disconnect/resume, matching
revisions and host transfer without printing credentials. Unadmitted sockets
expire after ten seconds; admission cancels that deadline. Lifecycle logs contain only allowlisted
metadata; never enable raw WebSocket debug logs with real credentials. Current
results and limitations: [LOBBY_VALIDATION.md](../docs/LOBBY_VALIDATION.md).

For real-phone development later, bind to a reachable private address and use
the debug transport configuration introduced in Phase 06. Phase 00 has no
Android network permission, endpoint selector or gameplay socket.
