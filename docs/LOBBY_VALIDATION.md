# Room and lobby validation — 2026-10-28

Observed Phase 04 verification on Windows. The session began at commit `f801d81`
with a clean working tree; continuation preserved the protocol/integration work
already produced in this session. The sole progress ledger is
[plans/plans.md](../plans/plans.md). No Android, game engine or gameplay launch
behavior was implemented in this phase.

## Dependencies and environment

Python launcher 3.14.0; backend Python 3.12.10; uv 0.13.6. Temurin java/javac
17.0.18 and installed Android Platform 36 revision 2 / Build Tools 35.0.0 were
verified. The backend dependency declarations and `uv.lock` are unchanged; locked
sync checked 31 packages. Existing baseline checks passed with 708 tests before
implementation. The ignored `artifacts/foundation/environment.ps1` selects local
tools; no SDK paths, credentials or generated outputs are committed.

Managed execution initially denied the installed Store Python 3.12 launcher.
Narrow automatic approval for running required interpreter/check commands resolved
that restriction. Commands used workspace `UV_CACHE_DIR=artifacts/phase04/uv-cache`
and `--offline`. The first offline build could not find Hatchling in that new
cache; reusing the existing local uv cache completed the build offline. These
were environment/cache limitations, not code failures or dependency changes.

## Checks and actual observations

Commands below are from `server/` unless stated otherwise:

| Command / check | Observed result |
| --- | --- |
| `uv sync --locked --extra dev --offline` | Passed; 31 packages |
| `uv run --locked --offline pytest -q` | 851 passed; one existing upstream warning |
| `uv run --locked --offline ruff check .` | Passed |
| `uv run --locked --offline ruff format --check .` | Passed; 51 files |
| `uv run --locked --offline mypy src` | Passed; 26 source files |
| `uv run --locked --offline mypy src examples` | Passed; 29 source/example files |
| `uv run --locked --offline ruff check ../scripts`; `uv run --locked --offline ruff format --check ../scripts`; `uv run --locked --offline mypy ../scripts` | Passed; two helper files |
| `uv build --offline` using existing local cache | Final source distribution and wheel built successfully |
| Built wheel, `uv run --locked --offline python -I -c` extraction/TestClient probe | Packaged rooms/sessions/owner modules and `py.typed` present; imports came from extracted wheel; health, admission, lobby, leave and cleanup passed using existing locked dependencies |
| `python scripts/check_repository.py` from root | Passed; 19 briefs, links, package/XML and wrapper structure |
| `git diff --check` | Passed |

Protocol tests validate strict names/codes/ready booleans/empty payloads, safe
unknown-token handling, targeted credential envelopes, nullable host, safe errors
and the shared synthetic Phase 04 fixtures. Existing framing/size/version/rate
tests remain, with their current feature gates updated for implemented commands.

Room tests exercise collision retry/exhaustion, UUID collisions, 2/3-player
capacity under simultaneous joins, exact eligibility counts, no-op revisions,
ready resets, digest-only admission receipts, normalized request conflicts,
128-entry/30-second cache limits, exact grace expiry, vacant-host resume, stale
commands/disconnects, idle expiry and shutdown racing in-flight admissions.
Expiry is checked before queued commands as well as at clock wakeups. The tests
use injected fake time and owner barriers, not sleeps for game/grace time.

Three-client TestClient integration verifies identical rosters/revisions,
private credentials, host/ready/start gating, explicit leave/token invalidation,
stable resume, active-socket replacement, grace host transfer, empty-room expiry,
30-second inbound inactivity, admission deadline cancellation, idle closure and
lifespan cleanup. Outbox tests preserve correlated/critical replies while
coalescing only unsolicited same-room/type snapshots. Pure engine/import/replay
regressions continue to pass.

The implementation checks caught and corrected empty-room double deletion,
shutdown/admission interleaving, admission-error revision metadata, and a replay
edge case where a previously failed resume must remain an error without admitting
a new connection. Cached raw credential envelopes are excluded by the replay type.
Initial Phase 03 assertions that rooms did not exist were updated to current
Phase 04 behavior; later commands still cannot launch gameplay.

## Live manual verification

Ran the single local server from `server/`:

```powershell
uv run --locked --offline uvicorn one_job.main:app --host 127.0.0.1 --port 8765 --workers 1 --ws-max-size 16384 --log-config logging.json
```

In another terminal:

```powershell
uv run --locked --offline python examples/websocket_smoke.py --base-url http://127.0.0.1:8765
uv run --locked --offline python examples/lobby_smoke.py --url ws://127.0.0.1:8765/ws
```

Both exited 0. Health returned the original exact HTTP 200 payload before/after
transport checks. Ping/pong, reserved observer gating, unknown type, malformed
JSON/1007 and unsupported version/1002 matched the contract. The lobby client
created one room and joined twice with distinct identities; all three sockets
agreed on the roster at revision 3. Readiness changes were consistent and eligible
start returned explicit `feature_unavailable`. One player left normally; another
disconnected then resumed the same identity/token. Both surviving sockets agreed
at revision 9 with readiness reset. Host leave transferred ownership and final
leave closed 1000. The client printed no credentials.

Both live scripts and the extracted-wheel probe passed again after the final
replay hardening. Source-archive inspection also confirmed the manual lobby client
was included. The package probe used existing locked dependencies; it does not
claim an independently provisioned clean dependency environment.

Application logs visibly contained only allowlisted generation/request/operation/
error/close/duration fields, with no token or lobby payload. Ctrl+C produced
`Application shutdown complete` and `Finished server process`; the terminal
command ended with interrupted exit 1. No server error was observed. Automated
lifespan tests separately asserted zero remaining room/session/connection tasks.

## Architecture and scope

[ADR-014](DECISIONS.md#adr-014--lobby-ownership-credential-replay-and-expiry-boundaries)
records mailbox ownership, synchronous index changes under serialized admissions,
ephemeral HMAC-issued credentials, credential-free replay receipts, nullable host
succession and exact expiry/activity boundaries. Standard-library
[secrets](https://docs.python.org/3.12/library/secrets.html) and
[hmac](https://docs.python.org/3.12/library/hmac.html) provide secure entropy and
digest comparison. Only targeted outbox messages contain actual resume tokens;
membership and replay records retain digests/metadata. Test fixtures use an
explicit synthetic marker, never a captured session credential.

The host is a permission-bearing player. Eligibility is reusable, while game
launch remains unavailable until Phase 08. There is no role reveal, live engine
runner, observer admission, Android flow, persistence or external deployment.
Restart loses all rooms/credentials. Android builds/device tests were not rerun
for this backend-only phase; prior evidence remains in FOUNDATION_VALIDATION.md
and DOMAIN_MODEL_VALIDATION.md. The existing Starlette/httpx deprecation warning
is retained without changing the dependency baseline.

All required Phase 04 gates have observed passing evidence; no gate remains
blocked. Recommended next phase: 05 — Android Foundation, only on a new instruction.
