# Foundation validation — 2026-10-27

Observed Windows validation of the existing foundation, starting from commit
`2249a61` with a clean working tree. The source scaffold was preserved. The
completion decision is recorded only in [plans/plans.md](../plans/plans.md).

## Observed environment

| Tool / prerequisite | Observed evidence |
| --- | --- |
| Python launcher | `python --version`: 3.14.0; `py -3.12 --version`: 3.12.10 |
| Backend interpreter | `uv run --project server --locked python --version`: 3.12.10, selected by `server/.python-version` |
| uv | `uv --version`: 0.13.6; installed in an ignored local tooling environment and added to this session's PATH |
| Java compiler/runtime | `java -version` and `javac -version`: Temurin 17.0.18; selected through session-local `JAVA_HOME` |
| Gradle | `gradlew.bat --version`: 8.13; launcher JVM 17.0.18; final daemon criteria select Java 17 / Eclipse Temurin |
| Android SDK | Platform `android-36`, revision 2, API 36; Build Tools 35.0.0, verified from installed `source.properties` |
| Android Studio | Rabbit 1, 2026.2.1; existing `android/` project opened and synced successfully |
| Emulator | 37.2.12; WHPX acceleration check passed; existing `Medium_Phone_API_37.0` AVD booted as API 37 / Android 17, x86_64 |

The emulator was started in read-only mode without loading/saving snapshots.
SDK paths, downloaded tooling, caches and outputs remain ignored. The existing
`server/uv.lock` and the application's runtime dependencies were retained.

During verification, Studio generated a Foojay resolver 0.10.0 entry in
`android/settings.gradle.kts` and `android/gradle/gradle-daemon-jvm.properties`
selecting Adoptium JDK 17. These changes were preserved and included in the final
checks. Studio provisioned its matching JDK; its daemon log confirms Java 17.
An unrelated `.vscode/settings.json` also appeared during the run and was left
untouched.

## Executed checks

| Check | Observed result |
| --- | --- |
| `python scripts/dev.py setup-server` | Passed; runs `uv sync --locked --extra dev` in server/; 31 locked packages installed/checked |
| `python scripts/dev.py check-server` | Passed: locked sync; `uv run --locked pytest` (2 passed, 1 upstream warning); `uv run --locked ruff check .`; `uv run --locked ruff format --check .` (6 files); `uv run --locked mypy src` (4 source files) |
| `uv build` in server/ | Passed; `one_job_server-0.1.0.tar.gz` and `one_job_server-0.1.0-py3-none-any.whl`; wheel inspected for the package and `py.typed` |
| `python scripts/check_repository.py` | Passed; 19 briefs, local links, packaging/XML and wrapper structure |
| `uv run --locked ruff check ../scripts`, `uv run --locked ruff format --check ../scripts`, `uv run --locked mypy ../scripts` in server/ | Passed; 2 helper files |
| `python scripts/dev.py run-server`, then `Invoke-WebRequest http://127.0.0.1:8000/health` in another terminal | HTTP 200, `{"status":"ok","service":"one-job-server"}`; Uvicorn logged clean application shutdown after Ctrl+C |
| `Get-FileHash android/gradle/wrapper/gradle-wrapper.jar -Algorithm SHA256` compared with the official published digest | Passed; `81a82aaea5abcc8ff68b3dfcb58b3c3c429378efd98e7433460610fecd7ae45f`; distribution checksum remains pinned |
| Wrapper scripts compared with Gradle v8.13.0 upstream, ignoring line endings; distribution pin compared with `Invoke-RestMethod https://services.gradle.org/distributions/gradle-8.13-bin.zip.sha256` | Both scripts match; distribution digest matches `20f1b1176237254a6fc204d8434196fa11a4cfb387567519c61556e8710aed78` |
| `gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest --console=plain` in android/ | Initial build passed in 7m 3s; lint 0 errors / 5 warnings; unit-test task `NO-SOURCE` |
| `gradlew.bat :app:connectedDebugAndroidTest --console=plain` before the fix | Failed: 1 test, 1 failure in Espresso setup, `NoSuchMethodException: InputManager.getInstance`; no placeholder assertion was reached |
| `gradlew.bat :app:dependencyInsight --configuration debugAndroidTestRuntimeClasspath --dependency espresso-core --console=plain` | Confirmed Compose UI test 1.9.4 selected Espresso 3.5.0 transitively |
| `gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest :app:connectedDebugAndroidTest --console=plain` after ADR-012 | BUILD SUCCESSFUL in 45s, 78 tasks executed; lint 0 errors / 5 warnings; JVM tests `NO-SOURCE`; instrumented smoke: 1 passed, 0 failures/errors/skips |
| Android Studio sync and Run `app` on `emulator-5586` | Passed; final sync succeeded, Studio assembly succeeded, install completed, and `MainActivity` became the resumed activity |
| `git diff --check` and ignore checks for SDK configuration, virtual environments, keys and generated outputs | Passed; local configuration and outputs are ignored |

The two Python tests verify the health response and the absence of premature
gameplay transport. The unchanged Compose test
`FoundationHomeTest.homeExplainsFoundationStatus` verifies the displayed title
and foundation status. The initial instrumentation failure was fixed by adding
only `espresso-core:3.7.0` to instrumented dependencies; see
[ADR-012](DECISIONS.md#adr-012--explicit-espresso-dependency-for-the-foundation-smoke-test)
and the [official release notes](https://developer.android.com/jetpack/androidx/releases/test#espresso-3.7.0).
No gameplay, domain model or networking behavior was added.

## Reproduce the checks

At repository root on Windows:

```powershell
python scripts/check_repository.py
python scripts/dev.py setup-server
python scripts/dev.py check-server
cd server
uv build
cd ..\android
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest
.\gradlew.bat :app:connectedDebugAndroidTest
```

First put uv on PATH, select JDK 17 for the terminal launcher and configure the
SDK using `ANDROID_HOME` or ignored `android/local.properties`. On this machine,
ignored `artifacts/foundation/environment.ps1` holds the session-local paths.
Use an API 26+ emulator/device. The unit-test task is `NO-SOURCE` because no
Android stateful logic exists yet; it is not a passed unit-test suite.

Backend manual check: run `python scripts/dev.py run-server`, then request
`http://127.0.0.1:8000/health` in a second terminal. This validates live HTTP
serving separately from the in-process tests.

## Manual verification and local evidence

All 19 phase briefs and the product, state, architecture, protocol and UX
documents were reviewed. Dependencies, host authority, recipient privacy and the
two-player Pilot / Engineer+Shields assignment agree. The shield-action wording
in GAME_DESIGN.md was corrected to match the protocol's required `active` and
`facing` fields; the wire contract did not change.

The existing project opened and synced in Android Studio, and its `app` run
configuration installed and launched on the emulator. CLI launch also passed:

```powershell
adb -s emulator-5586 install -r android/app/build/outputs/apk/debug/app-debug.apk
adb -s emulator-5586 shell cmd uimode night no
adb -s emulator-5586 shell am start -W -n com.onejob.game/.MainActivity
adb -s emulator-5586 shell cmd uimode night yes
adb -s emulator-5586 shell am force-stop com.onejob.game
adb -s emulator-5586 shell am start -W -n com.onejob.game/.MainActivity
```

Both launches reported `Status: ok`. Screenshots were visually inspected in
both system themes: title, tagline, foundation status and future-phase message
are readable and respect system insets. No working create/join flow is advertised.
Local evidence is in ignored `artifacts/foundation/`: `placeholder-light.png`,
`placeholder-dark.png`, `smoke-before-fix.xml` and `android-final-checks.log`.
Final JUnit XML is under
`android/app/build/outputs/androidTest-results/connected/debug/`; the HTML
report is `android/app/build/reports/androidTests/connected/debug/index.html`.
No screenshots, logs or build outputs are added to version control.

## Warnings and coverage limits

No required Phase 00 gate remains blocked. The first Work-environment attempt's
Gradle network failure and absent SDK/device are historical; local compilation,
lint, launch and instrumentation have now run.

- Pytest reports one upstream Starlette HTTPX TestClient deprecation warning.
- Android lint reports `OldTargetApi`, `AndroidGradlePluginVersion`,
  `GradleDependency`, `DataExtractionRules` and `MissingApplicationIcon` (one each).
  The pinned baseline is deliberate; the placeholder has no stored session data
  or final launcher art. No lint warning is suppressed.
- Gradle packages `libandroidx.graphics.path.so` without stripping its symbols;
  the debug build succeeds. uv used file copies across drives when hardlinks
  were unavailable; installation succeeded.
- Device coverage is one API 37 emulator. Physical phones and API 26 were not
  tested; multiplayer, gameplay, balance and external deployment remain future
  scope. No broad Android compatibility or playable-game claim is made.
