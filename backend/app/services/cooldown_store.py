"""
Cooldown Store — Tactical Card cooldown manager
================================================
Redis-backed if REDIS_URL is configured, else an in-memory dict fallback —
the same "real backend with a zero-setup fallback" pattern used throughout
this codebase (see db.py for Postgres, corruption_graph.py for Neo4j).

Kept synchronous (a plain `redis` client, not `redis.asyncio`) so it can be
called directly from SovereignEngine's existing synchronous methods without
threading async through the whole engine. A cooldown check/set is a single
cheap round-trip, well within acceptable latency for an occasional card play.

Swap-in path: if you outgrow the sync client, switch to `redis.asyncio` and
make `SovereignEngine.play_card` async — every call site is already awaited
from the router.
"""

import os
import time

try:
    import redis as _redis_lib  # type: ignore
except ModuleNotFoundError:
    _redis_lib = None

_REDIS_URL = os.getenv("REDIS_URL")


class CooldownStore:
    def __init__(self) -> None:
        self._client = None
        self._client_initialized = False
        # Fallback store: "match_id:role:card_id" -> ready_at (epoch seconds)
        self._memory: dict[str, float] = {}

    def _get_client(self):
        if self._client_initialized:
            return self._client
        self._client_initialized = True
        if not _REDIS_URL or _redis_lib is None:
            self._client = None
            return None
        try:
            self._client = _redis_lib.from_url(
                _REDIS_URL, decode_responses=True, socket_connect_timeout=1,
            )
            self._client.ping()
        except Exception:
            self._client = None
        return self._client

    @staticmethod
    def _key(match_id: str, role: str, card_id: str) -> str:
        return f"prajatantra:cooldown:{match_id}:{role}:{card_id}"

    def get_ready_at(self, match_id: str, role: str, card_id: str) -> float:
        key = self._key(match_id, role, card_id)
        client = self._get_client()
        if client is not None:
            try:
                value = client.get(key)
                return float(value) if value else 0.0
            except Exception:
                pass
        return self._memory.get(key, 0.0)

    def set_cooldown(self, match_id: str, role: str, card_id: str, seconds: float) -> float:
        ready_at = time.time() + seconds
        key = self._key(match_id, role, card_id)
        client = self._get_client()
        if client is not None:
            try:
                client.set(key, ready_at, ex=int(seconds) + 10)
                return ready_at
            except Exception:
                pass
        self._memory[key] = ready_at
        return ready_at

    def is_ready(self, match_id: str, role: str, card_id: str) -> bool:
        return time.time() >= self.get_ready_at(match_id, role, card_id)

    def seconds_remaining(self, match_id: str, role: str, card_id: str) -> float:
        return max(0.0, self.get_ready_at(match_id, role, card_id) - time.time())


cooldown_store = CooldownStore()
