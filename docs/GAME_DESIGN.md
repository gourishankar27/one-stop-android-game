# Spaceship game design

All numeric values below are **initial playtest assumptions**, not proven balance.
Change them in configuration, record the reason, and keep deterministic tests.
The pure engine is introduced in Phase 02; cooperative controls in Phase 09 and
emergencies in Phase 10. This document defines intended behavior, not current code.

## Round and communication

The crew survives for 90 seconds by steering, managing heat/power and protecting
the hull. All players win or lose together. They talk aloud; no microphone or
chat is needed. The host is a normal station operator with extra lobby permissions.

Create/join → ready lobby → host start → private station briefings → everyone
acknowledges → 3-second countdown → running → results → rematch or lobby.
The briefing acknowledgement limit is 60 seconds, outside the gameplay duration.
An incomplete briefing aborts the attempt. The server chooses a new round seed
and shuffles station ownership on each start/rematch.

For three players, shuffle the player roster using the round RNG and assign
Pilot, Engineer, Shields in that order. For two, the first shuffled player is
Pilot and the second owns Engineer plus Shields. Stations are fixed until the
round ends. Two-station mode has a large switch and urgent badges on the hidden
station; it never auto-operates either station. Test this workload with humans.

## Stations and information

| Station | Controls | Private information | Needs to say/hear |
| --- | --- | --- | --- |
| Pilot | Step left/right; evasive maneuver | Current lane, approaching impact lane, maneuver readiness | Tell crew which side needs cover; ask Engineer for output |
| Engineer | Output 0–100; boost; coolant; emergency shutdown | Exact output, temperature, power budget, heat warning details | Warn about heat; ask Shields to release demand; answer maneuver request |
| Shields | Activate/deactivate; facing; recharge; shield boost | Facing, exact energy, overload instructions | Ask for power; announce which side is protected |

Public state includes hull/shield percentage, round time/stage and warning labels.
No player receives another station's detailed instructions, even if they are host.
Engineer+Shields receives both owned views. A future display has no station views.
Pilot up/down controls and independently divided shield quadrants are deferred.

## Initial controls and physics

The engine uses 100 ms ticks. Ranges and initial values are in GAME_STATE.md.
No client supplies a delta time, player identity or authoritative resource values.

| Action / system | Initial rule |
| --- | --- |
| Pilot move | `move_lane(direction=left|right)` changes one lane; outside edge rejected; 2-tick cooldown |
| Pilot evade | Requires output >=60; maneuver active 10 ticks; 80-tick cooldown |
| Set output | Integer 0–100; reject if it cannot fund active consumers; no gameplay cooldown; transport rate limited |
| Engine boost | Requires 25 spare power; lasts 20 ticks; adds 4 heat units/tick; 100-tick cooldown |
| Coolant | Subtract 200 heat units, clamp at zero; 30-tick cooldown |
| Emergency shutdown | Set output to 0, cancel engine boost/recharge/shield boost, deactivate shields; always permitted to Engineer while running |
| Base heat | +2/tick at output >=60, otherwise -1/tick; clamp 0–1000 |
| Critical heat | At 1000, damage hull by 5 units/tick until temperature falls |
| Shield hold | Costs 15 power while active; drains 1 energy/tick; zero energy deactivates shields |
| Set shield | Both `active` boolean and `facing` front/left/right/rear are required; activating at zero energy rejected |
| Recharge | Requires 20 spare power; lasts 30 ticks; +6 energy/tick; 60-tick cooldown; may coexist with shield hold |
| Shield boost | Requires 25 spare power; lasts 10 ticks; adds 20 energy/tick; 150-tick cooldown |

Generation equals engine output. Consumer reservations apply for their duration;
available power = generation minus active reservations. The same action cannot
stack its own active effect. Cooldowns begin when accepted, not when requested.
Resource updates are applied each tick, clamped to bounds, then any zero-energy
deactivation releases power. Shutdown cancels active effects but keeps cooldowns.
Reject actions that fail stage, ownership, power or cooldown checks without any
partial mutation. Ship systems without emergencies provide a testable baseline;
the public party loop comes from emergency coordination.

## Emergency catalog

Start with three types. At most two active emergencies, at most one of each
type, and never spawn while paused/countdown/terminal. Resolved/failed events
are emitted once and removed from the active projection; bounded summaries may
be retained in results.

| Emergency | Start and private information | Resolution | Failure |
| --- | --- | --- | --- |
| Asteroid approach | Scheduled; 80-tick deadline; RNG chooses impact lane and facing; Pilot sees lane, Shields sees facing | At deadline: different lane with output >=60, or active evade; otherwise matching active shield with >=200 energy absorbs it and spends 200 | Hull -250 |
| Engine overheating | Temperature crosses >=800, if none active; 80-tick deadline; Engineer sees <=550 target and <=50 output requirement | Temperature <=550 and output <=50 before deadline | Hull -200; temperature reset to 650 |
| Shield overload | Scheduled; 70-tick deadline; Shields sees deactivate instruction, Engineer sees output <=45 request | Shield inactive and output <=45 for 20 consecutive ticks; reset progress if broken | Energy set to 0, shield deactivated; hull -100 |

Asteroid targets are evaluated at its deadline; earlier evasive actions may expire.
If both maneuver and shield conditions hold, maneuver wins and costs no shield
energy. Other emergency success checks precede deadline failure on the final tick.
Apply simultaneous emergency effects in stable emergency-ID order. Engine failure
checks then take precedence over victory if hull and time both reach zero.

Random scheduling starts at tick 80. At each scheduled slot choose uniformly from
eligible asteroid/overload kinds in stable enum order. When no kind/capacity is
eligible, skip the slot without retrying every tick. Next slot uses a seeded
integer interval; first third 80–120 ticks, middle third 60–100, final third
40–80. Overheat is threshold-triggered and consumes no RNG draw. A threshold
crossing while capacity is full is reconsidered once capacity opens if still hot.
Never pre-send the schedule or seed to clients. Navigation malfunction and an
independent power-shortage emergency are deferred; the Engineer can show a local
low-power indicator when free power is below 10, with no extra random event.

## End conditions and difficulty

Hull <=0 is defeat. Reaching the configured duration with hull >0 is victory.
There is no individual score or timer extension. Disconnect expiry, explicit
leave, briefing timeout and scheduler overload are aborted rounds with distinct
reasons, not defeats. A result records outcome/reason, survived milliseconds,
emergencies resolved/failed, final hull and the roster. Do not expose blame scores.

Difficulty initially changes only scheduled emergency intervals across thirds.
Two-player mode uses the same mechanics initially; Phase 15 may reduce overlaps
based on observations. Config should expose duration, hull damage, thresholds,
rates, event intervals, maximum active events and cooldowns. Keep a rules/config
version in reproduction data; do not claim balance before actual sessions.

## Questions for playtests

Can two-station players see urgent warnings without staring at menus? Does the
Pilot have enough to do between asteroids? Can a novice recover after a mistake?
Do people actually ask for power or do they play independently? Record round seed,
config version and observations privately; use consented local action traces when
needed for reproduction. Do not invent user feedback.
