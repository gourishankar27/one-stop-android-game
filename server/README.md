# One Job server

Current functionality: independent `GET /health` and `/ws` ping/pong/typed errors.
Phase 04 supports create/join/ready/leave/state, stable credentials, resume/fencing,
disconnect grace, host transfer, idle expiry and bounded reply replay. Eligible
start enters a private role briefing. Phase 11 acknowledgements enter a server
3000ms countdown, then running with all nine controls, fixed-step physics, 5Hz owned state and typed
action feedback. Disconnect pauses; leave/grace/briefing timeout/overload abort.
The package uses a `src/` layout and Python 3.12+. Phase 01 also provides pure,
immutable domain values with constructor validation; see the
[model API and construction example](../docs/GAME_STATE.md#implemented-python-api).
Phase 02 adds a synchronous fixed-step engine for power, lanes, coolant,
heat/damage and victory/defeat timing. Phase 09 completes the catalog/live control
loop; Phase 10 adds the concrete seeded three-emergency scheduler, private
instructions and shared lifecycle labels. Phase 03 adds strict v1
DTOs, a bounded connection supervisor, redacted logs and a fixture-only engine
adapter. Phase 08 adds pure seeded assignment, metadata, authenticated ownership
and allowlisted owned-station projections. See the
[implemented protocol subset](../docs/NETWORK_PROTOCOL.md#implemented-phase-12-subset).

Phase 12 adds two distinct public display sessions per room, code-only admission
at any stage, public lobby/round/result snapshots and independent credential resume.
Observers have no controller/host/ready permissions, never pause players and are
expired when the controller room disappears. Run `uv run python examples/display_smoke.py`
against the default local seeded harness for real 2/3-player plus two-display
capacity/privacy/permission/recovery/warning/result checks. Actual evidence and
deferred device gates: [PUBLIC_DISPLAY_VALIDATION.md](../docs/PUBLIC_DISPLAY_VALIDATION.md).

From this directory:

For repeatable Phase 10 verification, run
`uv run python examples/emergency_harness.py --seed 71 --profile default`, then
`uv run python examples/emergency_smoke.py` in another terminal. The optional
`--profile verification` is an explicit UI-inspection config with longer windows
and lower damage; it does not change production defaults. Full overrides, device
commands and observed evidence are in [EMERGENCY_VALIDATION.md](../docs/EMERGENCY_VALIDATION.md).

For Phase 11 repeatable room cycles, run that local harness with
`--seed 71 --profile lifecycle`, then `uv run python examples/round_lifecycle_smoke.py`.
This explicit verification profile uses 60-second rounds with emergencies disabled;
all other rules remain normal, and production defaults remain 90 seconds with
emergencies enabled. The local seed factory increments on every start/rematch;
there is no client seed/config switch. The script runs three rounds in each of
2/3-player rooms, countdown recovery, two rematches, stale-round fencing and lobby
readiness reset. Evidence and remaining manual gates are in
[ROUND_LIFECYCLE_VALIDATION.md](../docs/ROUND_LIFECYCLE_VALIDATION.md).

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
uv run python examples/role_smoke.py
uv run python examples/gameplay_smoke.py
uv run pytest tests/protocol tests/api tests/application
```

The client checks health, correlated pong, unavailable/unknown operations and
documented invalid JSON/version closes. The lobby client uses three sockets to
check admission, readiness, rejected non-host start, leave, disconnect/resume, matching
revisions and host transfer without printing credentials. Unadmitted sockets
expire after ten seconds; admission cancels that deadline. Lifecycle logs contain only allowlisted
metadata; never enable raw WebSocket debug logs with real credentials. Current
room evidence: [LOBBY_VALIDATION.md](../docs/LOBBY_VALIDATION.md). The role client
starts separate two-/three-controller rounds, checks captured frame field
allowlists and owned-only station keys/metadata, rejects wrong-role actions,
acknowledges everyone and verifies direct running at tick zero before leaving. It is bounded
to 20 seconds and optionally writes only sanitized field-name evidence with
`--proof ../artifacts/phase08/privacy-proof.json`; never save raw private frames.
Current role results: [ROLE_SYSTEM_VALIDATION.md](../docs/ROLE_SYSTEM_VALIDATION.md).
The gameplay example exercises all nine actions with two/three controllers,
cross-station power rejection, synchronized public state at matching revisions,
owned-only station keys and shutdown cancellation. Both examples default to
port 8765; pass `--url ws://127.0.0.1:8000/ws` when using the server command above.
Current gameplay evidence: [CORE_GAMEPLAY_VALIDATION.md](../docs/CORE_GAMEPLAY_VALIDATION.md).

For real-phone development later, bind to a reachable private address and use
the debug transport configuration introduced in Phase 06. Phase 00 has no
Android network permission, endpoint selector or gameplay socket.
