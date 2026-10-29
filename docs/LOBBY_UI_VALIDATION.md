# Lobby UI validation — 2026-10-28

Phase 07 builds on the existing Phase 06 delivery, which was still uncommitted
at session start (`fa855a5` HEAD). That work was preserved. AGENTS.md, the master
plan, selected brief, foundation validation, state/protocol and UI architecture
were read first. Phases 04 and 06 were already complete in the ledger. No backend
production code, domain rule, wire DTO, dependency pin or gameplay changed.

## Environment and automated checks

Observed: Python launcher 3.14.0; backend Python 3.12.10; uv 0.13.6; Temurin
17.0.18; Gradle 8.13 with Java 17 launcher/daemon; SDK Platform 36 revision 2 and
Build Tools 35.0.0. The existing AGP 8.13.2/Kotlin 2.2.21/Compose baseline was
retained. No new dependency was needed. The existing phone plus two emulators
was explicitly selected by the user for the multi-client gate.

| Check | Actual result |
| --- | --- |
| `uv sync --locked --extra dev --offline` in `server/` | Passed, 31 locked packages checked |
| `uv run pytest` | 852 passed, one existing TestClient deprecation warning |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | 51 files already formatted |
| `uv run mypy src` | Passed, 26 source files |
| `uv build --offline` | Wheel and source distribution built |
| `gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest` | Passed; final JVM count 43; lint 0 errors, 14 retained warnings |
| `gradlew.bat :app:connectedDebugAndroidTest :app:compileReleaseKotlin` with LAN/live-test flags below | Passed; 12 tests per device on all three devices, zero skips/failures; release Kotlin compiled |
| `git -c core.safecrlf=false diff --check` | Passed |
| `python scripts/check_repository.py` from root | Passed |

The Android connected command from `android/` was:

```powershell
.\gradlew.bat :app:connectedDebugAndroidTest :app:compileReleaseKotlin '-PoneJobDebugWsUrl=ws://192.168.12.61:8765/ws' '-PoneJobAllowDebugCleartext=true' '-Pandroid.testInstrumentationRunnerArguments.oneJobLiveServer=true' --console=plain
```

Debug assembly/lint/JVM checks were also run with those endpoint/cleartext flags,
and once with the default empty endpoint. The final offline-leave presentation
refinement and obsolete-resource cleanup passed the 43-test JVM suite and lint.
The final source also passed all 12 connected tests and release Kotlin compilation
again on the second emulator without operating the temporarily unavailable phone.
Installed Android tools required narrow sandbox escalation, as in the previous
phase; all commands executed successfully. Backend locked sync used the existing
ignored workspace uv cache and package building used the existing user cache.

Devices: Samsung SM-S721U1 / Android 16 API 36, and two separately running
read-only instances of the existing Medium Phone AVD / Android 17 API 37 x86_64.
This is one physical phone and two emulators, not three physical phones.
Serials and real credentials are omitted. Reports remain under ignored
`android/app/build/reports/`, `build/test-results/` and Android test outputs.

The 13 new ViewModel tests cover normalized admission, retained rejected inputs,
pending/duplicate submit, identity-gated success, explicit reset after uncertainty,
cancelled admission cleanup, host/server eligibility, duplicate names, authoritative
readiness, recovery, leave, expiry and late-result fencing. Four new Compose tests
cover these screen bindings with controlled repository state. Existing shell
tests now check live forms/restoration and the remaining three future previews.
The real-server instrumented case additionally sends non-host Start directly
through the repository, bypassing UI checks, and receives `not_host`; valid host
Start receives `feature_unavailable` and never creates a round.

Lint briefly reported five unused Phase 05 draft/preview strings. Those obsolete
resources were removed. Final warning categories match Phase 06: OldTargetApi (1),
AndroidGradlePluginVersion (1), GradleDependency (5), NewerVersionAvailable (4),
DataExtractionRules (1), MissingApplicationIcon (1), InsecureBaseConfiguration (1,
debug only). No warnings were suppressed and no unrelated upgrades were made.

## Live UI verification

The local server was started from root:

```powershell
uv run --project server --locked --offline uvicorn one_job.main:app --host 0.0.0.0 --port 8765 --workers 1 --ws-max-size 16384 --log-config server/logging.json
```

Separately installed app instances were launched with `adb -s <selected-serial>
install -r android/app/build/outputs/apk/debug/app-debug.apk` and `adb -s
<selected-serial> shell am start -n com.onejob.game/.MainActivity`. UIAutomator
interaction operated the actual app forms/controls; it did not inject memberships.
Only synthetic names Captain/Crew were used. Local screenshot/UI evidence stays
in ignored `artifacts/phase07/`.

- A created through the normal form. The physical phone B joined through Join
  using the lowercase version of A's code. Both displayed the same uppercase
  code and two distinct IDs, correct host/you markers and authoritative flags.
- Both Ready controls updated the shared roster. A's Start became enabled; B's
  remained disabled with the host-only explanation. A's valid Start displayed
  the planned unavailable message and stayed in Lobby. `a-two-start-result.png`
  was visually inspected.
- C joined through the normal form using the same display name as B. The roster
  retained distinct IDs and reset readiness. The phone became unavailable in
  another foreground app during this step; control of the phone was paused.
  Other clients showed its disconnected reserved seat, then removal after grace.
  This is not recorded as a successful three-connected-and-ready session.
- A long C network interruption showed reconnecting, an empty roster and disabled
  controls, then expiry/Home with the session-ended message. C rejoined normally.
  A subsequent short interruption, restored in the same script, resumed the same
  C player ID and a full matching roster without duplicates (`c-resumed-final.png`).
  The emulator's original airplane/Wi-Fi/mobile-data values were restored (0/1/1).
- C's new lobby and leave dialog were checked at font scale 2.0. Ready, Start and
  Leave remained readable and reachable by scrolling; Stay cancelled leave and
  retained membership. The dialog and controls were visually inspected. Font
  scale was restored to 1.0. No physical-phone settings were changed.

## Completed three-client gate

The user subsequently confirmed the phone was ready. The final APK was installed
on all three devices, each app was restarted, and a fresh lobby was created on A.
B (the physical phone) and C joined via the normal forms using the same Crew name
and lowercase code input. After each local Ready action, all three UI hierarchies
were compared: one identical code, exactly three identical distinct member IDs,
and every member Connected/Ready. A's Start was enabled; both non-hosts' Start
buttons remained disabled. A's valid Start displayed the planned unavailable
message and stayed in Lobby, with no role or round navigation.

B confirmed Leave and returned Home with the server-acknowledged leave message.
A immediately showed two current members and reset readiness. B joined the same
code again through the form. All three clients then agreed on exactly three
current IDs, the old phone membership was absent, and readiness was reset. This
completes the previously pending shared three-client gate using the explicitly
approved one-phone/two-emulator mix.

All three test memberships were subsequently left through confirmation and all
three apps returned Home. App-PID-only logcat scans found no crash/ANR or
credential/JSON-frame markers. The server logged clean application shutdown;
the owned server port and both verification emulators were stopped. The final
debug app remains installed on the phone. No physical-phone settings changed.
No Phase 07 gate remains blocked.

Ignored captures include `final-a-three-all-ready.png`,
`final-b-three-all-ready.png`, `final-c-three-all-ready.png`,
`final-a-three-start-result.png` and each `after-b-rejoin` capture. The earlier
two-client check and these shared real-app checks complement the automated
repository/Compose tests; they are not replaced by multiple repositories in one app.

## Architecture and handoff

[ADR-016](DECISIONS.md#adr-016--admission-driven-lobby-ui-and-explicit-uncertain-attempts)
records identity-driven navigation, explicit uncertain admission reset, one
repository, authoritative readiness, host/server start hints, confirmed leave
and no role/gameplay transition. Raw server errors/tokens never enter UI copy or
saved state. Only nonsecret form inputs/validation presentation are saved.

The complete Phase 14 background/process-death matrix, API 26, other phones and
real WSS hosting remain deferred. Starting rounds/roles remains Phase 08 work.
Phase 08 may enable start into role briefing after this handoff. It was not started.
