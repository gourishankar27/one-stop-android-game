# Phase 13 — Audio, Haptics and Presentation

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Improve readable feedback and local party-game presentation after gameplay works.

## Why this phase exists

Players need to notice accepted actions and urgency while still hearing one another.

## Dependencies

Phase 11 complete. Phase 12 is optional; polish its display only if it exists.

## In scope

Role identity, short licensed/generated sound effects, bounded alarms, countdown feedback, local haptics, typography, transitions, reduced motion and audio/haptics settings.

## Explicitly out of scope

No rule/balance rewrite, extra game systems, background audio service, mandatory cloud assets, final marketing art or elaborate animation.

## Architecture considerations

Feedback consumes authoritative events/snapshots and cannot trigger rules. Deduplicate sound/haptic effects by round/event IDs so resuming a snapshot does not replay alarms. Local settings never alter server urgency/deadlines.

## Files likely to be created or modified

Android ui/theme and feedback helpers; settings persistence; resource audio assets and attribution file; ViewModel/event mapping tests; UI/accessibility test notes.

## Data models / APIs involved

Local FeedbackPreferences(audioEnabled,hapticsEnabled,reducedMotion) and an event-to-feedback mapper. Reuse existing emergency IDs/round IDs; no new game-authority DTO is required.

## Implementation tasks

1. Check current readability and input feedback on actual phones before adding effects. Pick a restrained role label/color/icon scheme with text redundancy.
2. Add short countdown, accepted/rejected and urgent warning cues. Limit simultaneous/repeated alarms and pause local feedback when the app is not visible.
3. Use platform haptics with a local toggle. Keep every essential warning visible as text even with audio/haptics disabled.
4. Persist local preferences without session credentials; deduplicate feedback on reconnect, navigation recreation and full-state replay.
5. Check text scaling, contrast, TalkBack labels/traversal, 48dp controls and reduced-motion behavior. Avoid flashes or continuous effects that compete with conversation.
6. Record the source/license of included audio/art assets. Do not invent asset rights or add unrelated visual systems.

## Testing requirements

JVM tests cover event deduplication and preferences; Compose tests cover accessible labels/settings. Run Gradle build/lint/tests. Manual device checks with sound off, haptics off, large fonts, TalkBack and reconnect snapshots are required.

## Manual verification

Play a short round with friends in the same room and confirm voices remain audible. Repeat with feedback disabled and increased text size. Resume the app and confirm no stale alarm storm.

## Completion criteria

Feedback is optional, readable and lifecycle-safe; settings persist; essential information remains accessible without sound/color; asset rights are documented; game rules remain unchanged.

## Documentation updates

Update UI_UX.md, asset attribution, Android README settings and TESTING.md accessibility evidence. Record observed limits without calling the result final visual design.

## Handoff notes for next phase

Phase 14 must retest lifecycle/feedback interaction if this phase is implemented; it can otherwise proceed on the plain UI.

