# Phase 08 role-system validation

Date: 2026-10-28. Scope: seeded private station ownership and briefing only.
The existing Phase 06/07 working-tree changes were preserved. Dependencies 02
and 07 were already checked in the master ledger; their foundation was extended,
not regenerated. No gameplay, emergency scheduler, countdown, results or rematch
flow was implemented.

## Environment and dependencies

Verified Python launcher 3.14.0, backend Python 3.12.10, uv 0.13.6, Temurin JDK
17.0.18, Android SDK Platform 36 revision 2 and Build Tools 35.0.0. The existing
Gradle 8.13 / AGP 8.13.2 / Kotlin 2.2.21 / Compose BOM 2025.10.01 baseline was
retained. Locked offline sync resolved/checked 31 packages. No dependency was
added and no lockfile or toolchain pin was changed for Phase 08.

Verification used the user's existing device choice: one SM-S721U1 physical phone
(Android 16 / API 36) plus two separate read-only API 37 / Android 17 emulators.
These are three Android clients, not three physical phones. The debug APK used
the PC's trusted private LAN endpoint with explicit cleartext opt-in. No external
service, account, credential, firewall rule or phone setting was changed.

## Automated checks

From the repository root:

```powershell
python scripts/check_repository.py
git diff --check
```

From `server/`, with Python/uv configured and the existing local caches available:

```powershell
uv sync --locked --extra dev --offline
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src examples
uv build --offline
uv run python examples/lobby_smoke.py --url ws://127.0.0.1:8765/ws
uv run python examples/role_smoke.py --proof ../artifacts/phase08/privacy-proof.json
```

Observed: **897 backend tests passed**, Ruff lint passed, all 59 Python files
formatted, strict mypy passed for 34 source/example files, and wheel plus source
distribution built. The one existing Starlette/httpx TestClient deprecation
warning remains. The fresh isolated interpreter checks role assignment/metadata
and the engine without web dependencies or environment configuration.

Tests cover repeatable two-/three-player seed shuffles, full unique coverage,
invalid rosters without RNG consumption, immutable metadata, copied RNG state,
all nine action owners, stale round IDs, forged client fields, pause/resume/abort,
exact timeout boundaries, suspended acknowledgement budget, all-participant
reconnect, no ticks after all acknowledge, and frozen participants after abort.
A regression also crosses the deadline between the owner's earlier expiry check
and acknowledgement dispatch: abort advances revision and broadcasts to every
participant even though the acknowledgement itself is rejected.
Private projection tests use exact-value sentinels, include the host, inspect
per-member state replay and assert private details are absent from representations.

The live lobby example passed admission/readiness, non-host Start rejection,
leave/resume, stable identity/token, revision agreement and host transfer. The
role example passed separate **two- and three-controller** starts, private frame
field allowlists, exact owned metadata/station keys, non-host/wrong-role rejection,
all acknowledgements and held tick zero, then left every membership. Its optional
proof contains only controller counts, station names and field names; no raw
frames, instructions, UUIDs or tokens are saved in that proof or committed.

From `android/`, with the local LAN server on port 8765:

```powershell
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest :app:connectedDebugAndroidTest :app:compileReleaseKotlin '-PoneJobDebugWsUrl=ws://192.168.12.61:8765/ws' '-PoneJobAllowDebugCleartext=true' '-Pandroid.testInstrumentationRunnerArguments.oneJobLiveServer=true' --console=plain
```

Observed: build successful, **52 JVM tests passed**, lint **0 errors / 14 retained
warnings**, release Kotlin compilation passed, and **15 instrumented tests passed
on each of the three devices** (45 executions, zero failures/errors/skips).
The live-server test was enabled, not skipped. It starts a real round, checks
owned station keys, wrong-role/stale-round rejection and both acknowledgements,
forces a socket loss, restores identity and fresh private state with the same
acknowledgement, and verifies departure abort. New Compose tests check own-only
instructions, dual-station read gating, held briefing and explicit timeout abort.
JVM tests also reject foreign/null station keys and mismatched owned metadata,
clear private recovery state, and prevent duplicate acknowledgement sends.

The retained lint warnings concern target/available dependency versions, debug
cleartext policy, backup configuration and the foundation launcher icon. A new
pluralization warning was fixed with a plural resource; final checks returned
to the 14-warning baseline. Gradle reports that the optional command-line live
test argument is incompatible with configuration caching; it does not fail the
checks. No dependency upgrade or unrelated warning cleanup was undertaken.

## Actual multi-client UI verification

The local server was started from root with one in-memory owner process:

```powershell
uv run --project server --locked --offline uvicorn one_job.main:app --host 0.0.0.0 --port 8765 --workers 1 --ws-max-size 16384 --log-config server/logging.json
```

Separate app instances were installed/launched and operated through their normal
Create/Join/Ready/Start/Leave UI using app-scoped UIAutomator observations. Only
the synthetic names Captain/Crew were entered. No session was injected into UI.
Ignored local captures are under `artifacts/phase08/`.

- Two clients: emulator A created; physical phone B joined using the lowercase
  room code. Both became ready and A started the round. A received only Pilot;
  B received Engineer and Shields. B switched to each instruction set and marked
  each read before acknowledgement enabled. A read/acknowledged Pilot. Both then
  displayed the explicit completed-briefing hold, disabled acknowledgement and
  stayed on Role. Light emulator and dark phone screenshots were inspected.
- A temporary emulator radio interruption returned to the same held private
  briefing, but did **not** produce an observable server pause on B within that
  observation window. It is not counted as pause evidence. Controlled real
  socket loss in the enabled instrumented test and fake-clock server tests are
  the pause/recovery evidence. Emulator network settings were restored to their
  original airplane/Wi-Fi/mobile-data values (0/1/1). After A's confirmed leave,
  B showed the explicit player-left abort and then left.
- Three clients: A created a fresh room; B and emulator C joined. All were ready
  before host Start enabled. A received Engineer, B Pilot, C Shields. UI trees
  showed exactly one station button per client and three unique roles overall;
  the host received no additional private station. Screenshots were inspected.
- Acknowledgements were withheld in that three-client round. After the real
  60-second server deadline, **all three screens** showed “Briefing timed out.
  Leave this room to try again.” Acknowledgement was disabled. None entered
  gameplay or the future Results route. The fake-clock test separately verifies
  the exact 60-second boundary without sleeping.
- All three confirmed Leave and returned Home. App-PID-only log scans found no
  crash/ANR or token/raw-payload markers. Device UI/screenshot temporary files
  were removed. Raw private transport frames were never exported to artifacts.
  The final APK was reinstalled on the phone at Home after connected tests. The
  server reported application shutdown complete, both owned emulators were
  stopped, and port 8765 was confirmed closed.

Local screenshot examples: `two-a-held.png`, `two-b-held.png`,
`three-a-private.png`, `three-c-private.png` and `three-b-timeout.png`.
The durable privacy evidence is the committed sentinel/allowlist tests and
synthetic shared fixture, not Android hiding fields from a full internal state.

## Corrections and limits

Earlier test expectations for feature-gated Start were updated to the implemented
briefing. A duplicate pytest module basename was corrected, and the Android fake
server encoder was corrected to omit unowned null station values, matching the
real server. Ruff formatting/async file-write issues were corrected. One lobby
smoke attempt used its default port 8000 and was refused; the explicit 8765 run
above passed. A manual harness assertion expected hold after the host had already
left; the subsequent check correctly verified player-left abort. These are
resolved verification issues, not remaining product blockers.
Final review also found and fixed the deadline-crossing notification edge above;
the final 897-test/static/package rerun passed after that correction.

ADR-017 records the existing-mailbox round context, private projections,
membership-scoped replay, suspended deadline and held briefing policy. Contracts,
Python/Kotlin DTOs and synthetic `phase08.json` fixtures were updated together.

No Phase 08 completion blocker remains. API 26, WSS infrastructure, three physical
phones, TalkBack and the full background/process-death fault matrix were not
tested here. The approved phone/emulator mix is the manual device evidence.
Process death still loses credentials and requires fresh admission. API 37
emulator coverage does not replace minimum-SDK or release-device testing. Those
broader lifecycle/release checks remain in their selected phases. Phase 09 may
activate controls/running simulation behind acknowledged briefing; Phase 11 owns
countdown/results/rematch. Neither phase was started.
