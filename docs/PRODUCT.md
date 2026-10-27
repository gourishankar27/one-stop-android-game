# Product

## People and setting

One Job is for 2–3 friends sitting together, each with an Android phone and
access to the same backend. They talk aloud. No game account or embedded voice
chat is needed. The first session should teach controls quickly enough that a
person who rarely plays games can participate.

The first scenario is a spaceship. Each station has information another station
needs, and controls that affect another station's work. Mistakes should create
recoverable trouble before causing team defeat. There is no secret traitor or
individual winner in the MVP.

## Session

A player creates a room and shares its short code. Friends join with names.
The host starts once everyone is connected and ready. Players see assigned
stations, read a short briefing, acknowledge it, then play a timed round. Victory
means surviving to the end; hull destruction means defeat. The results page
offers the host a rematch or a return to lobby.

## Product principles

- Communication must matter: avoid giving every phone the same detailed view.
- Controls should be large and understandable with short labels.
- Outcomes and rejected actions need clear feedback; confusion about another
  player's warning can be funny, confusion about a broken connection is not.
- One round takes 60–120 seconds, initially 90. Briefings sit outside that time.
- Keep cooperation necessary without requiring precise twitch input or reading
  paragraphs during a round.

## MVP boundary

The full gameplay loop targets Phases 00–11. The complete MVP also needs the
reconnection behavior verified in Phase 14 and an actual playtest pass in Phase 15.
Phase 12 public display and Phase 13 presentation polish are optional additions.

The MVP includes Android phones, Python/FastAPI, in-memory rooms, a host, ready
state, short codes, names, Pilot/Engineer/Shield Operator stations, deterministic
server simulation, three basic emergency types, results, rematches, reconnect,
redacted operational logs and automated engine/server/client checks.

For three players, assign one station each. For two, one player is Pilot and
the other owns Engineer and Shield Operator, with a station switch. No station
is automated. This is a provisional playtest assumption, not an additional role.
More than three controllers is outside the MVP; a future display is an observer.

## Non-goals

No accounts, email/social login, permanent profiles, stranger matchmaking, chat,
leaderboards, achievements, cosmetics, currency, ads, subscriptions, purchases,
cloud saves, database persistence, AI players, advanced analytics, anti-cheat
system, iOS/desktop/web client, Android TV or casting integration.
Basic permission checks, limits and credential hygiene still belong to a usable
multiplayer server; they do not require an anti-cheat platform.

## Later directions

An extra Android device can show only public state in Phase 12. Easier LAN
discovery is investigated in Phase 16. A submarine is the proposed second
scenario in Phase 17, after observed spaceship playtests justify continuing.
Other ideas include a kitchen, reactor, pirate ship, airport, bank heist, haunted
house and space station. None requires implementation in the foundation.

Success criteria for playtesting: friends can enter a room without developer
help, explain their controls after a briefing, name moments where communication
changed an outcome, and choose whether they want another round. Record actual
observations; there is no evidence for fun or balance yet.
