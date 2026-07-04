"""
ConnectionManager
------------------
Tracks live WebSocket connections per match_id and broadcasts JSON payloads
(usually a fresh SovereignStateResponse) to every socket in that match the
instant either player takes an action. This is what makes the game feel
"multiplayer" instead of "two people polling the same REST endpoint."

Kept dependency-free (no Redis) so it runs with zero extra infra. If you
later run more than one backend process/replica, swap the in-memory
`self._rooms` dict for a Redis pub/sub channel keyed by match_id — every
other method signature stays the same.
"""
from __future__ import annotations

import json
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # match_id -> { player_id: WebSocket }
        self._rooms: dict[str, dict[str, WebSocket]] = defaultdict(dict)

    async def connect(self, match_id: str, player_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._rooms[match_id][player_id] = websocket

    def disconnect(self, match_id: str, player_id: str) -> None:
        room = self._rooms.get(match_id)
        if not room:
            return
        room.pop(player_id, None)
        if not room:
            self._rooms.pop(match_id, None)

    def connected_player_ids(self, match_id: str) -> list[str]:
        return list(self._rooms.get(match_id, {}).keys())

    async def broadcast(self, match_id: str, message: dict) -> None:
        room = self._rooms.get(match_id)
        if not room:
            return
        payload = json.dumps(message, default=str)
        dead: list[str] = []
        for player_id, socket in room.items():
            try:
                await socket.send_text(payload)
            except Exception:
                dead.append(player_id)
        for player_id in dead:
            room.pop(player_id, None)

    async def send_to(self, match_id: str, player_id: str, message: dict) -> None:
        room = self._rooms.get(match_id)
        if not room or player_id not in room:
            return
        try:
            await room[player_id].send_text(json.dumps(message, default=str))
        except Exception:
            room.pop(player_id, None)


connection_manager = ConnectionManager()
