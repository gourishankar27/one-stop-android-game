"""Observer identity, permissions, public-only delivery and independent recovery."""

import json
from uuid import UUID

import pytest

from one_job.domain.config import GameConfig
from one_job.domain.types import ResultReason
from one_job.protocol.envelopes import encode_message
from tests.application.test_briefing_rounds import started as started
from tests.application.test_room_runner import live
from tests.application.test_rooms import Peer, command
from tests.application.test_round_lifecycle import steps


def receipt(peer):
    return next(m.payload for m in peer.messages if m.type == "session_accepted")


def public_only(peer):
    assert {m.type for m in peer.messages} <= {
        "session_accepted",
        "lobby_state",
        "public_state",
        "ack",
        "error",
        "pong",
    }
    for message in peer.messages:
        if message.type == "public_state":
            value = json.loads(encode_message(message))
            assert set(value["payload"]) == {"public"}
            if value["payload"]["public"] is not None:
                assert set(value["payload"]["public"]) == {
                    "round_id",
                    "stage",
                    "tick_index",
                    "remaining_ms",
                    "countdown_remaining_ms",
                    "paused_from",
                    "hull_percent",
                    "shield_percent",
                    "warnings",
                    "result",
                }
            keys = set()

            def visit(item, keys=keys):
                if isinstance(item, dict):
                    keys.update(item)
                    for child in item.values():
                        visit(child)
                elif isinstance(item, list):
                    for child in item:
                        visit(child)

            visit(value)
            assert not keys & {
                "seed",
                "config",
                "stations",
                "roles",
                "instructions",
                "temperature",
                "lane",
                "available_power",
                "cooldowns",
                "impact_lane",
                "required_facing",
                "max_output",
                "max_temperature",
                "assignments",
                "owners",
                "resume_token",
            }


@pytest.mark.parametrize(
    "stage", ["lobby", "briefing", "countdown", "running", "paused", "finished", "aborted"]
)
@pytest.mark.parametrize("count", [2, 3])
async def test_admits_at_every_stage_with_only_public_snapshots(started, count, stage, monkeypatch):
    registry, room, players, _ = await started(
        count,
        seed=109876543210987,
        config=GameConfig(version="PRIVATE_CONFIG_SENTINEL", emergencies_enabled=False),
    )

    def prepare():
        engine = room.round.engine
        if stage == "lobby":
            room.round = None
            room.stage = "lobby"
            return
        if stage == "countdown":
            engine.begin_countdown()
        elif stage in ("running", "paused", "finished"):
            engine.start()
            if stage == "paused":
                engine.pause()
            elif stage == "finished":
                engine.tick(engine.snapshot().config.duration_ticks)
        elif stage == "aborted":
            engine.abort(ResultReason.BRIEFING_TIMEOUT)
        room.stage = room.round.stage

    await room.submit(prepare)
    if room.round is not None:

        def private(*args):
            raise AssertionError("PRIVATE_STATION_SENTINEL")

        monkeypatch.setattr(room.round, "view", private)
        monkeypatch.setattr(room.round, "assigned", private)
    before = room.view(), room.revision, room.idle_deadline, tuple(room.members)
    display = Peer(20)
    assert await command(registry, display, "join_display", "display", room_code=room.code) is None
    accepted = receipt(display)
    assert accepted.kind == "display" and accepted.player_id is None
    assert accepted.resume_token not in {
        receipt_token
        for receipt_token in (registry.issuer.token(identity) for identity in room.members)
    }
    assert len(room.members) == count and len(room.displays) == 1
    assert (room.view(), room.revision, room.idle_deadline, tuple(room.members)) == before
    state = display.messages[-1].payload.public
    assert state is None if stage == "lobby" else state.stage == stage
    await command(registry, display, "request_state", "state")
    assert display.messages[-1].reply_to == "state"
    assert display.messages[-1].type == "public_state"
    public_only(display)
    data = " ".join(encode_message(m) for m in display.messages)
    assert "PRIVATE_" not in data and "109876543210987" not in data


ACTIONS = [
    {"type": "move_lane", "direction": "left"},
    {"type": "evade"},
    {"type": "set_engine_power", "value": 40},
    {"type": "engine_boost"},
    {"type": "coolant"},
    {"type": "emergency_shutdown"},
    {"type": "set_shield", "active": True, "facing": "left"},
    {"type": "recharge_shield"},
    {"type": "shield_boost"},
]
FORBIDDEN = [
    ("create_room", {"name": "Display"}),
    ("join_room", {"room_code": "ABCD23", "name": "Crew"}),
    ("join_display", {"room_code": "ABCD23"}),
    ("player_ready", {"ready": True}),
    ("start_game", {}),
    ("briefing_ready", {"round_id": str(UUID(int=99))}),
    ("play_again", {}),
    ("return_to_lobby", {}),
] + [
    ("player_action", {"round_id": str(UUID(int=99)), "client_action_seq": 1, "action": a})
    for a in ACTIONS
]


@pytest.mark.parametrize("kind,payload", FORBIDDEN)
async def test_every_control_command_is_rejected_before_player_dispatch(started, kind, payload):
    registry, room, _, _ = await started(3)
    display = Peer(20)
    await command(registry, display, "join_display", "join", room_code=room.code)
    before = room.view(), room.round.engine.snapshot(), room.revision, room.idle_deadline
    assert await command(registry, display, kind, "forged", **payload) == "not_controller"
    first = display.messages[-1]
    assert first.type == "error" and first.reply_to == "forged"
    assert await command(registry, display, kind, "forged", **payload) == "not_controller"
    assert display.messages[-1] == first
    assert (room.view(), room.round.engine.snapshot(), room.revision, room.idle_deadline) == before
    public_only(display)


async def test_capacity_grace_fencing_and_controllerless_room_expiry(clock, started):
    registry, room, players, _ = await started(3)
    # Setup lobby before observing whether display operations alter ready flags.
    await room.submit(lambda: setattr(room, "round", None))
    await room.submit(lambda: setattr(room, "stage", "lobby"))
    for index, player in enumerate(players):
        await command(registry, player, "player_ready", f"ready-again-{index}", ready=True)
    before = room.view(), room.revision, room.idle_deadline
    displays = [Peer(20), Peer(21)]
    for index, display in enumerate(displays):
        await command(registry, display, "join_display", f"display-{index}", room_code=room.code)
    third = Peer(22)
    assert (
        await command(registry, third, "join_display", "full", room_code=room.code)
        == "display_full"
    )
    token = receipt(displays[0]).resume_token
    await registry.disconnect(displays[0])
    assert (
        await command(registry, third, "join_display", "still-full", room_code=room.code)
        == "display_full"
    )
    replacement = Peer(23)
    await command(registry, replacement, "resume_session", "resume", resume_token=token)
    assert receipt(replacement).kind == "display" and receipt(replacement).resume_token == token
    fenced = Peer(24)
    await command(registry, fenced, "resume_session", "duplicate", resume_token=token)
    assert replacement.close_code == 1008
    await registry.disconnect(replacement)
    assert (room.view(), room.revision, room.idle_deadline) == before
    await registry.disconnect(fenced)
    await clock.advance(30)
    await registry.synchronize()
    assert len(room.displays) == 1 and (room.view(), room.revision, room.idle_deadline) == before
    expired = Peer(25)
    assert (
        await command(registry, expired, "resume_session", "expired", resume_token=token)
        == "session_expired"
    )
    assert await command(registry, third, "join_display", "space", room_code=room.code) is None
    for index, player in enumerate(players):
        await command(registry, player, "leave_room", f"leave-{index}")
    assert registry.room_count == registry.session_count == 0
    assert all(d.close_code == 1008 for d in [displays[1], third])


async def test_display_disconnect_does_not_pause_countdown_or_running(clock, started):
    registry, room, players, _ = await started(2)
    display = Peer(20)
    await command(registry, display, "join_display", "join", room_code=room.code)
    token = receipt(display).resume_token
    for index, player in enumerate(players):
        await command(
            registry, player, "briefing_ready", f"ack-{index}", round_id=str(room.round.round_id)
        )
    await registry.disconnect(display)
    await steps(clock, registry, 30)
    assert room.stage == "running" and room.round.engine.snapshot().tick_index == 0
    await steps(clock, registry, 10)
    replacement = Peer(21)
    await command(registry, replacement, "resume_session", "resume", resume_token=token)
    assert replacement.messages[-1].payload.public.tick_index == 10
    await registry.disconnect(replacement)
    await steps(clock, registry, 10)
    assert room.stage == "running" and room.round.engine.snapshot().tick_index == 20


async def test_public_terminal_is_stable_and_return_clears_cached_round(clock, started):
    registry, room, players, _ = await live(started, 3)
    display = Peer(20)
    await command(registry, display, "join_display", "join", room_code=room.code)
    await steps(clock, registry, registry.game_config.duration_ticks)
    assert room.stage == "finished"
    assert display.messages[-1].payload.public.result.outcome == "victory"
    await command(registry, display, "request_state", "cached")
    await command(registry, players[0], "return_to_lobby", "return")
    assert display.messages[-1].payload.public is None
    await command(registry, display, "request_state", "cached")
    assert display.messages[-1].reply_to == "cached" and display.messages[-1].payload.public is None
    public_only(display)


async def test_display_cannot_extend_idle_or_survive_room_deletion(clock, started):
    registry, room, _, _ = await started(2)
    display = Peer(20)
    await command(registry, display, "join_display", "join", room_code=room.code)
    token = receipt(display).resume_token
    deadline = room.idle_deadline
    await clock.advance(10)
    await command(registry, display, "ping", "ping", nonce="alive")
    await command(registry, display, "request_state", "state")
    assert room.idle_deadline == deadline
    await clock.advance(deadline - clock.now())
    await registry.synchronize()
    assert display.close_code == 1008 and registry.room_count == registry.session_count == 0
    assert (
        await command(registry, Peer(21), "resume_session", "lost", resume_token=token)
        == "session_expired"
    )
