# Android foundation

Open this directory in Android Studio. Phase 05 has one Activity, Home, local
Create/Join drafts and explicit Lobby/Role/Gameplay/Results previews. Setup checks
nonsecret typed inputs locally; no room/session is created. All online actions
remain unavailable. The app has no network permission, socket or gameplay rules.

Toolchain: JDK 17, Gradle 8.13, AGP 8.13.2, Kotlin/Compose compiler 2.2.21,
Compose BOM 2025.10.01, compile/target SDK 36, min SDK 26.
Install Platform 36 and Build Tools 35.0.0 through SDK Manager.
Navigation Compose 2.9.5, Lifecycle Compose/ViewModel/SavedState 2.9.4,
coroutines-android/test 1.10.2 and JUnit 4.13.2 are explicit. The original toolchain,
Compose BOM and Espresso 3.7.0 pins remain unchanged.

The official Gradle wrapper scripts and JAR are included. Run:

```powershell
.\gradlew.bat --version
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest
.\gradlew.bat :app:connectedDebugAndroidTest
```

The last command requires a device or emulator visible in `adb devices -l`.
JVM tests check draft validation, StateFlow updates with a fake repository,
nonsecret restoration and independent form state. Instrumented tests check Home,
all preview routes/system Back, Create/Join behavior, activity recreation with
retained inputs and absence of network permission. Espresso 3.7.0 is explicit because the Compose test
dependency otherwise selects 3.5.0, which fails during setup on API 37; see
[ADR-012](../docs/DECISIONS.md#adr-012--explicit-espresso-dependency-for-the-foundation-smoke-test).
Phase 05 observed 8 JVM tests and 5 instrumented tests passing; JVM tests are no
longer `NO-SOURCE`.
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
form ViewModels and constructor-injected `data/GameRepository`. The production
repository is explicitly unavailable; fakes appear only in tests. State collection
is lifecycle-aware. SavedStateHandle stores only name/code/check presentation;
there are no credential arguments or saved tokens. See
[architecture](../docs/ARCHITECTURE.md#android) and [current UI](../docs/UI_UX.md#current-phase-05-shell).

Manual check: open all seven destinations, use system/visible Back, type a Join
draft and rotate. Change system font size, scroll to every control and confirm the
draft remains. Restore device settings afterwards. Lint reports appear in
`app/build/reports/lint-results-debug.html`; instrumented results appear in
`app/build/reports/androidTests/connected/debug/index.html`. Actual validation
evidence and any warnings are recorded in
[ANDROID_FOUNDATION_VALIDATION.md](../docs/ANDROID_FOUNDATION_VALIDATION.md).

Networking permissions and debug-only cleartext allowances belong to Phase 06.
The main manifest currently disables cleartext traffic and backup. There are
no signing credentials. Release signing/publication is future work.
