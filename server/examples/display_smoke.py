"""Real observers plus 2/3 players; inspect allowlists without exporting private frames."""

import argparse
import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any

from role_smoke import PUBLIC_FIELDS, STATION_FIELDS, receive, send
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed


async def check(url: str, count: int) -> None:
    async with AsyncExitStack() as stack, asyncio.timeout(150):
        peers = [await stack.enter_async_context(connect(url)) for _ in range(count)]
        await send(peers[0], "create_room", "create", {"name": "Captain"})
        admitted = (await receive(peers[0], "session_accepted", "create"))["payload"]
        for index, peer in enumerate(peers[1:]):
            await send(
                peer,
                "join_room",
                f"join-{index}",
                {"name": "Crew", "room_code": admitted["room_code"]},
            )
            await receive(peer, "session_accepted", f"join-{index}")
        shared: dict[int, dict[str, Any]] = {}
        warning = asyncio.Event()
        progressed = asyncio.Event()
        latest_tick = 0
        warning_labels: set[str] = set()

        def public_check(frame: dict[str, Any], public: dict[str, Any]) -> None:
            assert set(public) == PUBLIC_FIELDS
            assert shared.setdefault(frame["room_revision"], public) == public
            assert all(
                set(item) == {"emergency_id", "kind", "label"} for item in public["warnings"]
            )
            assert not {
                "stations",
                "seed",
                "config",
                "targets",
                "instructions",
                "assignments",
            } & set(public)

        async def display_read(socket: ClientConnection) -> dict[str, Any]:
            frame: dict[str, Any] = json.loads(await socket.recv())
            assert frame["type"] in {
                "session_accepted",
                "lobby_state",
                "public_state",
                "error",
                "ack",
                "pong",
            }
            payload = frame["payload"]
            if frame["type"] == "session_accepted":
                assert payload["kind"] == "display" and payload["player_id"] is None
                assert payload["resume_token"] != admitted["resume_token"]
            elif frame["type"] == "lobby_state":
                assert len(payload["players"]) == count
            elif frame["type"] == "public_state":
                assert set(payload) == {"public"}
                if payload["public"] is not None:
                    public_check(frame, payload["public"])
            return frame

        async def display_receive(socket: ClientConnection, kind: str) -> dict[str, Any]:
            while True:
                frame = await display_read(socket)
                if frame["type"] == kind:
                    return frame
                assert frame["type"] != "error"

        first = await stack.enter_async_context(connect(url))
        await send(first, "join_display", "display-lobby", {"room_code": admitted["room_code"]})
        credential = (await display_receive(first, "session_accepted"))["payload"]["resume_token"]
        assert (await display_receive(first, "public_state"))["payload"]["public"] is None
        for index, peer in enumerate(peers):
            await send(peer, "player_ready", f"ready-{index}", {"ready": True})
            await receive(peer, "ack", f"ready-{index}")
        for kind, payload in [("player_ready", {"ready": False}), ("start_game", {})]:
            await send(first, kind, f"forged-{kind}", payload)
            assert (await display_receive(first, "error"))["payload"]["code"] == "not_controller"
        await send(peers[0], "request_state", "ready-proof")
        assert all(
            p["ready"]
            for p in (await receive(peers[0], "lobby_state", "ready-proof"))["payload"]["players"]
        )
        await send(peers[0], "start_game", "start")
        await receive(peers[0], "ack", "start")
        roles = [(await receive(peer, "role_assigned"))["payload"] for peer in peers]
        round_id = roles[0]["round_id"]
        await send(
            first,
            "player_action",
            "forged-action",
            {"round_id": round_id, "client_action_seq": 1, "action": {"type": "coolant"}},
        )
        assert (await display_receive(first, "error"))["payload"]["code"] == "not_controller"
        for index, peer in enumerate(peers):
            await send(peer, "briefing_ready", f"read-{index}", {"round_id": round_id})
            await receive(peer, "ack", f"read-{index}")
        for peer in peers:
            while (await receive(peer, "role_state"))["payload"]["public"]["stage"] != "running":
                pass
        late = await stack.enter_async_context(connect(url))
        await send(late, "join_display", "display-running", {"room_code": admitted["room_code"]})
        await display_receive(late, "session_accepted")
        assert (await display_receive(late, "public_state"))["payload"]["public"][
            "stage"
        ] == "running"
        full = await stack.enter_async_context(connect(url))
        await send(full, "join_display", "display-full", {"room_code": admitted["room_code"]})
        assert (await display_receive(full, "error"))["payload"]["code"] == "display_full"
        await full.close()

        async def controller(index: int) -> dict[str, Any]:
            nonlocal latest_tick
            heartbeat = 0
            async for raw in peers[index]:
                frame = json.loads(raw)
                if frame["type"] != "role_state":
                    continue
                payload = frame["payload"]
                public = payload["public"]
                public_check(frame, public)
                assert set(payload["stations"]) == set(roles[index]["roles"])
                for role, view in payload["stations"].items():
                    assert set(view) == STATION_FIELDS[role]
                assert public["stage"] != "paused", "Observer disconnect paused players"
                if public["result"] is not None:
                    result: dict[str, Any] = public["result"]
                    return result
                if index == 0:
                    latest_tick = public["tick_index"]
                    progressed.set()
                if public["tick_index"] >= heartbeat:
                    await send(
                        peers[index], "ping", f"ping-{index}-{heartbeat}", {"nonce": "alive"}
                    )
                    heartbeat = public["tick_index"] + 100
            raise AssertionError("player closed before terminal")

        async def observer(socket: ClientConnection) -> dict[str, Any] | None:
            heartbeat = 0
            try:
                while True:
                    frame = await display_read(socket)
                    if frame["type"] != "public_state" or frame["payload"]["public"] is None:
                        continue
                    public = frame["payload"]["public"]
                    if public["warnings"]:
                        warning_labels.update(item["kind"] for item in public["warnings"])
                        warning.set()
                    if public["result"] is not None:
                        result: dict[str, Any] = public["result"]
                        return result
                    if public["tick_index"] >= heartbeat:
                        await send(socket, "ping", f"display-ping-{heartbeat}", {"nonce": "alive"})
                        heartbeat = public["tick_index"] + 100
            except ConnectionClosed:
                return None

        # TaskGroup cancels/awaits the readers on any assertion, timeout or disconnect.
        async with asyncio.TaskGroup() as group:
            player_tasks = [group.create_task(controller(index)) for index in range(count)]
            first_task = group.create_task(observer(first))
            late_task = group.create_task(observer(late))
            await warning.wait()
            await first.close()
            assert await first_task is None
            baseline = latest_tick
            while latest_tick <= baseline + 3:
                progressed.clear()
                await progressed.wait()
            resumed = await stack.enter_async_context(connect(url))
            await send(resumed, "resume_session", "display-resume", {"resume_token": credential})
            assert (await display_receive(resumed, "session_accepted"))["payload"][
                "resume_token"
            ] == credential
            resumed_task = group.create_task(observer(resumed))
        results = [task.result() for task in [*player_tasks, late_task, resumed_task]]
        assert results[0] is not None and all(result == results[0] for result in results)
        assert warning_labels
        for index, peer in enumerate([resumed, late, *peers]):
            await send(peer, "leave_room", f"leave-{index}")
            await receive(peer, "ack", f"leave-{index}")
        print(
            f"{count} players + 2 displays: lobby/running admission, capacity, wire allowlists, "
            "control rejection, unpaused recovery, warnings and "
            f"matching {results[0]['outcome']} passed",
            flush=True,
        )


async def main(url: str) -> None:
    await asyncio.gather(check(url, 2), check(url, 3))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="ws://127.0.0.1:8765/ws")
    asyncio.run(main(parser.parse_args().url))
