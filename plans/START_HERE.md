# First local Codex session

Extract the archive, open this repository root in Codex, and open `android/` in
Android Studio to install/configure its SDK. The first incomplete phase is 00
because Android could not be compiled/launched in the Work environment.

Give Codex this exact prompt:

```text
Finish plans/phase-00-repository-foundation.md in this existing One Job repository. Read AGENTS.md, plans/plans.md and docs/FOUNDATION_VALIDATION.md first. Preserve the implemented foundation and do not regenerate it. Verify Python 3.12+, uv, JDK 17, Android SDK Platform 36 and Build Tools 35.0.0. Run the repository checker, backend tests/static checks/package build, and Android debug build/lint checks. Launch the placeholder on an available emulator/device and run its included instrumented smoke test. Fix only Phase 00 issues. Record actual results and any remaining blockers. Mark Phase 00 complete in plans/plans.md only after all required gates pass. Do not implement Phase 01 or any gameplay. End with the required handoff and stop.
```

If an emulator/device is unavailable, Codex should complete independent checks and
leave the launch gate pending with exact instructions. It must not mark it passed.

Once Phase 00 is verified and checked off, explicitly request Phase 01 using the
prompt in [the master plan](plans.md). Keep one phase per session.
