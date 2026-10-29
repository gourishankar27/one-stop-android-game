# Foundation toolchain

The foundation pins a compatible baseline rather than claiming the newest
available versions. Revisit versions together in a deliberate maintenance change.

| Component | Selection | Reason |
| --- | --- | --- |
| Python | 3.12+; `server/.python-version` selects 3.12 | User requirement; stable local baseline |
| Python dependencies | Ranges in pyproject, exact resolution in uv.lock | Repeatable local/server setup |
| Java / Gradle | JDK 17 / Gradle 8.13 | AGP 8.13 compatibility requirements |
| AGP | 8.13.2 | API 36 support; avoid an unnecessary AGP 9 migration |
| Kotlin / Compose compiler | 2.2.21 / 2.2.21 | Compiler plugin follows Kotlin version |
| Compose libraries | BOM 2025.10.01 | Explicit compatible library set |
| Android navigation | Navigation Compose 2.9.5 | Explicit Phase 05 shell graph; compatible with retained baseline |
| Android lifecycle | runtime-compose, viewmodel-compose and viewmodel-savedstate 2.9.4 | Lifecycle-aware collection and navigation-entry saved state |
| Android coroutines / JVM tests | coroutines-android/test 1.10.2; JUnit 4.13.2 | Explicit StateFlow/test-dispatcher setup in Phase 05 |
| Android transport | OkHttp 4.12.0; kotlinx.serialization-json 1.9.0; serialization plugin 2.2.21 | Phase 06 typed WebSocket boundary; retained Kotlin baseline (ADR-015) |
| Instrumented tests | AndroidX runner 1.7.0, JUnit extension 1.3.0, Espresso 3.7.0 | Explicit Espresso avoids Compose's older transitive dependency failing on API 37; ADR-012 |
| Android SDK | min 26, compile/target 36; Build Tools 35.0.0 | Practical phone baseline; supported by selected AGP |

Official references consulted for the baseline:

- [AGP 8.13 release notes and compatibility](https://developer.android.com/build/releases/agp-8-13-0-release-notes)
- [Compose BOM use](https://developer.android.com/develop/ui/compose/bom)
- [Compose BOM mapping](https://developer.android.com/develop/ui/compose/bom/bom-mapping)
- [Android architecture guide](https://developer.android.com/topic/architecture)
- [Navigation 2.9.5](https://developer.android.com/jetpack/androidx/releases/navigation#2.9.5)
- [Lifecycle 2.9.4](https://developer.android.com/jetpack/androidx/releases/lifecycle#2.9.4)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Gradle wrapper documentation](https://docs.gradle.org/8.13/userguide/gradle_wrapper.html)

Wrapper scripts/JAR come from the official Gradle v8.13.0 source distribution.
The distribution SHA-256 is pinned in wrapper properties. The JAR is a vendored
third-party bootstrap binary, not a locally built artifact. Its upstream license
is recorded in `android/gradle/wrapper/NOTICE.md`.

Android Studio generated JDK 17/Adoptium daemon criteria during local validation.
The accompanying Foojay resolver 0.10.0 can provision a matching JDK when needed.
`gradlew --version` reports the launcher separately from these daemon criteria;
keep the launcher on JDK 17 as well. Machine-specific paths remain ignored.

Target SDK here is a development baseline, not a promise of future store-policy
compliance. Phase 18 must recheck publishing requirements when external testing
is actually prepared. No store tooling or signing keys are configured now.
