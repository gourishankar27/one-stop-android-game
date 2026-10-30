# Round lifecycle validation

Observed on 2026-10-29 (America/Phoenix). This records Phase 11 evidence, not a
replacement progress ledger. The existing Phase 09/10 working tree was preserved.
The user selected Phase 11 and explicitly deferred physical-phone testing;
ADR-020 records proceeding while Phase 10's human playtest prerequisite remains
open. Phase 11's master-plan checkbox remains open pending its real-phone gate.

## Implemented boundary

Briefing completion enters a server-owned 3000ms countdown through the existing
100ms room runner. Preparation consumes no gameplay time, resources, cooldowns,
emergencies or RNG; disconnect freezes preparation and resume discards paused
wall time. Running retains the existing 90-second default, 60–120-second supported
duration, seeded difficulty thirds and hull-before-timer terminal precedence.
There are no running-physics/config/replay-version changes.

Every terminal cause retains one stable public result and emits one critical
`game_over` to each connected member. Countdown/Results navigation uses matching
full snapshots, including after recovery. Explicit terminal readiness permits
host Play again; fresh context/UUID/seed/assignments replace all old round state.
Return to lobby clears the round and readiness while preserving room/membership.
Old private state-request cache entries and Android views/input queues are retired.
Only the last round ID/seed is retained, with bounded collision retries.

No Phase 12 display, Phase 13 audio, deployment or Phase 14 fault matrix was added.
No phone was installed, launched or operated during this validation.

## Dependencies and toolchains

The existing toolchain/dependency pins were retained; no dependency was added.

| Check | Observed |
| --- | --- |
| `python --version` | Launcher Python 3.14.0 |
| `server/.venv/Scripts/python.exe --version` | Backend Python 3.12.10 |
| `uv --version` | uv 0.13.6 |
| `java -version` | Temurin JDK 17.0.18+8 |
| `android/gradlew.bat --version` | Gradle 8.13; launcher/daemon use Java 17 |
| SDK package metadata | Platform 36 revision 2; Build Tools 35.0.0 |
| Android build pins | AGP 8.13.2, project Kotlin 2.2.21, Compose BOM 2025.10.01 |
| `uv sync --locked --extra dev` | 31 packages resolved/checked; lock retained |
| `:app:dependencies --configuration debugRuntimeClasspath` | Successful dependency report |

Commands sourced the existing ignored `artifacts/foundation/environment.ps1`.
Backend sync/run used the existing `artifacts/phase04/uv-cache`; `uv build` used
the normal local uv cache. These are process-local settings, not committed paths.
The Kotlin version printed inside Gradle's own version banner is its embedded
Kotlin, distinct from the project's Kotlin plugin.

## Automated checks

From root, `python scripts/check_repository.py` passed all 19 phase briefs,
local links, package/XML and wrapper structure. `git diff --check` exited 0;
only the existing Windows line-ending conversion warnings were emitted. The
master-plan hash matches its initial value for this phase.

From `server/`, the final observed commands were:

```powershell
uv sync --locked --extra dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run mypy examples
uv build
```

Results: **1,036 tests passed**, Ruff check/format passed (76 Python files), mypy
passed for 33 source and 8 example files. Both
`one_job_server-0.1.0.tar.gz` and `one_job_server-0.1.0-py3-none-any.whl` built.
The existing Starlette/httpx deprecation warning remains; no test is skipped.

Coverage includes exact countdown boundaries, invalid deltas, pause/no RNG,
countdown overload, existing timer/hull tie and emergency thirds, host/readiness
gates, one result event, terminal resume, full replacement, bounded seed/ID
collisions, stale actions/briefing/state-request IDs and return-to-lobby.
Thirty victory/defeat/briefing-abort cycles in each 2/3-player room (60 cycles)
keep membership/room identity stable, runner stopped at terminal, mailbox empty,
reply caches at most 128, clock waiters at most one and owned tasks at most three.
The registry closes without owned tasks remaining. Existing engine/replay and
private-projection regressions continue passing.

From `android/`:

```powershell
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest :app:compileReleaseKotlin `
  '-PoneJobDebugWsUrl=ws://10.0.2.2:8765/ws' '-PoneJobAllowDebugCleartext=true' --console=plain
```

Build/debug lint/JVM tests/release Kotlin compile passed. XML reports contain
**70 JVM tests, zero failures/errors/skips**. Final lint has **0 errors and 14
existing warnings**: dependency/tool/target update hints, opt-in debug cleartext,
backup metadata and missing application icon. Two obsolete preview strings were
removed after the initial lint run; no new warning remains.

With a one-process localhost server running, instrumentation was restricted to
the three owned emulators, explicitly excluding physical devices:

```powershell
$env:ANDROID_SERIAL = 'emulator-5586,emulator-5588,emulator-5590'
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest :app:compileReleaseKotlin `
  :app:connectedDebugAndroidTest '-PoneJobDebugWsUrl=ws://10.0.2.2:8765/ws' `
  '-PoneJobAllowDebugCleartext=true' `
  '-Pandroid.testInstrumentationRunnerArguments.oneJobLiveServer=true' --console=plain
```

All **27 tests on each emulator passed (81 executions), zero skips/failures**,
including the opt-in real-server networking test. Devices used Android 17/API 37,
the available Medium Phone AVD; the app compiles against Platform 36. The suite
covers authoritative countdown/pause/navigation, result recovery without a
one-shot event, terminal readiness/host controls, two rematches, lobby reset,
briefing abort and existing shell/lobby/private-control/networking behavior.
An earlier run failed the old briefing-abort UI expectation on all three devices;
that expectation was updated to the new authoritative Results route and the full
suite rerun passed. A transient explicit import of a Compose assertion member was
also corrected before the successful instrumentation build.

## Real-socket integration

The normal server was exercised using a single worker at `127.0.0.1:8765` with
the configured 16 KiB WebSocket limit and allowlisted logging. The seeded harness
uses the same application/transport/engine; no authentication or rule bypass is
available through its network endpoint. Seeds increment locally per round.

From `server/`, against:

```powershell
uv run --offline python examples/emergency_harness.py --seed 71 --profile default --host 127.0.0.1
```

Ran:

```powershell
uv run --offline python examples/role_smoke.py --url ws://127.0.0.1:8765/ws
uv run --offline python examples/gameplay_smoke.py --url ws://127.0.0.1:8765/ws
uv run --offline python examples/emergency_smoke.py --url ws://127.0.0.1:8765/ws
```

Both 2/3-client role checks passed owned allowlists, ownership, all acknowledgements,
observed countdown and running tick zero. Both control checks passed all nine
actions, power rejection, synchronized private/public views and shutdown. Normal
90-second emergency rounds completed with matching victories: 2 clients resolved
13/failed 0, 3 clients resolved 11/failed 1; no duplicate emergency transitions.
The seed factory started at 71 and advanced across these checks; it was not reset
between rooms. These scripted controllers do not count as human coordination.

Then restarted the harness with the explicit verification profile:

```powershell
uv run --offline python examples/emergency_harness.py --seed 71 --profile lifecycle --host 127.0.0.1
uv run --offline python examples/round_lifecycle_smoke.py --url ws://127.0.0.1:8765/ws
```

`lifecycle` overrides only `round_duration_ms=60000` and
`emergencies_enabled=False`, preserving other rules and production defaults.
Two concurrent 2/3-client rooms each completed three full 60-second victories,
two rematches, exactly one matching `game_over` per round/recipient, stable restored
results, countdown disconnect/resume, fresh round IDs/action sequence 1, rejection
of old-round commands and return to the same lobby with readiness cleared.
All clients explicitly left. This checks lifecycle in a quiet test configuration;
the preceding integration retained normal emergencies and duration.

## Observed emulator UI

The debug APK was explicitly installed/launched on owned emulators only. Ordinary
Create/Join, Ready, Start, station/read/acknowledgement, Results and host buttons
were driven through observed One Job UI nodes; no session/transport injection was
used. After AGP removed test APKs, the first UI launch found the app absent;
explicit installation resolved that setup issue before the successful UI run.

With the lifecycle profile above, the three-emulator room completed three rounds
and two normal-UI rematches. All three showed server countdown `2` on each cycle,
then matching Results: survived together, 60 seconds, 100% final hull, resolved 0,
failed 0. Fresh station/read acknowledgements were required each time. Play again
was disabled before readiness. After all readied at the final result, host Return
to lobby restored the same code and all Ready-up buttons, proving readiness reset.
All members used confirmed Leave. The Results screenshot was visually inspected;
outcome, totals, roster and reachable ready/host controls were legible.

A separate two-emulator normal-UI room completed its full 60-second victory too.
Pilot and the Engineer+Shields player read/acknowledged their own station sets;
both showed countdown `2`, then matching 60-second/100%-hull/0-resolved/0-failed
Results. Both readied at Results, host returned to the same lobby, readiness
reset and both confirmed Leave. The two-rematch UI sequence was run in the
three-emulator room; the two-client rematches also passed the real-socket check.

Local synthetic screenshots/UI captures and sanitized summaries are ignored under
`artifacts/phase11/`; no raw private projections or credentials are committed.
The UI helper was restricted to the session's emulator serials. This
scripted inspection is not a real-phone or human group playtest.

After all scripted members left, the owned verification server was stopped and
port 8765 had no listener. The three session-owned emulators were quit; their
launcher processes exited and each emulator serial was absent from ADB. No
other device or pre-existing service was stopped.

## Remaining gates and handoff

Physical-phone testing is deferred by the user's explicit instruction. The Phase
11 real-phone two-/three-player lobby → briefing → countdown → win/loss → matching
Results → two rematches → lobby readiness reset → short interruption/recovery
manual gate has **not** been run this phase. Emulator/socket checks do not close it.
Phase 10's human aloud-coordination/two-/three-player playtest gate also remains
pending by the earlier instruction. Balance/fun, full Phase 14 resilience and
Phase 15 human playtesting are not claimed.

`plans/plans.md` was not edited during Phase 11; its initial and final SHA-256
match. Its existing Phase 09/10 work was retained, and Phase 11 stays unchecked.
Finish the deferred validation before marking completion. Optional Phase 12/13
and MVP-critical Phase 14/15 require a new instruction; no later phase was started.
