"""Real room owner emits shared lifecycle once, with recipient-only targets."""

import json

import pytest

from one_job.application.outbox import Outbox
from one_job.domain.config import GameConfig
from one_job.domain.types import PlayerId
from one_job.protocol.envelopes import EmergencyEventEnvelope
from one_job.protocol.role_messages import EmergencyEventPayload
from tests.application.test_briefing_rounds import started as started
from tests.application.test_rooms import command


@pytest.mark.parametrize("count", [2, 3])
async def test_full_seeded_room_has_private_targets_and_once_only_lifecycles(clock, started, count):
    cfg = GameConfig(initial_temperature=799, initial_engine_output=60, first_emergency_tick=8)
    registry, room, peers, _ = await started(count, 71, cfg)
    round_id = str(room.round.round_id)
    for index, peer in enumerate(peers):
        await command(registry, peer, "briefing_ready", f"ack-{index}", round_id=round_id)
        peer.messages.clear()
    for _ in range(930):
        await clock.advance(0.1)
        await registry.synchronize()
        if room.stage == "finished":
            break
    assert room.stage == "finished"
    canonical = None
    public_by_revision = {}
    for identity, peer in zip(room.members, peers, strict=True):
        lifecycle = [m for m in peer.messages if m.type == "emergency_event"]
        assert lifecycle
        if canonical is None:
            canonical = lifecycle
        else:
            assert lifecycle == canonical
        keys = [(m.payload.emergency_id, m.payload.status) for m in lifecycle]
        assert len(keys) == len(set(keys))
        assert set(lifecycle[0].payload.model_dump()) == {
            "round_id",
            "emergency_id",
            "kind",
            "status",
        }
        assert all(m.reply_to is None for m in lifecycle)
        expected = {
            role.value
            for role in room.round.engine.snapshot().assignments.roles_for(PlayerId(identity))
        }
        terminal = []
        for message in peer.messages:
            if message.type != "role_state":
                continue
            assert set(message.payload.stations) == expected
            public = message.payload.public.model_dump(mode="json")
            assert (
                not {
                    "seed",
                    "next_slot",
                    "impact_lane",
                    "required_facing",
                    "progress_ticks",
                    "target_max_output",
                }
                & public.keys()
            )
            assert all(
                set(warning) == {"emergency_id", "kind", "label"} for warning in public["warnings"]
            )
            public_by_revision.setdefault(message.room_revision, public)
            assert public_by_revision[message.room_revision] == public
            if public["result"] is not None:
                terminal.append(public)
            for role, view in message.payload.stations.items():
                data = view.model_dump(mode="json")
                if role == "pilot":
                    assert all(
                        set(h) == {"emergency_id", "impact_lane", "deadline_remaining_ms"}
                        for h in data["hazards"]
                    )
                    assert "instructions" not in data
                elif role == "engineer":
                    assert all(
                        set(h)
                        == {
                            "emergency_id",
                            "target_max_output",
                            "target_max_temperature",
                            "deadline_remaining_ms",
                        }
                        for h in data["instructions"]
                    )
                    assert "hazards" not in data
                else:
                    assert all(
                        set(h)
                        == {
                            "emergency_id",
                            "required_facing",
                            "deactivate",
                            "deadline_remaining_ms",
                        }
                        for h in data["instructions"]
                    )
        assert len(terminal) == 1
        result = terminal[0]["result"]
        assert result["resolved_count"] == sum(m.payload.status == "resolved" for m in lifecycle)
        assert result["failed_count"] == sum(m.payload.status == "failed" for m in lifecycle)
        before = len(lifecycle)
        await command(registry, peer, "request_state", f"state-{identity.int}")
        assert len([m for m in peer.messages if m.type == "emergency_event"]) == before
        assert not any(
            word in json.dumps([m.model_dump(mode="json") for m in lifecycle])
            for word in ("impact_lane", "required_facing", "temperature", "seed", "next_slot")
        )
    old = room.round.engine.snapshot()
    await clock.advance(10)
    await registry.synchronize()
    assert room.round.engine.snapshot() is old and not room.round.runner.next_deadline


async def test_shared_lifecycle_events_are_critical_and_not_snapshot_coalesced():
    box = Outbox(2)

    def frame(status):
        return EmergencyEventEnvelope(
            room_revision=1,
            payload=EmergencyEventPayload(
                round_id="00000000-0000-0000-0000-000000000099",
                emergency_id=1,
                kind="asteroid",
                status=status,
            ),
        )

    first = frame("started")
    second = frame("resolved")
    assert box.offer(first) and box.offer(second) and not box.offer(first)
    assert (await box.get()).message == first and (await box.get()).message == second
