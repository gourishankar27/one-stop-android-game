# Verification strategy

Foundation evidence lives in FOUNDATION_VALIDATION.md; Phase 01 model and
regression evidence lives in [DOMAIN_MODEL_VALIDATION.md](DOMAIN_MODEL_VALIDATION.md).
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
The included Compose instrumented test checks that the foundation screen launches.
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
There is no ticking, seeded assignment, scheduling or action execution to test
until its respective phase.

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

Local JVM tests cover ViewModel StateFlow transitions with a coroutine test
dispatcher, repository connection state, typed decoding, request correlation,
unknown-field compatibility, credential clearing and stale snapshot filtering.
Use fake repositories/data sources with virtual time. Never test a copy of server
physics in Kotlin. Instrumented Compose tests cover create/join validation,
host/non-host lobby actions, station control intent emission, role privacy in
screen state, results and the connection overlay. Test rotation/background/resume
on an emulator or device. Add dependencies when behavior needs them.

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
