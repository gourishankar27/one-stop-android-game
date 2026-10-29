"""Exercise Phase 04 with three local clients; never print session credentials."""

import argparse
import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed


async def receive(socket: ClientConnection) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(await socket.recv())
    return value


async def send(
    socket: ClientConnection, kind: str, request_id: str, payload: dict[str, Any] | None = None
) -> None:
    await socket.send(
        json.dumps(
            {
                "version": 1,
                "type": kind,
                "request_id": request_id,
                "payload": payload or {},
            }
        )
    )


async def admission(
    socket: ClientConnection, request_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    accepted, snapshot = await receive(socket), await receive(socket)
    assert accepted["type"] == "session_accepted" and accepted["reply_to"] == request_id
    assert snapshot["type"] == "lobby_state" and snapshot["reply_to"] is None
    assert accepted["room_revision"] == snapshot["room_revision"]
    return accepted["payload"], snapshot


def same(*states: dict[str, Any]) -> None:
    assert all(state["type"] == "lobby_state" for state in states)
    assert all(state["payload"] == states[0]["payload"] for state in states)
    assert all(state["room_revision"] == states[0]["room_revision"] for state in states)


async def expect_close(socket: ClientConnection, code: int) -> None:
    try:
        await socket.recv()
    except ConnectionClosed as error:
        assert error.rcvd is not None and error.rcvd.code == code
    else:
        raise AssertionError("expected close")


async def check(url: str) -> None:
    async with AsyncExitStack() as stack:
        clients = [
            await stack.enter_async_context(connect(url, open_timeout=3, close_timeout=1))
            for _ in range(3)
        ]
        host, guest, third = clients
        await send(host, "create_room", "create", {"name": " Captain "})
        host_session, state = await admission(host, "create")
        code = host_session["room_code"]
        sessions = [host_session]
        for index, socket in enumerate(clients[1:], 1):
            await send(
                socket, "join_room", f"join-{index}", {"name": "Crew", "room_code": code.lower()}
            )
            session, state = await admission(socket, f"join-{index}")
            sessions.append(session)
            same(state, *[await receive(peer) for peer in clients[:index]])
        assert len(state["payload"]["players"]) == 3
        assert len({session["player_id"] for session in sessions}) == 3
        print(
            f"Create + two joins: three distinct players, shared revision {state['room_revision']}"
        )
        for index, socket in enumerate(clients):
            await send(socket, "player_ready", f"ready-{index}", {"ready": True})
            ack = await receive(socket)
            assert ack["type"] == "ack" and ack["reply_to"] == f"ready-{index}"
            snapshots = [await receive(peer) for peer in clients]
            same(*snapshots)
            assert ack["room_revision"] == snapshots[0]["room_revision"]
            state = snapshots[0]
        assert state["payload"]["can_start"]
        await send(guest, "start_game", "start")
        response = await receive(guest)
        assert response["payload"]["code"] == "not_host"
        assert response["room_revision"] == state["room_revision"]
        print("Ready: all clients agree; non-host Start rejected without leaving lobby")
        await send(third, "leave_room", "leave-third")
        assert (await receive(third))["type"] == "ack"
        await expect_close(third, 1000)
        same(await receive(host), await receive(guest))
        await guest.close()
        disconnected = await receive(host)
        assert len(disconnected["payload"]["players"]) == 2
        assert not all(player["connected"] for player in disconnected["payload"]["players"])
        replacement = await stack.enter_async_context(connect(url, open_timeout=3, close_timeout=1))
        await send(
            replacement, "resume_session", "resume", {"resume_token": sessions[1]["resume_token"]}
        )
        resumed_session, resumed = await admission(replacement, "resume")
        assert resumed_session == sessions[1]
        same(resumed, await receive(host))
        assert all(
            player["connected"] and not player["ready"] for player in resumed["payload"]["players"]
        )
        shared = json.dumps([state, disconnected, resumed])
        assert all(session["resume_token"] not in shared for session in sessions)
        print(
            "Leave + disconnect/resume: identity/token stable, "
            f"shared revision {resumed['room_revision']}, readiness reset"
        )
        await send(host, "leave_room", "leave-host")
        assert (await receive(host))["type"] == "ack"
        await expect_close(host, 1000)
        transferred = await receive(replacement)
        assert transferred["payload"]["host_player_id"] == resumed_session["player_id"]
        await send(replacement, "leave_room", "leave-last")
        assert (await receive(replacement))["type"] == "ack"
        await expect_close(replacement, 1000)
        print("Host transfer and final leave: normal closes; no gameplay launched")


async def main(url: str) -> None:
    async with asyncio.timeout(20):
        await check(url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="ws://127.0.0.1:8000/ws")
    args = parser.parse_args()
    asyncio.run(main(args.url))
