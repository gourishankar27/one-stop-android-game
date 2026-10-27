# Android scaffold

Open this directory in Android Studio. The only screen is a Compose foundation
placeholder; no networking, navigation, repository or gameplay is implemented.

Toolchain: JDK 17, Gradle 8.13, AGP 8.13.2, Kotlin/Compose compiler 2.2.21,
Compose BOM 2025.10.01, compile/target SDK 36, min SDK 26.
Install Platform 36 and Build Tools 35.0.0 through SDK Manager.

The official Gradle wrapper scripts and JAR are included. Run:

```powershell
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest
.\gradlew.bat :app:connectedDebugAndroidTest
```

The second command requires a device or emulator. There is currently no Android
unit-test behavior; the instrumented test checks the placeholder home screen.
Unit tests arrive with stateful client behavior in Phase 05.
On Unix, use `./gradlew` (run `chmod +x gradlew` if extraction loses permissions).

Gradle uses `ANDROID_HOME` or an ignored `local.properties` containing
`sdk.dir=...`. Never commit a machine-specific SDK path. JDK 17 must be selected
for Gradle even if Android Studio ships with a different runtime.

Networking permissions and debug-only cleartext allowances belong to Phase 06.
The main manifest currently disables cleartext traffic and backup. There are
no signing credentials. Release signing/publication is future work.
