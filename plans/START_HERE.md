# Local Codex sessions

Open the existing repository root in Codex and `android/` in Android Studio.
For a source archive, extract it first. Install/configure the toolchains in
[TOOLCHAIN.md](../docs/TOOLCHAIN.md), then consult [the master plan](plans.md)
for the current verified phase and remaining gates.

To finish or repeat foundation validation, give Codex this exact prompt:

```text
Finish plans/phase-00-repository-foundation.md in this existing One Job repository. Read AGENTS.md, plans/plans.md and docs/FOUNDATION_VALIDATION.md first. Preserve the implemented foundation and do not regenerate it. Verify Python 3.12+, uv, JDK 17, Android SDK Platform 36 and Build Tools 35.0.0. Run the repository checker, backend tests/static checks/package build, and Android debug build/lint checks. Launch the placeholder on an available emulator/device and run its included instrumented smoke test. Fix only Phase 00 issues. Record actual results and any remaining blockers. Mark Phase 00 complete in plans/plans.md only after all required gates pass. Do not implement Phase 01 or any gameplay. End with the required handoff and stop.
```

If an emulator/device is unavailable, Codex should complete independent checks and
leave the launch gate pending with exact instructions. It must not mark it passed.

Consult the master ledger before selecting a phase. For the room-and-lobby
session, after Phase 03 is verified and checked off, explicitly request:

```text
Implement plans/phase-04-room-and-lobby.md. Follow AGENTS.md and implement only this phase. Verify dependencies, run the required checks, update plans/plans.md only if all completion criteria are met, report the handoff, and stop.
```

Keep one phase per session. The master plan is the only progress ledger.
