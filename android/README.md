# Android foundation

Open this directory in Android Studio. The single-Activity shell has Home,
Create/Join forms and a live Lobby. Role/Gameplay/Results remain previews. Phase 06
adds a typed, socket-owning data source and application-owned session repository.
Phase 07 binds the forms and live lobby to that repository: name/code submission,
room code, ID-keyed roster, host/you labels, local readiness and confirmed leave.
Eligible host Start displays the server's planned unavailable response.
There are no Android gameplay rules.

Toolchain: JDK 17, Gradle 8.13, AGP 8.13.2, Kotlin/Compose compiler 2.2.21,
Compose BOM 2025.10.01, compile/target SDK 36, min SDK 26.
Install Platform 36 and Build Tools 35.0.0 through SDK Manager.
Navigation Compose 2.9.5, Lifecycle Compose/ViewModel/SavedState 2.9.4,
coroutines-android/test 1.10.2 and JUnit 4.13.2 are explicit. The original toolchain,
Compose BOM and Espresso 3.7.0 pins remain unchanged.
Transport adds OkHttp 4.12.0 and kotlinx.serialization JSON 1.9.0, using the
serialization compiler plugin at the existing Kotlin version, 2.2.21 (ADR-015).

The official Gradle wrapper scripts and JAR are included. Run:

```powershell
.\gradlew.bat --version
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest
.\gradlew.bat :app:connectedDebugAndroidTest
```

The last command requires a device or emulator visible in `adb devices -l`.
JVM tests check form admission/pending/errors/uncertainty/cancellation, host/ready/
leave/recovery presentation plus typed shared fixtures, strict primitives, safe decode
failures, endpoint policy, correlation, uncertainty, bounded recovery, stale
generations, snapshot revisions and credential clearing with virtual time.
Instrumented tests check Home, previews/Back, local forms, retained inputs and
repository ownership across recreation, INTERNET permission and lifecycle-aware
connection feedback. The optional live-server test is skipped unless enabled below.
Espresso 3.7.0 is explicit because the Compose test
dependency otherwise selects 3.5.0, which fails during setup on API 37; see
[ADR-012](../docs/DECISIONS.md#adr-012--explicit-espresso-dependency-for-the-foundation-smoke-test).
Phase 08 observed 52 JVM tests and 15 instrumented tests passing on each of one
physical phone and two emulators, including the enabled live-server check.
On Unix, use `./gradlew` (run `chmod +x gradlew` if extraction loses permissions).

Gradle uses `ANDROID_HOME` or an ignored `local.properties` containing
`sdk.dir=...`. Never commit a machine-specific SDK path. JDK 17 must be selected
for Gradle even if Android Studio ships with a different runtime.
The generated `gradle/gradle-daemon-jvm.properties` selects Temurin JDK 17 for
the daemon, taking precedence over `JAVA_HOME` and Studio's Gradle JDK setting.
Keep the terminal launcher on JDK 17 too and inspect both JVM lines in
`gradlew.bat --version`. Studio can download a matching daemon JDK through the
configured resolver. Without daemon criteria, its Gradle JDK setting is under
Settings → Build, Execution, Deployment → Build Tools → Gradle; the
`GRADLE_LOCAL_JAVA_HOME` option uses ignored `.gradle/config.properties`.
See the [official JDK configuration guide](https://developer.android.com/build/jdks).

The package wiring is `MainActivity → app/OneJobApp → ui` with navigation-entry
form ViewModels and constructor-injected `data/GameRepository`. The application
owns one `SocketGameRepository`; `OkHttpSocketDataSource` alone owns the socket.
Closing the owner cancels pending work and transport. Rotation retains the owner.
State collection
is lifecycle-aware. SavedStateHandle stores only name/code/check presentation;
there are no credential arguments or saved tokens. See
[architecture](../docs/ARCHITECTURE.md#android) and [current UI](../docs/UI_UX.md#current-phase-05-shell).

Manual check: create on one client and join two others, compare the code/roster,
toggle readiness, check non-host/eligible host Start, reconnect and confirm leave.
Rotate with typed form input and ensure it is retained. At large font sizes all
controls must remain scrollable. Restore device settings afterwards. Lint reports appear in
`app/build/reports/lint-results-debug.html`; instrumented results appear in
`app/build/reports/androidTests/connected/debug/index.html`. Actual validation
evidence and any warnings are recorded in
[ANDROID_FOUNDATION_VALIDATION.md](../docs/ANDROID_FOUNDATION_VALIDATION.md) and
[ANDROID_NETWORKING_VALIDATION.md](../docs/ANDROID_NETWORKING_VALIDATION.md).
Current lobby evidence is in [LOBBY_UI_VALIDATION.md](../docs/LOBBY_UI_VALIDATION.md).

## Explicit endpoint configuration

No endpoint is configured by default. Start the single-process local server from
the repository root (bind only on a trusted network for the phone check):

```powershell
uv run --project server uvicorn one_job.main:app --host 0.0.0.0 --port 8765 --workers 1 --ws-max-size 16384 --log-config server/logging.json
```

From `android/`, opt in to cleartext on the emulator:

```powershell
.\gradlew.bat :app:assembleDebug '-PoneJobDebugWsUrl=ws://10.0.2.2:8765/ws' '-PoneJobAllowDebugCleartext=true'
```

For a physical phone, replace `10.0.2.2` with this PC's reachable private Wi-Fi
IPv4 address, such as `192.168.1.50`. Connect both to the same trusted LAN; allow
the local server port if the host firewall requires it. `localhost` on the phone
means the phone, and emulator-only `10.0.2.2` does not identify the PC on a phone.
Rebuild/reinstall after changing properties. Quote complete `-P...` arguments in
PowerShell, especially those containing dots. Properties may instead live in an
ignored local Gradle properties file; never include credentials in an endpoint.
The endpoint must end in `/ws`, with no user info, query or fragment.

Only debug variants contain the cleartext policy. Runtime validation additionally
requires the explicit flag and a canonical private/loopback address for `ws://`;
public cleartext hosts are refused. Release always requires `wss://`, configured
with `-PoneJobReleaseWsUrl=wss://your-host.example/ws`, and retains platform TLS
verification and `usesCleartextTraffic=false`. There are no signing credentials.

Home now offers **Create room** and **Join room**. Enter a name and, for Join, the
six-symbol code shown by the host. Case and outer spaces are normalized for the
submitted code; rejected inputs are retained. Pending admission blocks double
submission. Uncertain admission requires **Clear attempt before trying again**;
it is never automatically replayed. Back cancels an outstanding attempt.
The earlier debug transport panel remains in source but is no longer on Home.

The lobby shows only authoritative members/readiness. Ready affects your own
membership; Start is enabled only for the eligible host and opens a server-owned
private briefing. Both Back and Leave ask for confirmation.
Connection recovery clears the visible roster until the current server snapshot;
expiry returns Home. Use three separately running Android clients for the shared
lobby check; multiple repositories in one app do not replace that UI verification.

The briefing shows only your station(s). Switch between Engineer and Shields
when assigned both, read each instruction set and mark each read before
acknowledging. All acknowledged briefings explicitly hold without gameplay.
Pause freezes the server's acknowledgement budget; timeout/departure/grace expiry
shows an abort with Leave. Recovery clears private presentation until the fresh
owned snapshot arrives. Gameplay and Results remain Home previews. No credential
or private snapshot is saved through process death.

Run all connected tests with the real-server case enabled:

```powershell
$env:ANDROID_SERIAL = 'emulator-5554' # choose a serial from adb devices -l
.\gradlew.bat :app:connectedDebugAndroidTest '-PoneJobDebugWsUrl=ws://10.0.2.2:8765/ws' '-PoneJobAllowDebugCleartext=true' '-Pandroid.testInstrumentationRunnerArguments.oneJobLiveServer=true'
```

Use the phone's serial and PC LAN address for the phone run. The test performs
ping/create/join/readiness/start, verifies owned private views and wrong-role/
stale-round rejection, acknowledges both players, drops one real socket, verifies
stable identity, preserved acknowledgement and a fresh private snapshot after
resume, and leaves both memberships (aborting on departure).
It logs no credentials. A server-off connection check must also show actionable
feedback without a crash. Tokens stay in private process memory, are bound to
the endpoint and are cleared on leave, expiry or owner closure; process death
requires admission again. Durable recovery/background policy awaits Phase 14.
