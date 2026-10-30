"""Three real-time cycles per 2/3-player room against the local lifecycle profile.

Use emergency_harness.py --profile lifecycle --seed 71. No private frames or
credentials are exported. This scripted check does not replace a phone playtest.
"""

import argparse
import asyncio
import json
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

from role_smoke import PUBLIC_FIELDS, STATION_FIELDS, send
from websockets.asyncio.client import ClientConnection, connect


@dataclass
class Peer:
    socket: ClientConnection
    shared: dict[int, dict[str, Any]]
    roles: list[str] = field(default_factory=list)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)

    async def read(self) -> dict[str, Any]:
        frame: dict[str, Any] = json.loads(await self.socket.recv())
        payload = frame["payload"]
        if frame["type"] == "role_assigned":
            self.roles = payload["roles"]
        elif frame["type"] == "role_state":
            public = payload["public"]
            assert set(public) == PUBLIC_FIELDS
            assert set(payload["stations"]) == set(self.roles)
            for role, view in payload["stations"].items():
                assert set(view) == STATION_FIELDS[role]
            revision = frame["room_revision"]
            assert self.shared.setdefault(revision, public) == public
        elif frame["type"] == "game_over":
            assert set(payload) == {"round_id", "result"}
            assert payload["round_id"] not in self.results
            self.results[payload["round_id"]] = payload["result"]
        return frame

    async def receive(self, kind: str, reply: str | None = None) -> dict[str, Any]:
        while True:
            frame = await self.read()
            if frame["type"] == kind and (reply is None or frame["reply_to"] == reply):
                return frame
            assert frame["type"] not in ("error", "action_rejected"), frame["type"]

    async def command(
        self, kind: str, request: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        await send(self.socket, kind, request, payload)
        return await self.receive("ack", request)

    async def stage(self, stage: str) -> dict[str, Any]:
        while True:
            public: dict[str, Any] = (await self.receive("role_state"))["payload"]["public"]
            if public["stage"] == stage:
                return public


async def check(url: str, count: int) -> None:
    async with AsyncExitStack() as stack, asyncio.timeout(220):
        shared: dict[int, dict[str, Any]] = {}
        peers = [Peer(await stack.enter_async_context(connect(url)), shared) for _ in range(count)]
        await send(peers[0].socket, "create_room", "create", {"name": "Captain"})
        admission = (await peers[0].receive("session_accepted", "create"))["payload"]
        credentials = [admission]
        for index, peer in enumerate(peers[1:], 1):
            await send(
                peer.socket,
                "join_room",
                f"join-{index}",
                {"name": f"Crew {index}", "room_code": admission["room_code"]},
            )
            credentials.append((await peer.receive("session_accepted"))["payload"])
        previous = None
        for cycle in range(3):
            prefix = f"cycle-{cycle}"
            for index, peer in enumerate(peers):
                await peer.command("player_ready", f"{prefix}-ready-{index}", {"ready": True})
            await peers[0].command("start_game" if cycle == 0 else "play_again", prefix)
            assignments = [(await peer.receive("role_assigned"))["payload"] for peer in peers]
            round_id = assignments[0]["round_id"]
            assert round_id != previous
            assert all(item["round_id"] == round_id for item in assignments)
            if previous is not None:
                await send(
                    peers[0].socket, "briefing_ready", f"{prefix}-old-read", {"round_id": previous}
                )
                assert (await peers[0].receive("error"))["payload"]["code"] == "stale_round"
                await send(
                    peers[0].socket,
                    "player_action",
                    f"{prefix}-old-action",
                    {
                        "round_id": previous,
                        "client_action_seq": 999,
                        "action": {"type": "coolant"},
                    },
                )
                assert (await peers[0].receive("action_rejected"))["payload"][
                    "code"
                ] == "stale_round"
            for index, peer in enumerate(peers):
                await peer.command(
                    "briefing_ready", f"{prefix}-read-{index}", {"round_id": round_id}
                )
            countdowns = await asyncio.gather(*(peer.stage("countdown") for peer in peers))
            assert all(item["countdown_remaining_ms"] == 3000 for item in countdowns)
            assert all(item["tick_index"] == 0 for item in countdowns)
            if cycle == 0:
                await peers[-1].socket.close()
                paused = await peers[0].stage("paused")
                assert paused["paused_from"] == "countdown" and paused["tick_index"] == 0
                peers[-1].socket = await stack.enter_async_context(connect(url))
                await send(
                    peers[-1].socket,
                    "resume_session",
                    "resume-countdown",
                    {"resume_token": credentials[-1]["resume_token"]},
                )
                await peers[-1].receive("session_accepted", "resume-countdown")
                resumed = await peers[-1].stage("countdown")
                assert resumed["countdown_remaining_ms"] == paused["countdown_remaining_ms"]
            starts = await asyncio.gather(*(peer.stage("running") for peer in peers))
            assert all(
                item["tick_index"] == 0 and item["remaining_ms"] == 60_000 for item in starts
            )
            engineer = next(peer for peer in peers if "engineer" in peer.roles)
            ack = await engineer.command(
                "player_action",
                f"{prefix}-first-action",
                {"round_id": round_id, "client_action_seq": 1, "action": {"type": "coolant"}},
            )
            assert ack["payload"]["client_action_seq"] == 1

            async def finish(
                index: int, peer: Peer, prefix: str = prefix, round_id: str = round_id
            ) -> dict[str, Any]:
                terminal: dict[str, Any] | None = None
                heartbeat = 0
                while True:
                    frame = await peer.read()
                    if frame["type"] == "role_state":
                        public = frame["payload"]["public"]
                        if public["result"] is not None:
                            terminal = public["result"]
                        elif public["tick_index"] >= heartbeat:
                            await send(
                                peer.socket,
                                "ping",
                                f"{prefix}-ping-{index}-{heartbeat}",
                                {"nonce": "alive"},
                            )
                            heartbeat = public["tick_index"] + 100
                    elif frame["type"] == "game_over":
                        assert terminal == peer.results[round_id]
                        assert (
                            terminal["outcome"] == "victory" and terminal["survived_ms"] == 60_000
                        )
                        return terminal
                    assert frame["type"] not in ("error", "action_rejected"), frame["type"]

            results = await asyncio.gather(*(finish(i, peer) for i, peer in enumerate(peers)))
            assert all(result == results[0] for result in results)
            for index, peer in enumerate(peers):
                request = f"{prefix}-restore-{index}"
                await send(peer.socket, "request_state", request)
                restored = (await peer.receive("role_state", request))["payload"]["public"]
                assert restored["result"] == results[0]
                assert len(peer.results) == cycle + 1
            previous = round_id
            print(
                f"{count} controllers: cycle {cycle + 1} victory; matching result, one game_over",
                flush=True,
            )
        await peers[0].command("return_to_lobby", "return")
        for peer in peers:
            while True:
                lobby = (await peer.receive("lobby_state"))["payload"]
                if lobby["stage"] == "lobby":
                    assert lobby["room_code"] == admission["room_code"]
                    assert len(lobby["players"]) == count
                    assert not any(player["ready"] for player in lobby["players"])
                    break
        for index, peer in enumerate(peers):
            await peer.command("leave_room", f"leave-{index}")
        print(
            f"{count} controllers: two rematches, countdown recovery, "
            "fresh sequences, lobby reset passed",
            flush=True,
        )


async def main(url: str) -> None:
    await asyncio.gather(check(url, 2), check(url, 3))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="ws://127.0.0.1:8765/ws")
    asyncio.run(main(parser.parse_args().url))
