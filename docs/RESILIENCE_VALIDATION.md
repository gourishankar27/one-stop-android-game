# Resilience and reconnection validation

Observed 2026-10-29 on Windows. This is evidence, not a second progress ledger.
Phase 14 remains unchecked in `plans/plans.md`: its required physical 2/3-phone
fault matrix has not run. The user's earlier phone/human deferrals remain in
force. Phase 11 is implemented but its manual completion gate remains open;
the user explicitly selected Phase 14. Implemented optional Phases 12/13 were
preserved and included. No Phase 15 work was started.

## Scope and implementation

The [interruption matrix](INTERRUPTION_MATRIX.md) and
[ADR-023](DECISIONS.md#adr-023--process-safe-recovery-without-action-replay) were
written before coding. Existing room ownership, fixed steps, generation fencing,
stable credentials, 30-second monotonic grace, pause/abort/host-transfer and
public/owned projections were retained.

- Android persists only endpoint/token/expected identity and membership kind,
  using AtomicFile in UID-private noBackupFilesDir. Explicit legacy backup and
  cloud/device-transfer exclusions were added. No projection, action queue or
  credential enters UI saved state, routes or logs. Records are bounded; malformed,
  incompatible, mismatched or unreadable records cannot auto-admit and produce
  local feedback. Leave/disconnect/expiry remove records; process disposal keeps
  them. Read/write/removal failures drop private controls and expose a storage
  error rather than silently claiming persistence or deletion succeeded.
- Non-configuration Activity stop suspends socket/heartbeat/retry and discards
  controls/input. Start resumes within the existing absolute recovery deadline;
  production uses elapsedRealtime so sleep counts. Lifecycle changes are
  conflated into the existing bounded owner channel. Rotation keeps the app owner.
- Full private snapshots carry only the recipient's consumed action sequence.
  Both codecs/fixtures and the private smoke allowlist were updated. Signed
  64-bit bounds prevent a Python-only sequence from exceeding Android's range.
  The client merges its local/server high-water marks and never replays actions.
- A live test exposed equal-revision snapshot filtering after rejected actions:
  the sequence can advance without a ship mutation. Correlated full owned
  snapshots now refresh equal revisions. Older revisions, unsolicited duplicates,
  retired rounds and old socket generations remain fenced.
- Recovery retains safe Retry/Leave UI and silent feedback baselines. Expiry/
  missing-session text explains a possible server restart and asks for rejoin.
  Display recovery stays public-only and never pauses controllers.

## Dependencies and commands

Toolchain observed: launcher Python 3.14.0, server Python 3.12.10, uv 0.13.6,
Temurin JDK 17.0.18+8, SDK Platform 36 revision 2 and Build Tools 35.0.0.
Existing Gradle 8.13 / AGP 8.13.2 / Kotlin 2.2.21 / Compose BOM 2025.10.01 pins
were retained. No dependency was added. Disposable API 37 emulators were used;
no phone was installed, launched or controlled.

Commands below ran, with process-local environment set by the existing ignored
`artifacts/foundation/environment.ps1`. uv used the existing warmed development
cache; packaging used its ordinary local cache. No machine configuration changed.

| Location | Exact command | Observed result |
| --- | --- | --- |
| Root | `python scripts/check_repository.py` | Pass: phase/link/package/XML/wrapper checks |
| server | `uv sync --locked --extra dev` | Pass, locked environment retained |
| server | `uv run pytest` | 1,113 passed, one upstream Starlette/httpx deprecation warning |
| server | `uv run ruff check .` | Pass |
| server | `uv run ruff format --check .` | Pass, 80 files |
| server | `uv run mypy src` | Pass, 33 source files |
| server | `uv run mypy src examples` | Pass, 42 files |
| server | `uv build --no-sources` | Pass, sdist and wheel |
| server | `uv run python examples/role_smoke.py --proof ../artifacts/phase14/role-proof.json` | Pass: 2/3 controllers, private field allowlists, ownership, acknowledgement/countdown/running |
| android | `./gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest` with the properties below | Pass; 96 JVM tests, zero failures/skips; lint zero errors, 13 retained warnings |
| android | `./gradlew.bat :app:connectedDebugAndroidTest` with live-server property below | All 39 tests passed on each of two API 37 emulators: 78 executions, zero skips |
| android | Same gates plus selected `LiveServerResilienceTest,SessionStorageTest` after final storage-error refinements | Four tests per emulator; full JVM/build/lint gates rerun |

Android properties (quoted as individual arguments in PowerShell):

```text
-PoneJobDebugWsUrl=ws://10.0.2.2:8765/ws
-PoneJobAllowDebugCleartext=true
-Pandroid.testInstrumentationRunnerArguments.oneJobLiveServer=true
```

The full instrumented run used the default single-process local harness:
`uv run --offline python examples/emergency_harness.py --seed 71 --profile default --host 127.0.0.1`
(the equivalent locked-environment Python entry point was launched hidden).
Emulators were selected explicitly through ANDROID_SERIAL; no unselected device
was eligible. The selected rerun adds the quoted argument
`-Pandroid.testInstrumentationRunnerArguments.class=com.onejob.game.LiveServerResilienceTest,com.onejob.game.SessionStorageTest`.

An initial command needed quoting for the dotted Gradle runner property. Initial
Ruff checks found a loop-lambda binding/format issue, subsequently fixed. The
first instrumented run found the equal-revision bug and an old hard-coded expiry
copy assertion; both were corrected and the complete two-emulator suite passed.
No failed attempt is counted as a pass. Final storage refinements add explicit
corrupt-record and removal-failure reporting; the focused live/storage suite and
full JVM/build/lint gates were repeated after those changes.

## Fault evidence

New server tests cover 2/3 controllers, host/non-host, briefing/countdown/running,
29-second freeze/resume and exact 30-second expiry/abort/removal/connected-host
transfer. With one survivor rematch is rejected and return to lobby succeeds.
Concurrent takeover tests repeat 20 two-resumer races per count, fence queued old
actions and disconnects, preserve private sequence/request-cache outcomes and
check binding/session/task cleanup. A fresh registry cannot restore old-process
credentials. Existing fake-clock watchdog, slow-outbox, overload, display,
stale-round, terminal and shutdown coverage also ran. No simulation-time sleeps.

Android virtual-time cases cover process-owner replacement, full-snapshot gating,
authoritative sequence restoration, equal-revision refresh, uncertain-action
discard, background transport suspension, unchanged absolute grace, expired/
superseded controller/display records, endpoint mismatch and read/write/removal
failure, 25 repeated recovery cycles and late callback rejection. Existing
backoff, queue bounds, action receipts, public display and feedback tests ran.
Instrumented tests exercise actual AtomicFile recovery/corruption and backup XML,
plus real sockets with fresh storage owners for 2/3-controller, display and missed
terminal-event recovery.

## Emulator UI observations and remaining manual gates

Three ordinary app instances were launched on the owned emulators. A CLI driver
operated visible UI nodes, with the existing `verification` harness profile
(120-second windows/lower damage, not a balance claim):

- Two clients: actual Home/background closed the host connection; the peer
  displayed paused controls/time. Returning resumed owned gameplay. Force-stop/
  reopen restored gameplay without joining again. A second force-stop lasting
  31 seconds produced **Round aborted** for the survivor; the old host reopened
  at Home with the expiry/possible-restart explanation.
- Three clients: background and actual force-stop/reopen restored owned gameplay;
  peers displayed pause. Abruptly restarting the in-memory server then returned
  all three clients to Home with the rejoin explanation.
- In a separate ordinary lobby, rotating to landscape retained the same room and
  ready state (the **Not ready** button remained, meaning the player was ready).
  Wi-Fi was disabled for 18 seconds then restored. The same room recovered and
  the button became **Ready up**, consistent with server readiness reset on
  resume. No disconnected state was visible at the 18-second UI sample. This
  does not establish an uninterrupted outage, timing or active-round peer pause:
  an emulator can have another route. It is not a physical Wi-Fi pass. Rotation
  and Wi-Fi settings were restored.

Ignored `artifacts/phase14/` holds masked summaries, UI screenshots, test reports
and command logs. It contains no exported credential or raw network projection
proof. UI evidence uses synthetic local rooms. Test servers/emulators and changed
device settings are cleaned up; no system-wide ADB restart or phone operation.

**Required and still unrun:** on 2 and 3 physical phones, brief and beyond-grace
Wi-Fi interruption, background suspension, process kill/reopen, duplicate session
and server restart; repeat for host and non-host, recording peer stage/roster/
outcome/explanation. Emulator and fake-clock evidence cannot close these gates.
Earlier phone, human coordination, perceptual audio/haptics and accessibility
gates remain deferred. API 26/OEM/device-transfer behavior was not exercised.

If the filesystem refuses removal, software cannot claim the old token file was
erased: the app drops in-memory membership and reports the failure. Server grace/
expiry remains authoritative. There is no offline authority, persistent server
recovery, hidden host migration or automatic business-command replay.

The master ledger is intentionally byte-for-byte unchanged. Finish required
physical and earlier deferred gates before claiming completion; Phase 15 group
playtesting/tuning needs a separate instruction.
