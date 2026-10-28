# Android foundation validation — 2026-10-28

Observed Phase 05 implementation/verification on Windows. The Phase 04 server
implementation and documentation were uncommitted at session start and were
preserved. This phase changed Android shell code/tests and related documentation;
server behavior/dependency pins and the existing engine were retained. The sole
progress ledger is [plans/plans.md](../plans/plans.md).

## Toolchain and dependency evidence

| Check | Observed result |
| --- | --- |
| `java -version`; `javac -version` | Temurin 17.0.18 |
| `gradlew.bat --version` | Gradle 8.13; launcher 17.0.18; daemon criteria Java 17 / Eclipse Temurin |
| SDK source properties | Platform 36 revision 2; Build Tools 35.0.0 installed |
| Gradle plugin/Compose baseline | AGP 8.13.2, Kotlin/compiler 2.2.21, BOM 2025.10.01 unchanged |
| New explicit dependencies | Navigation Compose 2.9.5; Lifecycle runtime-compose/viewmodel-compose/viewmodel-savedstate 2.9.4; coroutines-android/test 1.10.2; JUnit 4.13.2 |
| `gradlew.bat :app:dependencies --configuration debugRuntimeClasspath --console=plain` | Resolved navigation/lifecycle/coroutine runtime versions match those pins |
| `adb devices -l`; `getprop sys.boot_completed` | Existing Medium_Phone_API_37.0 booted as emulator-5586, API 37 / Android 17, x86_64; boot complete 1 |

The emulator was started read-only, with no snapshot load/save and no window.
The original JDK/SDK environment script and local caches/outputs remain ignored.
No dependency-injection framework, networking library, signing key or Android
network permission was added. The older compatible release pins were retained
deliberately; [Navigation 2.9.5](https://developer.android.com/jetpack/androidx/releases/navigation#2.9.5)
and [Lifecycle 2.9.4](https://developer.android.com/jetpack/androidx/releases/lifecycle#2.9.4)
are documented releases, not claims about newest versions.

## Executed checks

From `android/` on Windows, with the local toolchain environment selected:

| Command | Actual result |
| --- | --- |
| `gradlew.bat :app:assembleDebug :app:lintDebug --console=plain` | Initial build/lint passed in 1m 4s |
| `gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest :app:assembleDebugAndroidTest --console=plain` | BUILD SUCCESSFUL in 9s; 8 JVM tests passed; instrumentation compiled |
| `gradlew.bat :app:connectedDebugAndroidTest --console=plain` | BUILD SUCCESSFUL in 30s; 5 tests, 0 failures/skips |
| Lint XML inspection | 0 errors; 11 warnings, detailed below |
| Root `python scripts/check_repository.py` and `git diff --check` | Passed; 19 phase briefs, links, package/XML/wrapper checks and clean whitespace |

JVM XML: DraftValidationTest 3 tests; RoomFormViewModelTest 5 tests; all have zero
failures/errors/skips. The tests cover Unicode scalar counting, malformed/control
input, ASCII code hints, immutable StateFlow updates, validation recovery, fake
repository status changes, nonsecret input restoration and independent forms.
Coroutine test dispatchers replace Main; no game/connection time sleeps are used.

The device suite contains the adapted original Home smoke and four navigation
tests. It traverses every future route with system Back, exercises actual local
Create/Join intents, recreates the Activity with the current Join destination and
typed inputs intact, and checks the installed app has no INTERNET permission.
No form submit method or socket/data source exists; composables cannot start a
create/join call through this repository interface.

Backend regressions also ran from `server/` with a workspace uv cache:

```powershell
uv sync --locked --extra dev --offline
uv run --locked --offline pytest -q
uv run --locked --offline ruff check .
uv run --locked --offline ruff format --check .
uv run --locked --offline mypy src
```

All passed: 31 locked packages, 851 tests, Ruff lint/format (51 files), strict
mypy (26 source files), one existing Starlette/httpx warning. Store Python 3.12
execution required the same narrow automatically approved invocation as Phase 04.
Backend packaging was not rerun because no server package/dependency changed.

## Manual verification

After instrumentation removed the tested APK, the first manual launch found no
installed Activity. Reinstalling the built debug APK resolved this expected test
runner cleanup; subsequent launch reported `Status: ok`:

```powershell
adb -s emulator-5586 install -r android/app/build/outputs/apk/debug/app-debug.apk
adb -s emulator-5586 shell am start -W -n com.onejob.game/.MainActivity
```

Using emulator input commands and fresh UI hierarchy/screenshot captures:

- Opened Home, Create, Join, Lobby, Role briefing, Gameplay and Results.
- Opened each of the four future previews and verified its unimplemented/no-session
  text; system Back returned to Home each time.
- Checked a local Create draft; filled a Join draft with synthetic `Engineer` /
  `abcd23` inputs and verified the truthful local-check result.
- Set accelerometer rotation off and user rotation to landscape. The Join route,
  both inputs and validation result remained; scrolling reached all controls.
- Returned to portrait and changed system font scale to 2.0. Home buttons, the
  Join fields/check action/result and the longest Role preview were visually
  inspected. Text wraps and scrolls; no fixed-height text container or unusable
  control was observed.
- Restored original font scale 1.0, user rotation 0 and accelerometer rotation 1.

Screenshots and hierarchy XML remain in ignored `artifacts/phase05/`, including
`home.png`, all four preview captures, `join-landscape-fields.png`,
`join-large-font-fields.png`, `home-large-font.png` and `role-large-font.png`.
They contain synthetic local drafts, not session credentials. The read-only
emulator started for this verification was stopped with `adb -s emulator-5586
emu kill` after restoring its settings.

## Architecture choices and limits

The existing Material 3 theme is preserved. A single Activity hosts enum-backed
Navigation Compose routes and stateless pages. An ordinary application container
injects the unavailable repository. Form ViewModels are scoped to navigation
entries and use SavedStateHandle/StateFlow with lifecycle-aware UI collection.
Only name/code/check presentation is saved. These follow the selected phase;
no significant policy deviation or new ADR was needed. See the documented
[ViewModel factory pattern](https://developer.android.com/topic/libraries/architecture/viewmodel/viewmodel-factories)
and [UI state saving guidance](https://developer.android.com/develop/ui/compose/state-saving).

Lint warnings are retained without suppressions or unrelated upgrades: target API
36, newer Gradle/Activity/Navigation/Lifecycle/coroutine versions (8 notices total
with the target warning separate), backup extraction rules and missing app icon.
The exact XML contains OldTargetApi (1), AndroidGradlePluginVersion (1),
GradleDependency (5), NewerVersionAvailable (2), DataExtractionRules (1) and
MissingApplicationIcon (1): 11 warnings. Release policy, icons/assets and final
presentation remain their planned work.

No socket, endpoint selection, live membership, gameplay rules or fake working
multiplayer was added. Local validation is a presentation hint; future server
admission remains authoritative. A full process-death/reconnection matrix,
physical devices, API 26 and other host platforms were not verified here. The
actual rotation/recreation and large-font gates above passed on the API 37 AVD.
Phase 06 is the recommended next phase, only on a new instruction.

All required Phase 05 gates have observed passing evidence. No gate remains
blocked. The master ledger records the completion decision; Phase 06 was not
started.
