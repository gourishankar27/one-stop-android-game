# Verification strategy

Foundation evidence lives in FOUNDATION_VALIDATION.md; Phase 01 model and
regression evidence lives in [DOMAIN_MODEL_VALIDATION.md](DOMAIN_MODEL_VALIDATION.md).
Phase 02 engine/replay evidence lives in [ENGINE_VALIDATION.md](ENGINE_VALIDATION.md).
Phase 03 transport evidence lives in [SERVER_FOUNDATION_VALIDATION.md](SERVER_FOUNDATION_VALIDATION.md).
Phase 04 room/lobby evidence lives in [LOBBY_VALIDATION.md](LOBBY_VALIDATION.md).
Phase 05 Android shell evidence lives in [ANDROID_FOUNDATION_VALIDATION.md](ANDROID_FOUNDATION_VALIDATION.md).
Phase 06 transport/device evidence lives in [ANDROID_NETWORKING_VALIDATION.md](ANDROID_NETWORKING_VALIDATION.md).
Phase 07 lobby evidence lives in [LOBBY_UI_VALIDATION.md](LOBBY_UI_VALIDATION.md).
Phase 08 role/privacy evidence lives in [ROLE_SYSTEM_VALIDATION.md](ROLE_SYSTEM_VALIDATION.md).
This document defines the commands and behavior each layer must verify as it is
implemented.

## Foundation

From root: `python scripts/check_repository.py` verifies required files, all 19
phase briefs, mandatory sections, local Markdown links, packaging configuration,
Android XML and the wrapper JAR. It does not compile Kotlin or prove gameplay.

From `server/`:

```bash
uv sync --locked --extra dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```

Or use `python scripts/dev.py check-server` from root. Packaging is also checked
with `uv build` before handing off the foundation. Do not commit build outputs.

From `android/`: `./gradlew :app:assembleDebug :app:lintDebug :app:testDebugUnitTest`.
Use `./gradlew.bat` on Windows. `:app:connectedDebugAndroidTest` requires a device.
A successful `testDebugUnitTest NO-SOURCE` is not evidence of Android unit tests.
The Compose tests check shell launch/navigation and retained form inputs.
Keep its explicit Espresso 3.7.0 dependency: Compose's older transitive version
failed before the assertions on API 37. ADR-012 records the observed failure and
the test-only fix; FOUNDATION_VALIDATION.md records the passing rerun.

## Pure engine (01–02, 08–11)

Phase 01 has model tests in `server/tests/domain/`: config bounds/coherence,
explicit 2/3-player station ownership, action argument domains, ship/result/round
invariants, typed emergency records and defensive snapshot copying. The isolated
import test launches Python with an empty environment and asserts that importing
and constructing domain values loads no FastAPI, Pydantic, asyncio, sockets or
other transport dependencies. Run `uv run pytest tests/domain` from `server/`.
Phase 02 adds `test_engine.py`, `test_engine_replay.py`, three recorded fixtures
under `tests/fixtures/engine/`, and `examples/engine_round.py` for manual use.
Run `uv run pytest tests/domain/test_engine.py tests/domain/test_engine_replay.py`.
These cover exact end ticks, ordered/atomic actions, ownership, cooldown edges,
unchanged RNG, snapshot isolation, terminal idempotence and the hull/timer tie.
Replay compares every snapshot and event between independent engines, then checks
that accepted-only traces reproduce every boundary despite rejected commands.
Fresh-process isolation also runs the engine through victory with an empty
environment. Phase 08 adds `test_roles.py` for deterministic seeded two-/three-
player assignment, invalid roster/RNG preservation, metadata immutability, nine-
action ownership and pause/resume/abort. The fresh-process isolation test includes
role metadata/assignment. Emergency scheduling, remaining controls and live
orchestration still await their selected phases.

Use pytest without a web server, wall-clock waits or Android. Cover configuration
bounds, immutable snapshot behavior, role ownership, atomic rejection, exact ticks,
resource invariants, cooldown boundaries, simultaneous terminal conditions, and
every emergency's resolve/fail path. Two engines with the same seed/config and
tick-indexed accepted actions must produce equal semantic snapshots/events.
Different seeds should produce different eligible schedules on selected fixtures,
not a statistically flaky assertion that every seed differs.

Replay fixtures include engine/config version, Python version, seed, tick number,
command order, actor/station and accepted action parameters. Inject stable IDs in
tests or exclude infrastructure-only UUIDs. Advancing 900 ticks takes no 90-second
sleep. Test rejects negative/nonfinite deltas and refuses non-100ms steps if a
delta API is exposed. Do not assert cross-version RNG equivalence.

## Server and protocol (03–04 onward)

Phase 03–04 runnable checks from `server/`:

```bash
uv run pytest tests/protocol tests/api tests/application
uv run mypy src examples
```

Strict parser/fixture tests cover Unicode byte bounds, unsafe correlation IDs,
duplicates/nonfinite JSON, unsupported versions and future feature gates.
TestClient verifies real ASGI ping/errors/close codes, independent health/factories,
separate rate budgets, injected admission deadline and sentinel-free errors/logs.
Async tests use an ASGI socket harness to block sends/handshakes and a fake clock
to verify send timeouts, queue overflow, disconnect/shutdown and level cancellation.
They assert no owned tasks/deadline waiters remain. Outbox tests preserve critical
order and coalesce only unsolicited same-kind/round snapshots. Adapter tests call
the real pure fixture, check all domain rejection mappings, public field allowlists,
resource percentages, final results and cancellation without a domain tick.
No test sleeps for simulated admission or gameplay time.

Phase 04 adds `tests/application/test_rooms.py`, `tests/api/test_lobby.py` and
`tests/protocol/test_lobby_messages.py`. These check collision exhaustion,
simultaneous joins/capacity, strict normalization, two/three-player eligibility,
ready resets, one revision per mutation, explicit leave, grace/idle expiry,
stable resume/fencing, cache conflict/bounds/TTL, credential-free replay storage,
nullable host succession and shutdown/admission races. Three-client ASGI tests
compare shared roster/revisions and absence of credential sentinels. Fake time
is advanced explicitly; `await app.state.rooms.synchronize()` provides an owner
barrier after clock advancement. `RoomSettings` and `ConnectionSettings` can
shorten deadlines independently. Fixtures in `docs/protocol-fixtures/phase04.json`
validate current DTOs and use an explicit synthetic token marker.

For a live local smoke check, run `python scripts/dev.py run-server` from root,
then `uv run python examples/websocket_smoke.py` from `server/` in a second terminal.
It checks health, ping/pong, unavailable/unknown commands, malformed JSON/1007 and
unsupported version/1002, then health again. It creates no rooms. The script is
bounded to 15 seconds and accepts `--base-url http://127.0.0.1:8765` for another
local port. Stop Uvicorn with Ctrl+C and observe clean application shutdown.

With the same server, `uv run python examples/lobby_smoke.py --url ws://127.0.0.1:8765/ws` exercises three
real WebSocket clients: create/join twice, ready, rejected non-host start, leave,
disconnect/resume, matching lobby revisions and host transfer/final leave.
Use `--url ws://127.0.0.1:8765/ws` for another local port. It prints no credentials
and is bounded to 20 seconds. It does not start a round.

Phase 08 adds `tests/application/test_briefing_rounds.py` and
`tests/protocol/test_role_messages.py`. Injected clocks test the exact 60-second
abort, suspended/resumed budget, all-participant reconnect, held tick zero,
departure/grace abort, stale IDs, authenticated ownership and per-member private
replay. Sentinel tests prove other stations' exact values/metadata are absent,
including for the host. Shared synthetic `phase08.json` fixtures round-trip in
Python and Kotlin. Private representations and recovery clear stale details.

With the local server running, `uv run python examples/role_smoke.py` starts
separate two-/three-client rooms, inspects captured frames against exact field
allowlists, checks owned-only metadata/stations, rejects non-host/wrong-role
commands, acknowledges all and verifies held briefing at tick zero before leave.
`--proof ../artifacts/phase08/privacy-proof.json` optionally saves only sanitized
field names/counts, never raw frames, tokens or player IDs. Its global limit is
20 seconds. Actual UI verification uses the approved phone plus two emulators:
read both owned stations before acknowledging in two-player mode, verify one
distinct station per client in three-player mode, and let 60 seconds expire to
an explicit abort. `RoleViewModelTest`, `RoleCodecTest`, repository tests and
`RoleUiTest` cover own metadata, dual reads, pending guards, recovery, pause,
held/abort routing and forbidden keys. The enabled live instrumented test starts
and acknowledges an actual round, rejects wrong-role/stale commands, then resumes
to a fresh private state with the same identity/acknowledgement and leaves.

Use app-factory tests with isolated registries and controllable clock/ticker.
Test typed envelopes and all error classes, WS handshake, frame limits, version
failure, host checks, concurrent room joins/collisions, full lobby, leave/expiry,
bounded sends, obsolete connection fencing and lifecycle task cleanup.
Use public and private sentinel fields: verify forbidden fields are absent in
every emitted view/error, including host and observer connections.

Tick orchestration tests use a fake monotonic clock; no sleeps for grace periods.
Check queued action ordering, per-round action sequence replay rejection,
request-ID deduplication, stale round rejection, output backpressure and one
terminal result event. Use actual test sockets to prove DTO/domain integration;
do not replace all integration tests with mocked route calls.

## Android (05 onward)

Phase 05: `:app:testDebugUnitTest` runs 8 tests (3 client draft-hint tests and
5 ViewModel/StateFlow tests). `MainDispatcherRule` supplies a coroutine test
dispatcher; fake-repository status changes use virtual scheduling. Tests verify
Unicode/control/code hints, immutable state updates, validation recovery, current
repository status after restoration, whitelisted saved inputs and independent
Create/Join entries. No network command exists to submit a draft.

`:app:connectedDebugAndroidTest` runs 5 tests on a device: Home smoke plus four
shell tests. They traverse future destinations and system Back, check local
forms, recreate the Activity with retained Join inputs and verify no INTERNET
permission (the historical Phase 05 state). Phase 06 updates this assertion to
require INTERNET. They test navigation/state behavior, not one assertion per placeholder.
The original Espresso fix remains. Manual verification additionally checks actual
device rotation and font scale 2.0 with scrolling; document what was inspected.
These are shell tests, not real multiplayer or a full process-death fault matrix.

Phase 06 runs 30 JVM tests: the retained 8 draft/ViewModel tests plus 22 endpoint,
codec and repository checks. Fake sockets and virtual time cover strict shared
fixtures, additive fields, unknown kinds/versions, primitive coercion, duplicate
keys/nesting/byte bounds, correlation, uncertain replies, stale generations,
equal-revision distinct messages, retired rounds, send/pending bounds, heartbeat,
absolute recovery deadline, no action replay, credential clearing and endpoint
changes. No simulated game time uses sleep.

Eight instrumented tests include lifecycle-collected connection feedback,
application-owner retention after recreation and an opt-in real-server test.
Normal `connectedDebugAndroidTest` skips that live case unless
`-Pandroid.testInstrumentationRunnerArguments.oneJobLiveServer=true` is supplied.
Quote the full flag in PowerShell. Configure the explicit debug endpoint and
cleartext opt-in as described in [android/README.md](../android/README.md#explicit-endpoint-configuration).
The enabled test checks real ping/create/join, readiness, the unavailable start
gate, socket loss/resume with stable identity and fresh full snapshot, and leave.
Run it on an emulator and physical phone over the trusted LAN. Additionally
create a test membership in the debug Home panel, stop the server, inspect
bounded recovery/unavailable feedback, and check the app's logs for crashes or
credential/frame output. Record device/API and actual results, without serials
or real token capture. No Phase 07 lobby UI or full Phase 14 fault matrix is claimed.

Local JVM tests cover ViewModel StateFlow transitions with a coroutine test
dispatcher, repository connection state, typed decoding, request correlation,
unknown-field compatibility, credential clearing and stale snapshot filtering.
Use fake repositories/data sources with virtual time. Never test a copy of server
physics in Kotlin. Instrumented Compose tests cover create/join validation,
host/non-host lobby actions, station control intent emission, role privacy in
screen state, results and the connection overlay. Test rotation/background/resume
on an emulator or device. Add dependencies when behavior needs them.

Phase 07 adds 13 ViewModel tests, bringing the JVM suite to 43: admission success/
rejection/pending and normalization, retained inputs, duplicate-submit suppression,
explicit reset of uncertain attempts, cancellation, host/non-host gating,
authoritative ready state, disabled-start reasons, recovery, leave and expiry.
Four new Compose tests bring the connected suite to 12 (with the live case enabled).
They verify real screen bindings with controlled repository flows, including
duplicate names keyed by IDs, error-preserving input, leave confirmation and
expiry navigation. Retained shell tests now check live-form validation/restoration
and only the three future previews. The real transport test additionally sends
non-host Start directly through the repository, bypassing the UI guard, and
requires server `not_host`.

Separately run two and three independently installed Android app clients against
one backend. Compare code/roster/host/readiness, join/reset behavior, valid gated
Start, network interruption/resume and explicit leave/rejoin. This session's
user-selected mix is one physical phone plus two emulators, not three physical
phones; record exact observed behavior and limitations in the validation file.

## Multiplayer integration

By Phase 07, connect 2 and 3 real Android clients to one lobby. By Phase 11,
exercise two seeded full rounds with simulated protocol clients and real-phone
victory/defeat/rematch. By Phase 14, interrupt Wi-Fi, kill/recreate an app, replace
a duplicate connection and restart the server. Observe what happens to the host
and other phones; a single-device screenshot cannot prove multiplayer behavior.
Keep local fixtures without real session tokens or personal player names.

## Manual playtests (15)

Record date, build/config version, number of players, seed, setup time, outcome,
confusing controls and actual quotes only with consent. Ask people to explain
their station in their own words. Note communication failures and recoveries,
time spent reading and whether two-station workload is manageable. Do not invent
observations or tune against an imagined preference. A provisional preset can be
ready while human evidence is explicitly pending; leave the phase incomplete.

## Reporting and completion

Record exact commands, pass/fail counts, skipped checks and environment blockers.
Keep a phase checkbox open if a required build or manual gate has not run. A
source inspection is useful evidence, but never label it a successful build.
