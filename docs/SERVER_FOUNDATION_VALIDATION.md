# Server foundation validation — 2026-10-28

Observed Phase 03 implementation/verification on Windows during October 27–28.
The master [ledger](../plans/plans.md) is the only progress record. Phase 02 was
already verified/checked there; its engine, fixtures and documentation were
uncommitted at session start and have been preserved. No Phase 04 room/admission
behavior or Android changes were implemented.

## Dependencies and environment

| Command / prerequisite | Actual observation |
| --- | --- |
| `python --version`; `py -3.12 --version` | Launcher 3.14.0; installed 3.12.10 |
| `uv --version`; `uv run --project server --locked python --version` | uv 0.13.6; backend 3.12.10 |
| `java -version`; `javac -version` | Temurin 17.0.18 |
| Read installed SDK `platforms/android-36/source.properties` and `build-tools/35.0.0/source.properties` | API 36 revision 2; Build Tools 35.0.0 |
| `uv sync --locked --extra dev` in `server/` | Passed; 31 locked packages |

The ignored foundation environment script selects local tools; no SDK paths or
environment credentials are committed. AnyIO was already locked at 4.15.1 and
used by Starlette. It is now a direct dependency (`>=4,<5`) for shielded ASGI
cleanup; `uv lock` changed only the project's dependency metadata, no versions.
FastAPI 0.162.0, Starlette 1.10.0, Pydantic 2.14.1, Uvicorn 0.54.0 and websockets
16.1.1 remain on the existing lock baseline.

## Backend and package checks

| Exact command / check | Observed result |
| --- | --- |
| `uv run pytest` | 708 passed, one upstream TestClient deprecation warning |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed; 44 files |
| `uv run mypy src` | Passed; 23 source files |
| `uv run mypy src examples` | Passed; 25 source files |
| `uv build` | Passed; source distribution and Python wheel in ignored `server/dist/` |
| `python scripts/dev.py check-server` from root | Passed locked setup, full tests and source static checks; final hardening rerun separately passed all 708 tests |
| `python scripts/check_repository.py` from root | Passed; 19 phase briefs, links, package/XML and wrapper structure |
| `git diff --check` | Passed; only repository line-ending notices |
| `uv run --locked ruff check ../scripts`; `uv run --locked ruff format --check ../scripts`; `uv run --locked mypy ../scripts` | Passed; two helper files |
| `uv run --locked pytest tests/api/test_websocket.py tests/application/test_connections.py -q --disable-warnings`, repeated ten times | 46 passed on every run; 460 executions, no cleanup race reproduced |
| Built-wheel inspection and `uv run --locked python -I -c` probe | Required protocol/application/API modules and `py.typed` present; extracted-wheel import, health and WebSocket pong passed using existing locked dependencies |

The full suite includes the 557 existing domain/health tests plus 151 new
protocol/API/application cases. Parser tests cover all reserved commands, strict
envelopes and ping payloads, unknown/missing fields, byte/Unicode bounds, safe
correlation, duplicate/nonfinite/deep JSON and unsupported versions. TestClient
verifies ping/pong, recoverable/fatal errors, binary frames, ten-second admission,
separate rate limits, factory isolation, shutdown and redacted logs/errors.
Async ASGI harness tests cover blocked sends/accepts, timeout/queue-overflow 1013,
disconnect/cancellation, writer exceptions and zero remaining owned tasks/waiters.
Final review added fatal-error precedence over exhausted rate budgets, plus
blocked/failing final-close regression tests; all four new cases passed.
Outbox tests preserve critical replies/order and restrict snapshot coalescing.
Adapter tests call the real engine fixture, exercise every result-code mapping,
check public field allowlists/percentages/results, and cancel an awaited tick
without advancing simulation. Existing isolated-import/replay tests still pass;
the domain has no transport, asyncio, clock or environment dependency.

The wheel probe extracted the built archive into a temporary directory, prepended
that directory under `python -I`, asserted `one_job.main.__file__` came from the
extracted wheel, then ran health and ping through a new TestClient. This checks
packaged code rather than importing the editable source path. It is not a claim
of an independently provisioned clean dependency environment.

## Live manual verification

From `server/`, with port 8765 available:

```powershell
uv run --locked uvicorn one_job.main:app --host 127.0.0.1 --port 8765 --workers 1 --ws-max-size 16384 --log-config logging.json
```

In a second terminal, also from `server/`:

```powershell
uv run --locked python examples/websocket_smoke.py --base-url http://127.0.0.1:8765
```

Observed, exit 0:

- `GET /health`: HTTP 200 with the original exact liveness payload.
- Ping: correlated `pong`, unchanged nonce, null room revision.
- `create_room`: correlated `feature_unavailable`, no admission.
- Unknown type: correlated `unknown_type`; same socket stayed open.
- Malformed JSON: safe `invalid_message`, null correlation, close 1007.
- Version 2 on a fresh socket: `unsupported_version`, correlated ID, close 1002.
- A second health request still returned HTTP 200.

The manual smoke and extracted-wheel probe passed again after final hardening.
A separate bounded `uv run --locked python -c` live probe sent 16,385 bytes and
observed close 1009 directly from Uvicorn, before an application error, matching
the documented server-level limit. Source archive inspection confirmed the
logging config/manual client were included; wheel metadata declares AnyIO.

Connection logs visibly contained generation, validated request ID, allowlisted
operation/error code, close code and duration, without payloads/views. Ctrl+C
produced `Waiting for application shutdown`, `Application shutdown complete`
and `Finished server process`; the PTY command ended as an interrupted process
(exit 1), not a server failure. No live room or engine task was expected.

## Architecture decisions and limitations

[ADR-013](DECISIONS.md#adr-013--phase-03-transport-subset-and-bounded-connection-ownership)
records the strict current subset, future-payload gating, bounded ownership,
coalescing/rates and redaction. The first API run exposed an intermittent
TestClient exit cancellation; cleanup is now shielded while cancelling/awaiting
owned tasks, following [AnyIO's finalization guidance](https://anyio.readthedocs.io/en/stable/cancellation.html#finalization).
The fixed regression and ten repeated targeted runs passed. An initial deep-JSON
test incorrectly classified a valid nested root as malformed JSON; it now checks
safe bounded rejection without depending on the interpreter recursion limit.

There are no credentials, lobby/rooms, duplicate-request cache, generation
membership fencing, live engine runner, station projections or Android codec.
Generation IDs currently identify connection lifetimes only. The fixture adapter
emits the baseline public state and empty warnings; no private views are emitted.
These are planned later-phase behavior, not missing Phase 03 implementation.

The Starlette warning recommends migrating from httpx to httpx2. The existing
test dependency remains unchanged; the warning does not fail checks. uv also
reported cross-filesystem hardlink fallback during the editable package rebuild;
installation succeeded by copying. Android builds/lint/device smoke were not
rerun in this backend-only phase; earlier evidence remains in
[FOUNDATION_VALIDATION.md](FOUNDATION_VALIDATION.md) and
[DOMAIN_MODEL_VALIDATION.md](DOMAIN_MODEL_VALIDATION.md). Toolchain presence was
checked, and no Android source/dependency changed.

No required Phase 03 gate remains blocked. Recommended next phase: 04 — Room and
Lobby System, only on a new request.
