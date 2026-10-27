# Android scaffold

Open this directory in Android Studio. The only screen is a Compose foundation
placeholder; no networking, navigation, repository or gameplay is implemented.

Toolchain: JDK 17, Gradle 8.13, AGP 8.13.2, Kotlin/Compose compiler 2.2.21,
Compose BOM 2025.10.01, compile/target SDK 36, min SDK 26.
Install Platform 36 and Build Tools 35.0.0 through SDK Manager.

The official Gradle wrapper scripts and JAR are included. Run:

```powershell
.\gradlew.bat --version
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest
.\gradlew.bat :app:connectedDebugAndroidTest
```

The last command requires a device or emulator visible in `adb devices -l`.
There is currently no Android unit-test behavior; the instrumented test checks
the placeholder home screen. Espresso 3.7.0 is explicit because the Compose test
dependency otherwise selects 3.5.0, which fails during setup on API 37; see
[ADR-012](../docs/DECISIONS.md#adr-012--explicit-espresso-dependency-for-the-foundation-smoke-test).
Expect `testDebugUnitTest NO-SOURCE`, not a count of passed JVM tests.
Unit tests arrive with stateful client behavior in Phase 05.
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

Inspect the placeholder in both system themes. Lint reports appear in
`app/build/reports/lint-results-debug.html`; instrumented results appear in
`app/build/reports/androidTests/connected/debug/index.html`. Actual validation
evidence and any warnings are recorded in
[FOUNDATION_VALIDATION.md](../docs/FOUNDATION_VALIDATION.md).

Networking permissions and debug-only cleartext allowances belong to Phase 06.
The main manifest currently disables cleartext traffic and backup. There are
no signing credentials. Release signing/publication is future work.
