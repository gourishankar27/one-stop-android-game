# Phase 09 core spaceship gameplay validation

Initial checks: 2026-10-28; verification resumed 2026-10-29.
Scope: complete core controls/physics, mailbox-owned running
simulation, owned Android panels and minimal terminal feedback. No random
emergencies, countdown, Results/rematch flow, public display or sound was added.
The existing uncommitted Phase 06–08 foundation was preserved and extended.

## Dependencies and environment

The master ledger has prerequisites 02, 06 and 08 checked. Observed versions:
Python launcher 3.14.0; backend Python 3.12.10; uv 0.13.6; Temurin JDK 17.0.18;
Android SDK Platform 36 revision 2; Build Tools 35.0.0. Existing Gradle 8.13,
AGP 8.13.2, Kotlin 2.2.21 and Compose BOM 2025.10.01 were retained. Locked
offline sync checked 31 packages. No dependency, toolchain pin or balance default
changed. Engine rules version is now `spaceship-engine-v2`; baseline replay
commands/outcomes remain unchanged with updated version provenance.

Initially the physical phone was unavailable. The user requested emulators for
that run. Three separate read-only API 37 / Android 17 emulator instances were used;
none is counted as a physical phone. Debug clients used emulator host alias
`10.0.2.2:8765` with explicit cleartext opt-in. The local single-process server
bound loopback only. No external service, firewall rule, phone setting or
credential was introduced or changed.

## Automated commands and observed results

At root:

```powershell
python scripts/check_repository.py
git diff --check
```

From `server/`, using configured Python/uv and existing caches:

```powershell
uv sync --locked --extra dev --offline
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src examples
uv build --offline
uv run python examples/lobby_smoke.py --url ws://127.0.0.1:8765/ws
uv run python examples/role_smoke.py --proof ../artifacts/phase09/privacy-proof.json
uv run python examples/gameplay_smoke.py
```

Observed backend results: **973 tests passed**, Ruff lint/format passed (64 Python
files), strict mypy passed (36 source/example files), and source distribution plus
wheel built. The one existing Starlette/httpx TestClient deprecation remains.
The domain isolation test still runs with an empty environment and no web imports.

New tests parameterize every action across briefing/countdown/paused/finished/
aborted, correct/wrong ownership, power rejection and active/cooldown boundaries.
They verify exact cross-station reservations, boost heat/critical damage,
shutdown cancellation with preserved cooldown/evade, combined energy clamping,
empty-shield release, all nine accepted trace kinds and accepted-only deterministic
replay without RNG draws. Existing pure-engine baseline replay outcomes still pass.

Runner tests use fake monotonic time, with no simulated-time sleeps: exact 100ms
steps, 5Hz owned snapshots, correlated accepted/rejected action replies, replay/
monotonic sequence handling, bounded catch-up and overload abort, running pause/
resume without backlog, old-connection fencing, slow outgoing consumer and
noncoalesced terminal state. Shared synthetic `phase09.json` running states and
action ack/rejection round-trip in Python and Kotlin.

Live role and gameplay examples passed separate two-/three-controller rooms.
Role frames passed exact allowlists and owned-only metadata/station keys,
including host privacy. Gameplay exercised all nine controls, insufficient-power
rejection, equal public state at common revisions, private station keys and
shutdown cancellation, then left memberships. The optional privacy proof saves
only field/station names and counts, never raw frames, UUIDs, instructions or
credentials. The lobby example checks admission/ready/non-host rejection,
leave/resume and host transfer without starting gameplay.

From `android/`:

```powershell
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest :app:connectedDebugAndroidTest :app:compileReleaseKotlin '-PoneJobDebugWsUrl=ws://10.0.2.2:8765/ws' '-PoneJobAllowDebugCleartext=true' '-Pandroid.testInstrumentationRunnerArguments.oneJobLiveServer=true' --console=plain
```

Observed: debug build, lint and release Kotlin compilation passed; **61 JVM tests
passed**; **19 instrumented tests passed on each of three emulators** (57
executions, zero failures/errors/skips). The live-server case was enabled. It
performs all nine real actions, power rejection, private-state checks, socket
loss/running resume, stable identity/acknowledgement, and explicit leave abort.
A focused final live-test rerun additionally verifies a newly allocated accepted
action after resume, proving the repository retains sequence across reconnect;
one test passed on each emulator with zero failures/skips:

```powershell
.\gradlew.bat :app:connectedDebugAndroidTest '-PoneJobDebugWsUrl=ws://10.0.2.2:8765/ws' '-PoneJobAllowDebugCleartext=true' '-Pandroid.testInstrumentationRunnerArguments.oneJobLiveServer=true' '-Pandroid.testInstrumentationRunnerArguments.class=com.onejob.game.LiveServerNetworkingTest' --console=plain
```

JVM/UI tests verify own-only controls, typed intent emission, pending guards,
one-in-flight/one-conflated-latest output at at most 10Hz, shutdown discarding old
output, server reconciliation, safe power feedback, inactive-tab instruction
badges, private recovery clearing, frozen client time and server-only outcomes.
No Kotlin test reproduces ship physics. Final lint is **0 errors / 14 retained
warnings**. New resource and Modifier warnings were corrected; retained notices
concern SDK/dependency availability, debug cleartext, backup and foundation icon.
The optional command-line instrumentation flags still produce Gradle's existing
configuration-cache compatibility notice.

## Actual emulator UI control loop

The server was run from root:

```powershell
uv run --project server --locked --offline uvicorn one_job.main:app --host 127.0.0.1 --port 8765 --workers 1 --ws-max-size 16384 --log-config server/logging.json
```

Three independently installed app instances used the normal Create/Join/Ready/
Start/Read/Acknowledge controls. Only synthetic Captain/Crew names were entered.
UIAutomator operated observed app nodes; it did not inject sessions or actions
through a debug UI. Local UI/screenshot evidence is ignored under
`artifacts/phase09/`.

- Two-client session: A owned Engineer+Shields, B Pilot. A opened/read both
  briefings, switched the live station tabs, activated shields/changed facing,
  and requested lower output. Engineer showed accepted output 36/free power 21
  with shield hold; boost visibly rejected for insufficient power. Both clients
  later displayed the authoritative “Survived together” terminal summary. The
  window ended before that attempt's output-raise step; it is not claimed as
  successful two-client evade acceptance. The two-client live transport test and
  separate gameplay example cover every accepted action.
- Fresh three-client session: A owned Shields, B Pilot, C Engineer. Each showed
  exactly one owned station, including the host. All acknowledged through UI and
  entered running. Engineer lowered output to 36. Shields activated, faced left
  and recharged; the Engineer screenshot shows free power 1 while hold/recharge
  reserved 35. Engine boost and Pilot evade visibly rejected for power.
- Engineer then raised accepted output to 99 through the slider. Pilot moved
  left and successfully evaded; the screenshot shows accepted feedback and the
  server cooldown. Shields boosted and displayed increasing exact energy/left
  facing. Engineer used boost/coolant, then shutdown; its confirmed snapshot
  showed output/free power 0. These are actual UI actions and server feedback,
  not claims about a human party playtest or balance.
- Pilot and Shields captures both show 70 seconds, hull 100% and shield 80%,
  while retaining different private panels. The independent socket check also
  compares exact public state at matching revisions and station-key privacy.
- All three reached the server's 90-second victory with identical time 0,
  hull 100%, shield 78% and “Survived together.” No client opened the Results
  preview or invented an outcome. Each confirmed Leave and returned Home.
  App-PID-only log scans found no crash/ANR or token/raw-payload markers. Own
  device temporary XML/PNG files were removed.

Inspected captures include `three-engineer-pressure.png`,
`three-pilot-accepted.png`, `three-shield-accepted.png`,
`three-engineer-stopped.png` and the three terminal captures. Source privacy
evidence remains the committed sentinel/allowlist tests and synthetic fixture;
no raw private transport projection is committed.

## Corrections, pending gate and handoff

On 2026-10-29 the Phase 08 foundation was present in commit `49c9937`; Phase 09
changes remained in the working tree and were preserved. Locked sync, all 973
backend tests, Ruff/format, strict mypy, Android debug build/lint/JVM checks and
release Kotlin compilation were rerun successfully. Gradle reused the unchanged
JVM/release artifacts; the 61-test JVM and connected-device counts above are from
the passing 2026-10-28 executions. No connected test was claimed on 2026-10-29.
Repository/whitespace checks
passed and the ledger remained unchanged. No Android device was connected at
the start of this continuation, and the user confirmed that the phone was still
unavailable. The prior verification server port was closed
and the three owned emulators had been stopped; manual memberships were left.

Initial old feature-unavailable/held-briefing test expectations and replay version
tags were updated for the intended Phase 09 transition. Dynamic replacement
typing/format issues were corrected. The first role smoke waited for ordinary
error rather than the new action_rejected and timed out; its corrected run
passed. The first connected UI run had two substring assertions written as exact
text matching on each emulator; corrected assertions passed. An early manual
briefing timed out while the harness was idle; a fresh coordinated session read/
acknowledged within the deadline. These resolved verification failures are not
remaining code blockers.

ADR-018 records exact duration/energy semantics, unchanged defaults, engine v2,
the existing-mailbox runner, overload policy, monotonic attempts, bounded slider
intents and minimal terminal UI. Contracts, DTOs, fixtures, API/UI notes and setup
documentation were updated together.

The phone became available later on 2026-10-29. The user explicitly requested
closing Phase 09 and then implementing Phase 10. The previously approved device
mix (one physical phone and two emulators) was used; this is not three phones.
The phone runs Android 16 / API 36 on the same trusted Wi-Fi as the PC. A debug
LAN endpoint and cleartext opt-in were configured locally. The disposable server
bound `0.0.0.0:8765`, one worker; no firewall or external service was changed.

The complete backend commands above ran again: 973 passed, Ruff/format/strict
mypy passed, wheel/sdist and repository/whitespace checks passed. Android debug,
test APK, lint, 61 JVM tests and release compilation passed with 14 retained lint
warnings. `:app:connectedDebugAndroidTest` with the LAN endpoint and
`oneJobLiveServer=true` passed all 19 tests on the phone and first emulator.
The second emulator finished booting after Gradle enumerated devices; its same
test APK was installed with `adb install -r`, then
`adb shell am instrument -w -r -e oneJobLiveServer true com.onejob.game.test/androidx.test.runner.AndroidJUnitRunner`
passed all 19 tests. Thus there are 57 passing instrumented executions in this
continuation, including live all-nine-action, rejection, private recovery and
post-resume sequence checks on every device. Live two-/three-controller role
allowlists and gameplay socket examples passed again.

Normal UI Create/Join/Ready/Start/read/acknowledge was used for fresh two- and
three-client sessions. The real phone owned Pilot. In two-client mode the other
client explicitly read and switched Engineer/Shields. Shields activated, faced
left and recharged; low output gave visible Pilot and Engineer power rejection.
Shutdown was accepted and both screens reached time zero/hull 100%/shields 40%
with the same authoritative victory. The first harness tapped the slider's far
edge without changing output; that attempt does not count as accepted evade.
Its initial Leave-label mismatch was corrected and both memberships were left.

In the fresh three-client session the phone owned only Pilot, the first emulator
only Shields and the second only Engineer, including host privacy. Output 36,
left-facing active shields/recharge and power rejection were observed. A corrected
interior slider tap raised accepted output to 91. On the phone, move-left and
evade then received accepted feedback with a server cooldown (inspected capture
`phone-3-0-evade-accepted.png`). Engineer coolant and shutdown were accepted;
accepted output/free power became zero. All three public hull values stayed
100%; after shutdown their shield percentage agreed at 33%. Exact common-revision
public equality and private allowlists also passed the independent socket checks.
App-only log scans on all three devices found zero crash/ANR or private-payload
markers. Captures and the disposable UI driver remain ignored in `artifacts/phase09/`.
All three then reached time zero/hull 100%/shields 33% with “Survived together”;
the driver confirmed Leave through the normal UI on every client.

The real-phone gate is now satisfied using the user-approved device mix. No
required Phase 09 code/toolchain/test gate remains blocked. The ledger can close
Phase 09; Phase 10 is explicitly authorized by the user's latest instruction.

API 26, WSS infrastructure, three physical phones, TalkBack and the broader
background/process-death matrix were not tested here. Credentials intentionally
remain memory-only. No new production service or dependency was added. Phase 10
emergencies and Phase 11 countdown/results/rematch remain unimplemented.
