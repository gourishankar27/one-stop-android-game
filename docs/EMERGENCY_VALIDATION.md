# Phase 10 emergency validation — 2026-10-29

Scope: only asteroid approach, engine overheating and shield overload, their pure
seeded scheduling/rules, existing-room event delivery, private projections and
Android warnings. Phase 09's physical-phone gate closed before implementation;
its complete evidence remains in CORE_GAMEPLAY_VALIDATION.md. Phase 11 countdown,
results navigation, rematch and additional emergencies are not implemented.

## Environment and dependencies

Observed Python launcher 3.14.0, backend 3.12.10, uv 0.13.6, Temurin JDK 17.0.18,
SDK Platform 36 revision 2 and Build Tools 35.0.0. Existing Gradle 8.13, AGP 8.13.2,
Kotlin 2.2.21, Compose BOM 2025.10.01 and all dependency pins/lockfiles are retained.
The prerequisite Phase 09 checkbox has observed completion evidence. Device mix
is the user's approved API 36 physical phone plus two separate API 37 emulators,
not three physical phones. The local single-worker server uses an explicitly
configured trusted-LAN debug endpoint/cleartext opt-in. No firewall, credentials,
external service or publication was introduced.

## Implemented rules and architecture

ADR-019 was recorded before implementation. Numeric production defaults remain
unchanged and provisional. Config version is spaceship-v2; engine version is
spaceship-engine-v3. Emergencies are enabled by default. Explicit disabled
configuration preserves historical core-only fixtures without changing their
actions/outcomes; it is never a client-selectable bypass.

Continuous resources precede existing emergency effects in ID order; durations
age afterward, preserving the final evade protection tick. Maneuver precedes
shield absorption; success precedes same-tick timeout. Overload progress resets
when either condition breaks. Completed events are removed/count once, terminal
checks follow effects and no new event starts on a terminal tick. Pauses freeze
deadlines/scheduling/RNG. Finish/abort clear unfinished warnings without fake
failures. Heat uses no RNG and has priority over a due scheduled slot when only
one capacity slot is available. Empty scheduled slots draw only the next interval.

Shared events contain only round ID/event ID/kind/status. Private target arrays
are explicit per-owned-station allowlists; host status grants no extra access.
Events use the bounded critical outbox; snapshots remain coalesced. Android uses
the server's deadline values/conditions and retains at most one shared lifecycle
label, with no local physics, outcome or deadline clock. Recovery clears it.

## Commands and observed results

From `server/`, using the configured Python/uv caches:

```powershell
uv sync --locked --extra dev --offline
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src examples
uv build --offline
```

The final suite has **1,020 passing backend tests**, with the one existing
Starlette/httpx TestClient warning. Strict mypy passes 40 source/example files.
Source distribution and wheel built successfully. Final locked sync, pytest,
Ruff/format (72 files), mypy and package commands all passed. The pure core-only
engine example still reproduces victory at tick 900/hull 1000/one terminal event.
Repository/whitespace checks passed. Final lobby/role/gameplay real-socket
regressions also passed, including all nine actions, power rejection, owned
allowlists, common-revision public equality, resume and normal leave.

New deterministic tests cover all asteroid paths and exact energy boundaries,
overheat threshold/deadline/output checks, overload progress/reset/final-tick
success, capped concurrency/one kind, skipped slots/draw order/third boundaries,
capacity-delayed heat, ascending simultaneous IDs, final evade protection,
paused/terminal RNG, completed result counts and accepted-only full seeded replay.
Eight frozen resolve/fail/simultaneous traces and a complete seed-71 lifecycle
fixture are included. Real room-owner tests advance a fake clock through complete
2/3-player rounds and compare all recipient public state, private keys, one-time
event emission, result counts and non-replay on state requests. No unit test sleeps
for simulated time. Shared synthetic phase10.json round-trips through both codecs.

From `android/`:

For the observed commands below, `<PC-LAN-IP>` was `192.168.12.61`; it was supplied
only as a local Gradle property, not committed as application configuration.

```powershell
.\gradlew.bat :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug :app:testDebugUnitTest :app:compileReleaseKotlin '-PoneJobDebugWsUrl=ws://<PC-LAN-IP>:8765/ws' '-PoneJobAllowDebugCleartext=true' --console=plain
.\gradlew.bat :app:connectedDebugAndroidTest '-PoneJobDebugWsUrl=ws://<PC-LAN-IP>:8765/ws' '-PoneJobAllowDebugCleartext=true' '-Pandroid.testInstrumentationRunnerArguments.oneJobLiveServer=true' --console=plain
```

Debug/test APK, lint, JVM and release compilation checks passed. The final combined
build/lint/JVM/release/connected command passed. **23 instrumented
tests passed on each of the phone and two emulators** (69 executions, no skips or
failures), including the enabled live LAN core actions/resume case and new warning
privacy/visibility/paused deadline/dual-station badge tests. No test copies physics
into Kotlin. Report inspection found **63 JVM tests passed**, **0 lint errors and
14 retained baseline warnings**. Gradle reused unchanged JVM/release outputs in
the final combined run; the 63 JVM test executions passed after the latest
repository lifecycle-feedback behavior change. The final device rerun covers
that behavior and the added UI test that event feedback cannot locally remove
active warnings or change hull. Experimental distributed tests are excluded from
the included test APK; their failed attempts are documented below.

## Reproducible local seed harness

Run in `server/`, on the trusted development network only:

```powershell
uv run python examples/emergency_harness.py --seed 71 --host 0.0.0.0 --profile default
uv run python examples/emergency_smoke.py
```

The default profile is the unmodified production GameConfig. The smoke operates
2 then 3 independent real sockets through normal admission, briefing, existing
station actions and complete terminal rounds. It checks common-revision public
equality, owned keys, shared lifecycle allowlists, no duplicates and exact result
counts, then leaves every membership. Only counts/outcomes are printed. Seeds,
targets, credentials and raw private frames are never exported to shared logs.
Both complete default-profile seed-71 rounds passed: two controllers reached
victory with 11 resolved/1 failed; three controllers reached victory with
12 resolved/1 failed. All recipients agreed and no lifecycle duplicate appeared.

For normal-UI device inspection, `--seed 1 --profile verification` selects the
explicit `spaceship-ui-verification-v1` config defined in emergency_harness.py:
120 seconds; initial heat 799/output 60/energy 1000; heat gain/cooling 4 per tick;
coolant 300; critical damage zero; each event damage 60; asteroid/overheat deadlines
160 ticks, overload deadline 140; every scheduled interval 80. Other defaults,
including 20 consecutive overload ticks, remain unchanged. These overrides make
UI inspection feasible; they are not production balance changes. There is no HTTP
seed/debug route or emergency-resolution command. The ordinary room owner,
scheduler, actions, privacy and client UI still run.

## Remaining verification and limitations

The user explicitly requested **leaving the human playtest gate pending**. Phase
10 stays unchecked. The required two-/three-player communication check, including
a resolution/failure of each kind in each mode, must be observed with people.
No fun/balance or completed manual-matrix claim is made. API 26, three physical phones, WSS infrastructure,
TalkBack and the broader Phase 14 background/process-death matrix are not claimed.

Normal UI inspection did start a real two-client round on the API 36 phone
(Engineer+Shields) and an emulator (Pilot). An inspected phone capture shows
distinct public overheating/asteroid labels, both owned attention badges, only
the selected Engineer's temperature/output instruction, accepted output 60 and
the server deadline. No Pilot lane appears on that phone panel. Two-client
shared UI feedback observed overheating failed/resolved, asteroid failed/resolved
and overload failed, before the experimental driver failed. This is partial
evidence, not a passing full matrix or an observed human conversation.

The first coordinate driver lost station selection when dynamic warnings changed
layout positions. A subsequent experimental Compose driver initially readied the
host before all joins, which correctly reset readiness; the harness was corrected
to wait for the full roster. It also encountered missing Compose hierarchies and
a `CalledFromWrongThreadException` through the test frame clock when background
StateFlow delivery resumed the default test dispatcher. A test-only queued
dispatcher experiment then stalled during the dual-station briefing. These
experimental checks did not pass and are not counted in the included passing
suite. The experimental source/logs remain ignored in `artifacts/phase10/`; no
production dispatcher, toolchain or dependency was changed to accommodate them.
The distinction between default unconfined and explicitly queued test dispatch
is documented in the [official Compose testing API](https://developer.android.com/reference/kotlin/androidx/compose/ui/test/AndroidComposeUiTestEnvironment).
The frame-clock diagnosis is an inference from that API and the observed trace,
not a claim that the ordinary app exhibited the same crash.

Final cleanup: all included live test/example memberships were left. Abandoned
experimental memberships were discarded when their disposable server was stopped.
The final server port is closed and no verification harness server process remains;
the two owned emulators were stopped. No graceful-shutdown log claim is made for
the redirected Windows Ctrl+C harness. The final debug APK installed on the phone
and MainActivity launched with `Status: ok`. A final UIAutomator idle probe failed;
when a later foreground check showed the user had switched away from One Job,
no further phone UI or screenshot operation was performed. Home was therefore
not re-confirmed at cleanup. Final ordinary-app PID log scan found zero crash/ANR
or private-payload markers. Own temporary device XML/PNG files were removed.
