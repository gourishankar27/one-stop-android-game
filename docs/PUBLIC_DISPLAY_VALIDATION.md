# Public display validation

Observed 2026-10-29 (America/Phoenix), starting at commit `b7afd5d` with a clean
working tree. Its title mentions Public Display, but `join_display` was still
reserved and observer membership was absent. The implemented foundation and
Phases 09–11 were preserved. The user explicitly selected Phase 12 while physical
phone testing remains deferred; Phase 10's human and Phase 11's phone gates remain
open. ADR-021 records this dependency discrepancy and the observer boundaries.

An unrelated `plans/START_HERE.md` prompt edit appeared during implementation; it
was left untouched. The selected phase brief and master ledger were not edited.

## Delivered boundary

Two distinct display sessions per room, including disconnected seats during
30-second grace, can join any stage. They have their own credentials/internal
identities, `kind=display`, `player_id=null`, no player slot/role/ready/host, and
only ping/state/resume/leave permissions. Generation fencing, bounded replay and
digest-only indexes reuse the existing session machinery. Their lifecycle never
pauses gameplay, resets player readiness, changes host/revision or extends idle
time. A room without controllers expires its displays and their credentials.

Displays receive public lobby and independently allowlisted public round/result
snapshots, never player projections or one-shot gameplay events. Explicit
`public:null` means no round in lobby; terminal public snapshots are critical.
New rounds/lobby return clear obsolete cached state replies. No domain/rule,
configuration/replay-version, dependency, TV/casting, audio or later-phase change
was made.

Android has code-only Join display and a dedicated public-only ViewModel/screen.
Membership kind drives routing; repository guards reject control intents and
private inbound messages. Recovery clears old data and requires correlated public
synchronization. Large shared totals, public warnings/results and public roster/
readiness scroll and adapt to wider screens. No local simulation/clock, private
station widgets, settings or animation was introduced.

## Toolchains and dependencies

| Check | Observed |
| --- | --- |
| `python --version` | Launcher 3.14.0 |
| `server/.venv/Scripts/python.exe --version` | Backend 3.12.10 |
| `uv --version` | 0.13.6 |
| `java -version` | Temurin 17.0.18+8 |
| `android/gradlew.bat --version` | Gradle 8.13; Java 17 launcher/daemon |
| SDK `source.properties` | Platform 36 revision 2, Build Tools 35.0.0 installed |
| Existing Android pins | AGP 8.13.2, Kotlin/Compose compiler 2.2.21, Compose BOM 2025.10.01 |
| `uv sync --locked --extra dev` | 31 packages resolved/checked; lock unchanged |

Commands sourced ignored `artifacts/foundation/environment.ps1`. Backend sync/run
used the existing `artifacts/phase04/uv-cache`; package build used the normal local
uv cache. These settings were process-local. Dependency manifests/locks and Android
build pins are unchanged. No new package was needed.

## Required automated checks

From root, `python scripts/check_repository.py` passed all 19 phase briefs,
local links, package/XML and wrapper structure. `git diff --check` exited 0;
existing Windows line-ending conversion warnings are nonblocking. Ignore checks
confirmed local configuration, artifacts, APKs and package outputs stay excluded.

From `server/`:

```powershell
uv sync --locked --extra dev
uv run pytest -q --tb=short
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run mypy examples
uv build
```

**1,080 tests passed, no skips/failures.** Ruff check/format passed for 79 Python
files; mypy passed for 33 source and 9 example files. Wheel and sdist built:
`one_job_server-0.1.0-py3-none-any.whl` and `one_job_server-0.1.0.tar.gz`.
One existing Starlette/httpx deprecation warning remains.

New coverage includes admission at all seven stages with 2/3 controllers, secret
sentinels and exact public allowlists, every controller command including all
nine actions, independent 3-player-plus-2-display capacity, reserved grace seats,
duplicate-connection fencing, unchanged readiness/host/revision/deadlines,
unpaused countdown/running, terminal/lobby cache reset, idle/room expiry and
critical terminal/null-lobby outbox behavior. Shared synthetic Phase 12 fixtures
round-trip through both Python and Kotlin, including strict membership kind/null
identity and code-only payloads. Existing domain/replay/lifecycle tests still pass.

From `android/`:

```powershell
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest :app:compileReleaseKotlin `
  '-PoneJobDebugWsUrl=ws://10.0.2.2:8765/ws' '-PoneJobAllowDebugCleartext=true' --console=plain
```

Debug package/lint/JVM tests and release Kotlin compile passed. JUnit XML contains
**76 JVM tests, zero failures/errors/skips**. Final lint has **0 errors and 14
retained warnings** (dependency/tool/target update hints, opt-in debug cleartext,
backup metadata and missing icon); no new warning was suppressed.

Against the single-process default local server, restricted to owned emulators:

```powershell
$env:ANDROID_SERIAL = 'emulator-5586,emulator-5588,emulator-5590'
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest :app:compileReleaseKotlin `
  :app:connectedDebugAndroidTest '-PoneJobDebugWsUrl=ws://10.0.2.2:8765/ws' `
  '-PoneJobAllowDebugCleartext=true' `
  '-Pandroid.testInstrumentationRunnerArguments.oneJobLiveServer=true' --console=plain
```

All **31 tests on each of three API 37/Android 17 emulators passed (93 executions),
zero skips/failures**, including both opt-in real-server tests. The display test
joins in lobby/running, checks capacity, interrupts/reconnects an observer while
players advance, restores public-only state, and observes room-deletion expiry.
Compose tests cover code-only admission, hidden controls/private sentinel, server
countdown without a local clock, warnings/results, recovery and confirmed leave.

After the final label/roster-readiness adjustments, the three display UI tests and
live display test were rerun on the tablet-sized emulator at font scale 1.5:

```powershell
$env:ANDROID_SERIAL = 'emulator-5590'
.\gradlew.bat :app:connectedDebugAndroidTest '-PoneJobDebugWsUrl=ws://10.0.2.2:8765/ws' `
  '-PoneJobAllowDebugCleartext=true' `
  '-Pandroid.testInstrumentationRunnerArguments.oneJobLiveServer=true' `
  '-Pandroid.testInstrumentationRunnerArguments.class=com.onejob.game.DisplayUiTest,com.onejob.game.LiveServerDisplayTest' --console=plain
```

**4/4 passed, no skips/failures** (97 total observed instrumentation executions).
The full-suite log and count summary were retained in ignored
`artifacts/phase12/android-connected.log` and `full-instrumentation-summary.json`;
the latest build report contains the separate four-test tablet run.

Initial resolved checks: old reserved-command tests were updated to typed display
admission while preserving UTF-8 size/admission deadline checks; one existing
navigation test needed an explicit nonnull player ID; fixture validation now uses
JSON mode for strict tuple fields. Final checks above passed after these fixes.

## Real-socket privacy and recovery

From `server/`, one worker at localhost with normal production game defaults:

```powershell
uv run --offline python examples/emergency_harness.py --seed 71 --profile default --host 127.0.0.1
uv run --offline python examples/display_smoke.py
```

The local seed factory starts at 71 and increments across rounds; no client
seed/config bypass exists. The app/engine/transport and 90-second default remain
normal. Two concurrent rooms with 2/3 players each and two displays passed:
lobby and running admission, independent capacity, exact incoming message/public
field allowlists, shared-state equality at matching revisions, crafted ready/
start/action denial, display disconnect while player ticks continue, credential
resume, warning observation and matching terminal defeat. Controllers deliberately
observed without responding to hazards; defeat is the game outcome, not a failed
check. Both displays and every player explicitly left. No raw frame, credential,
private target or station data was exported by the script.

## Normal emulator UI and tablet layout

The final debug APK was installed explicitly on the three owned emulators after
instrumentation. Ordinary UI nodes drove two controller apps and one public display
app. The display joined in lobby with code only, showed the roster, then watched
the running round. Confirmed display Leave returned Home while controller time
continued without a pause. Rejoining through the form during running restored
shared data, showed an actual Asteroid approach warning and ended with the same
Ship lost result and resolved=4/failed=4 counts as both players. All confirmed Leave.
This form rejoin is fresh admission; credential recovery is proven separately by
the real-socket and Android networking tests above.

The display emulator used these temporary settings:

```powershell
adb -s emulator-5590 shell wm size 1600x2560
adb -s emulator-5590 shell wm density 240
adb -s emulator-5590 shell settings put system font_scale 1.5
adb -s emulator-5590 shell settings put system accelerometer_rotation 0
adb -s emulator-5590 shell settings put system user_rotation 1
```

Portrait and landscape screenshots were visually inspected: large public totals,
warning, roster and Leave were readable within insets, with no station controls.
Rotation retained the same room/session. Phone-sized Compose tests exercise the
stacked layout; tablet tests exercise the wider layout. No viewing-distance,
physical-tablet or broad compatibility claim is made. Original settings were
1080x2400, density 420, font 1.0, accelerometer rotation 1 and user rotation 0.
Local screenshots/XML/sanitized summaries are ignored under `artifacts/phase12/`.

After validation all test memberships were left/closed, tablet settings were
restored and verified (1080x2400, density 420, font 1.0, original rotation).
The owned server was stopped; port 8765 had no listener. All three owned emulator
launchers exited and their serials were absent from ADB. The physical phone and
other existing services were not operated or stopped.

## Remaining gates and handoff

The physical-phone/tablet part remains deferred by the user. Joining an actual
extra physical Android device during lobby/running, checking shared-screen
readability and its disconnect/recovery has not been run this phase. Emulator
resizing is layout evidence, not physical-tablet evidence. Phase 10's human
coordination and Phase 11's physical-phone loop gates also remain open.

`plans/plans.md` remains unchanged this phase (initial/final SHA-256 match) and
Phase 12 is unchecked. No later phase was started. Finish deferred validation
before completion; optional Phase 13 is separate, and Phase 14 remains the next
MVP resilience step without requiring TV/casting or this optional display.
