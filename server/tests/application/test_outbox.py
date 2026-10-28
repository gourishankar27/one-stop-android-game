import asyncio

import pytest

from one_job.application.outbox import Outbox
from one_job.protocol.envelopes import PublicStateEnvelope, error_message, lobby_state
from one_job.protocol.mapping import public_view
from one_job.protocol.messages import ErrorCode, LobbyStatePayload, PublicStatePayload


def snapshot(engine, revision, *, reply_to=None, round_id=None):
    view = public_view(engine.snapshot())
    if round_id is not None:
        view = view.model_copy(update={"round_id": round_id})
    return PublicStateEnvelope(
        reply_to=reply_to,
        room_revision=revision,
        payload=PublicStatePayload(public=view),
    )


def lobby(revision, reply_to=None):
    return lobby_state(
        LobbyStatePayload(
            room_code="AAAAAA",
            stage="lobby",
            host_player_id=None,
            players=(),
            can_start=False,
        ),
        revision,
        reply_to,
    )


async def test_lobby_coalescing_preserves_correlated_reply_and_distinct_snapshot_type(engine):
    box = Outbox(3)
    assert box.offer(lobby(1))
    public = snapshot(engine, 2)
    correlated = lobby(2, "state")
    assert box.offer(public)
    assert box.offer(correlated)
    assert box.offer(lobby(2))
    assert (await box.get()).message == public
    assert (await box.get()).message == correlated
    assert (await box.get()).message == lobby(2)


async def test_coalesce_snapshot_at_tail_preserves_critical_reply_order(engine):
    box = Outbox(3)
    first = error_message(ErrorCode.INVALID_ACTION, "a")
    terminal = error_message(ErrorCode.COOLDOWN, "b")
    assert box.offer(first)
    assert box.offer(snapshot(engine, 1))
    assert box.offer(terminal)
    assert box.offer(snapshot(engine, 2))
    assert (await box.get()).message == first
    assert (await box.get()).message == terminal
    assert (await box.get()).message.room_revision == 2


async def test_full_queue_never_evicts_terminal_reply(engine):
    box = Outbox(2)
    first, second = (
        error_message(ErrorCode.INVALID_ACTION, "a"),
        error_message(ErrorCode.COOLDOWN, "b"),
    )
    assert box.offer(first)
    assert box.offer(second)
    assert not box.offer(snapshot(engine, 1))
    assert not box.offer(error_message(ErrorCode.INTERNAL_ERROR, "c"))
    assert (await box.get()).message == first
    assert (await box.get()).message == second


async def test_only_same_round_unsolicited_snapshots_coalesce(engine):
    box = Outbox(4)
    messages = [
        snapshot(engine, 1),
        snapshot(engine, 1, round_id="other"),
        snapshot(engine, 1, reply_to="state-a"),
        snapshot(engine, 1, reply_to="state-b"),
    ]
    for message in messages:
        assert box.offer(message)
    assert box.offer(snapshot(engine, 2))
    assert not box.offer(snapshot(engine, 2, reply_to="state-c"))
    for expected in [*messages[1:], snapshot(engine, 2)]:
        assert (await box.get()).message == expected


async def test_stale_snapshot_does_not_replace_or_reorder(engine):
    box = Outbox(2)
    current = snapshot(engine, 10)
    critical = error_message(ErrorCode.COOLDOWN)
    assert box.offer(current)
    assert box.offer(critical)
    assert box.offer(snapshot(engine, 9))
    assert (await box.get()).message == current
    assert (await box.get()).message == critical


async def test_close_wakes_consumer_and_rejects_new_messages():
    box = Outbox(1)
    consumer = asyncio.create_task(box.get())
    box.close()
    with pytest.raises(EOFError):
        await consumer
    assert not box.offer(error_message(ErrorCode.INTERNAL_ERROR))


@pytest.mark.parametrize("capacity", [0, -1, True, 1.5])
def test_invalid_capacity(capacity):
    with pytest.raises(ValueError):
        Outbox(capacity)
