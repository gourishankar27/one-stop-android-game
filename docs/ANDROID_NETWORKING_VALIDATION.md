# Android networking validation — 2026-10-28

Phase 06 was implemented on the existing foundation, beginning with a clean
working tree at `fa855a5`. Phases 03, 04 and 05 were already checked in the master
plan. AGENTS.md, the master plan, phase brief and foundation validation were read
before implementation. No backend production source or domain rule changed.
The master plan remains the only completion ledger.

## Environment and dependencies

| Requirement | Observed |
| --- | --- |
| Python | `python --version`: 3.14.0; `py -3.12 --version`: 3.12.10; uv backend tests used 3.12.10 |
| uv | `uv --version`: 0.13.6; locked development sync passed |
| Java | `java -version` / `javac -version`: Temurin 17.0.18 |
| Gradle | `gradlew.bat --version`: 8.13; Java 17 launcher/daemon |
| SDK | Installed `android-36/source.properties`: API 36, revision 2; Build Tools `source.properties`: 35.0.0 |
| Emulator | Existing read-only Medium Phone AVD, Android 17 / API 37, x86_64 |
| Physical phone | Samsung SM-S721U1, Android 16 / API 36, authorized USB debugging and same trusted Wi-Fi LAN |
| Added dependencies | OkHttp 4.12.0; kotlinx.serialization-json 1.9.0; serialization compiler plugin 2.2.21 |

The Gradle/AGP/Kotlin/Compose/SDK baseline and existing dependency versions were
preserved. New dependencies resolved and compiled on that baseline; release
Kotlin also compiled. Serialization 1.9.0 uses Kotlin 2.2.0, compatible with the
retained 2.2.21 compiler ([official release](https://github.com/Kotlin/kotlinx.serialization/releases/tag/v1.9.0)).
Local toolchain setup, caches, APKs, reports, screenshots and app-only logs remain
ignored under the existing build/artifact directories. No phone serial, session
credential or raw private frame is recorded here.

## Executed checks

From root, `python scripts/check_repository.py` passed. From `server/`:

```powershell
uv sync --locked --extra dev --offline
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build --offline
```

Results: **852 passed**, Ruff clean, **51 files** already formatted, mypy clean
across **26 source files**, wheel and source distribution built successfully.
The Phase 04 fixture test now also validates `docs/protocol-fixtures/phase06.json`;
Kotlin reads those same files directly as test resources. All credentials in the
fixtures are explicit synthetic markers. Existing Starlette/TestClient `httpx`
deprecation remains one warning; no dependency upgrade was made for it.

The installed Python/Java/uv tools needed execution outside the workspace sandbox.
Locked sync used the existing ignored workspace uv cache; package building used
the existing user uv cache containing Hatchling. These were successful local
environment accommodations, not missing completion gates.

From `android/`, using the reachable PC LAN address for this observed run:

```powershell
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest '-PoneJobDebugWsUrl=ws://192.168.12.61:8765/ws' '-PoneJobAllowDebugCleartext=true' --console=plain
.\gradlew.bat :app:connectedDebugAndroidTest :app:compileReleaseKotlin :app:processReleaseMainManifest '-PoneJobDebugWsUrl=ws://192.168.12.61:8765/ws' '-PoneJobAllowDebugCleartext=true' '-Pandroid.testInstrumentationRunnerArguments.oneJobLiveServer=true' --console=plain
```

Results: debug assembly/lint and **30 JVM tests passed**. The final connected run
passed **8 tests on the emulator and 8 on the phone, zero skipped/failures**;
release Kotlin compilation and manifest processing passed. Before the combined
regression, the emulator was tested first, then the phone independently using:

```powershell
adb -s <phone-serial> install -r app/build/outputs/apk/debug/app-debug.apk
adb -s <phone-serial> install -r -t app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb -s <phone-serial> shell am instrument -w -r -e oneJobLiveServer true com.onejob.game.test/androidx.test.runner.AndroidJUnitRunner
```

The actual authorized serial was selected locally and is omitted here. The
independent phone invocation reported `OK (8 tests)`. Default connected runs
without the opt-in argument skip the live-server case; the passing runs above
explicitly enabled it. Reports are in `android/app/build/reports/` and test XML
under `android/app/build/outputs/androidTest-results/` / `build/test-results/`.

Final lint: **0 errors, 14 warnings**. Categories are OldTargetApi (1),
AndroidGradlePluginVersion (1), GradleDependency (5), NewerVersionAvailable (4),
DataExtractionRules (1), MissingApplicationIcon (1) and InsecureBaseConfiguration
(1). The latter describes the explicit **debug-only** cleartext resource. The
merged release manifest has INTERNET, backup disabled, cleartext disabled and
no debug network-security configuration. The newer-version/icon/backup warnings
do not justify unrelated upgrades or release work in this phase.

Negative configuration check:
`gradlew.bat help '-PoneJobReleaseWsUrl=ws://127.0.0.1:8765/ws' --console=plain`
failed as intended with a static credential-free WebSocket/WSS requirement.
This is evidence of the guard, not a remaining build failure. No insecure TLS
trust manager or logging interceptor was added.

## Behavior and manual verification

The local server was started from root with:

```powershell
uv run --project server --locked --offline uvicorn one_job.main:app --host 0.0.0.0 --port 8765 --workers 1 --ws-max-size 16384 --log-config server/logging.json
```

The enabled live test used two independent real repositories on each device to
ping, create a room, join the other player, agree on the two-player roster, ready
both players and receive the existing `feature_unavailable` start response. It
then cancelled one actual socket, observed cleared cached state and reconnecting,
resumed with the same server identity, and waited for a fresh correlated full
snapshot. Both readiness flags reset according to server policy. Exactly one
replacement socket opened. State request and both explicit leaves succeeded.
The fixture/fake tests additionally verify that actions/admission are never
replayed, old generations cannot expire a replacement, lower room revisions and
retired rounds are rejected, and equal-revision distinct kinds remain applicable.

The first real emulator run exposed an ordering race: leave acknowledged its
caller before publishing disconnected. Terminal state is now published before
completing leave/error/timeout results. Both subsequent device suites passed.
A Gradle DSL namespace/import error and an unquoted PowerShell dotted-property
argument were also corrected during setup; quoted commands above passed.

Both installed placeholders were launched. Home's development panel created a
disposable test membership, showing **Connection: connected** and a successful
check. The owned server was stopped with Ctrl+C; its log showed application
shutdown completion. Both UIs visibly changed to **Connection: reconnecting**,
then expired within the bounded recovery budget. Explicit Connect with the
server still stopped produced **Connection: server unavailable** with retry/
disconnect feedback. Both original app processes stayed alive immediately after
server loss and the expiry check. The phone subsequently returned Home and Android
reclaimed its background process: the app's exit record reports `LOW_MEMORY`,
importance 400, status 0, with no crash-buffer entry. Relaunch correctly began
disconnected because credentials are not persisted; its explicit server-off retry
was checked again. This is an observed process-lifetime limitation, not an
unimplemented durable-resume claim. App-PID-only logcat inspection found no
FATAL EXCEPTION/ANR or credential/JSON-frame markers;
the server logs contained only allowlisted operation/request metadata.

Screenshots and UI hierarchy evidence were inspected locally in ignored
`artifacts/phase06/`: `emulator-connected`, `phone-connected`, both `server-off`
and both `unavailable` captures. The emulator used the existing light theme;
the phone used its existing dark theme. No device settings or firewall rules
were changed. The server and verification emulator were stopped after checks;
the phone's debug app remains installed with the connection explicitly closed.

## Decisions, limits and handoff

[ADR-015](DECISIONS.md#adr-015--android-transport-ownership-and-debug-endpoint-opt-in)
records the application-owned coroutine repository, one socket, bounded queues/
requests, five-second uncertainty, 1/2/4/8-second resume within an absolute
30-second budget, private endpoint-bound memory credentials and explicit debug
cleartext configuration. Setup instructions are in [android/README.md](../android/README.md#explicit-endpoint-configuration).
The v1 wire version and server room policy did not change.

No Phase 06 blocker remains after these checks. Credentials intentionally do not
survive process death. API 26, other physical devices, real WSS hosting, full
background/process-death/fault coverage and durable credential storage remain
unverified or deferred to their selected phases. Existing lint/TestClient warnings
remain above. This is a networking foundation, not a usable multiplayer lobby.

Phase 07 may bind create/join/lobby UI to these APIs. It must preserve typed
outcomes, distinguish uncertainty from rejection, gate navigation during recovery
and use authoritative snapshots. No Phase 07 work or gameplay was implemented.
