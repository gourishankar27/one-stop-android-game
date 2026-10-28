# Core engine validation — 2026-10-27

Observed Phase 02 work on Windows, starting from commit `03022ab` with a clean
working tree. Phase 01 was complete with evidence in DOMAIN_MODEL_VALIDATION.md.
Completion is recorded only in [plans/plans.md](../plans/plans.md).

## Prerequisites and executed checks

Python launcher 3.14.0, backend Python 3.12.10, uv 0.13.6 and JDK 17.0.18 were
observed using `python --version`, `uv run --project server --locked python --version`,
`uv --version` and `java -version`. Existing ignored local tooling setup was
reused; no dependency versions or toolchain pins changed.

| Command / inspection | Observed result |
| --- | --- |
| `uv sync --project server --locked --extra dev` at root | Passed; 31 locked packages checked |
| `python scripts/check_repository.py` at root | Passed; 19 phase briefs, links, packaging/XML/wrapper and domain import boundaries |
| `python scripts/dev.py check-server` at root | Passed; locked setup plus the backend checks below |
| `uv run --locked pytest` in server/ | 557 passed, 1 existing upstream warning, 1.08s; includes 70 new engine/replay cases and extended isolated execution |
| `uv run --locked ruff check .` in server/ | All checks passed |
| `uv run --locked ruff format --check .` in server/ | 24 files already formatted |
| `uv run --locked mypy src` in server/ | Success; 12 source files |
| `uv build` in server/ | Wheel and source distribution built successfully, version 0.1.0 |
| `uv run --locked mypy examples` in server/ | Success; one example file |
| `uv run --locked ruff check ../scripts`, `uv run --locked ruff format --check ../scripts`, `uv run --locked mypy ../scripts` in server/ | Passed; 2 existing helpers |
| Wheel/source archive inspection | Engine/rules and `py.typed` present in wheel; sdist has 33 entries including the example and all three replay fixtures |
| Clean wheel install with `--no-deps`, followed by isolated example runs | Passed for both output settings; no web dependencies installed in that environment |
| `git diff --check` | Passed; no whitespace errors |

Clean-package commands, from root:

```powershell
uv venv --python 3.12 artifacts/phase-02/wheel-env
uv pip install --python artifacts/phase-02/wheel-env/Scripts/python.exe --no-deps server/dist/one_job_server-0.1.0-py3-none-any.whl
.\artifacts\phase-02\wheel-env\Scripts\python.exe -I server/examples/engine_round.py --output 40
.\artifacts\phase-02\wheel-env\Scripts\python.exe -I server/examples/engine_round.py --output 60
```

The ordinary test subprocess also runs 900 engine steps with an empty environment
and checks that FastAPI, Pydantic, asyncio, socket, HTTPX and Uvicorn are not loaded.
The source checker confirms the pure domain has no forbidden imports. Tests use
explicit steps; there are no sleeps for simulated game time.

## Behavioral and replay evidence

Engine tests cover prestart/duplicate-start errors; strict seed/step validation;
explicit 2/3-player ownership and fixed rosters; power bounds/budget checks;
lane edges and two-tick cooldown; coolant clamping and the 30-tick boundary;
heat thresholds, hull clamping, exact victory/defeat timing and the hull/timer tie.
Invalid or unsupported commands preserve the same snapshot/history and emit no
events. Old snapshots and trace tuples remain immutable. Terminal updates emit
one event, then preserve the same result/state on further valid ticks. The private
RNG and global random state remain unchanged through actions, rejections and ticks.

The concrete replay harness is `tests/domain/test_engine_replay.py`. Its three
fixtures record engine/config/Python versions, config overrides, seed, supplied
IDs, roster, assignments, boundary-indexed commands and accepted order:

- `ordered-victory.json`: same-boundary ordering, cooldown/edge rejections,
  independently specified checkpoints, and victory at 900 ticks.
- `heat-defeat.json`: critical damage clamps an 11-unit hull to zero on tick 3.
- `hull-timer-tie.json`: hull reaches zero exactly at the configured final tick
  600; defeat takes precedence over victory.

Each fixture runs twice and compares every captured snapshot, action result,
accepted trace and terminal event. Replaying accepted commands alone reproduces
every boundary and final state, proving that rejected requests contribute no
effects or ordering entries. A changed valid power action gives a different
deterministic temperature; changing just the seed has no effect while RNG draws
are absent. Fixtures were recorded for Python 3.12.10 and `spaceship-engine-v1`;
no cross-version random replay guarantee is claimed.

## Manual verification

From server/, ran the fixed-seed example with an explicit tick loop:

```powershell
uv run --locked python examples/engine_round.py --output 40
uv run --locked python examples/engine_round.py --output 60
```

Observed output, also reproduced from the clean wheel environment:

```text
seed=12345 output=40 outcome=victory tick=900 elapsed_ms=90000 hull=1000 temperature=0 end_events=1
seed=12345 output=60 outcome=defeat tick=549 elapsed_ms=54900 hull=0 temperature=1000 end_events=1
```

Only a valid action value changed. Neither run used a web server, Android,
wall-clock scheduling or a random event. The example is checked in for repeatable
verification. Backend check logs and the clean environment are under ignored
`artifacts/phase-02/`; package outputs remain ignored in `server/dist/`.

## Decisions and remaining limitations

No significant architecture deviation or wire-contract change was needed. The
implementation follows ADR-002/ADR-006. Boundary n means n completed steps, and
accepted commands apply in caller order before step n+1. The engine API and its
stable internal result codes/events are documented in GAME_STATE.md. Phase 03
must map them into typed transport/projections explicitly.

No required Phase 02 gate remains blocked. Pytest retains the existing upstream
Starlette HTTPX TestClient deprecation warning; it is not suppressed. uv used
file copies when cross-drive hardlinking was unavailable; installation succeeded.

The engine implements only power, lane movement, coolant, base heat/critical
damage, supported cooldowns and timer/result rules. Shield values remain at their
configured initial values; existing reservations still constrain power changes.
The other six actions are explicitly unavailable. No shield/boost dynamics,
emergency scheduler/resolver, seeded assignment, pause/recovery lifecycle, rooms,
WebSocket adapter, projections or Android gameplay was added. No fun/balance or
multiplayer claim is made.

Android builds/device smoke and live HTTP serving were not rerun in this phase:
the selected brief requires pure engine checks, and Android/health transport,
dependencies and protocol were unchanged. Their prior evidence remains in the
foundation/model validation records. No later phase was started.
