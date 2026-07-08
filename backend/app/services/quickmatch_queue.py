"""
Quick Match Queue — auto-pairs two free players using the existing
MatchmakingEngine's compatibility scoring, as an alternative to sharing a
join code.

Purely additive: this module has zero knowledge of Match/MatchInfo and
never creates or seats a match itself — it only decides WHO to pair.
match_registry.create_match()/join_match() (the existing code-based flow)
are completely untouched by this file and keep working exactly as before;
routers/match.py's quickmatch endpoints call into both this queue AND the
existing match_registry functions to actually stand up the match.

In-memory only (per backend process) — same "no required external infra"
philosophy as connection_manager.py and match_registry.py. If you ever run
multiple backend processes behind a load balancer, move this to a shared
store (Redis, same approach as cooldown_store.py) so players hitting
different processes can still find each other.
"""

import time
from dataclasses import dataclass, field

from app.schemas.prajatantra import Ideology, MatchmakingRequest, PlayerMatchProfile
from app.services.matchmaking import matchmaking_engine

# Stale waiting entries (player closed the tab without leaving cleanly) are
# dropped the next time anyone joins or polls the queue.
QUEUE_ENTRY_TTL_SECONDS = 120.0
# How long a "you've been matched" result waits to be picked up by the
# player who was passively waiting when the pairing happened.
READY_RESULT_TTL_SECONDS = 90.0


@dataclass
class QueueEntry:
    player_id: str
    username: str
    ideology: Ideology
    political_mmr: int
    joined_at: float = field(default_factory=time.time)


class QuickMatchQueue:
    def __init__(self) -> None:
        self._waiting: dict[str, QueueEntry] = {}
        # player_id -> (match_id, set_at) for the player who was already
        # waiting when someone else's join() paired them.
        self._ready: dict[str, tuple[str, float]] = {}

    def _to_match_profile(self, entry: QueueEntry) -> PlayerMatchProfile:
        # No live city yet at queue time — trust/gdp_score use a neutral
        # baseline, so MMR + ideology contrast carry the real matching signal.
        return PlayerMatchProfile(
            username=entry.username, political_mmr=entry.political_mmr,
            ideology=entry.ideology, trust=50, gdp_score=50,
        )

    def _prune_stale(self) -> None:
        now = time.time()
        stale = [pid for pid, e in self._waiting.items() if now - e.joined_at > QUEUE_ENTRY_TTL_SECONDS]
        for pid in stale:
            del self._waiting[pid]
        stale_ready = [pid for pid, (_, set_at) in self._ready.items() if now - set_at > READY_RESULT_TTL_SECONDS]
        for pid in stale_ready:
            del self._ready[pid]

    def is_waiting(self, player_id: str) -> bool:
        self._prune_stale()
        return player_id in self._waiting

    def queue_size(self) -> int:
        self._prune_stale()
        return len(self._waiting)

    def find_opponent(
        self, player_id: str, username: str, ideology: Ideology, political_mmr: int,
    ) -> QueueEntry | None:
        """
        Looks for the best already-waiting opponent (excluding self) via the
        existing MatchmakingEngine scoring and, if found, REMOVES them from
        the queue and returns them. The caller is responsible for actually
        creating/seating the Match. Returns None if nobody's waiting, in
        which case the caller should add() themselves instead.
        """
        self._prune_stale()
        candidates = [e for pid, e in self._waiting.items() if pid != player_id]
        if not candidates:
            return None

        me = QueueEntry(player_id=player_id, username=username, ideology=ideology, political_mmr=political_mmr)
        request = MatchmakingRequest(
            queued_player=self._to_match_profile(me),
            candidates=[self._to_match_profile(c) for c in candidates],
        )
        result = matchmaking_engine.pair(request)
        if result.selected is None:
            return None

        opponent = next((c for c in candidates if c.username == result.selected.username), None)
        if opponent is not None:
            del self._waiting[opponent.player_id]
        return opponent

    def add(self, player_id: str, username: str, ideology: Ideology, political_mmr: int) -> None:
        self._waiting[player_id] = QueueEntry(
            player_id=player_id, username=username, ideology=ideology, political_mmr=political_mmr,
        )

    def remove(self, player_id: str) -> None:
        self._waiting.pop(player_id, None)

    def mark_ready(self, player_id: str, match_id: str) -> None:
        self._ready[player_id] = (match_id, time.time())

    def pop_ready(self, player_id: str) -> str | None:
        self._prune_stale()
        entry = self._ready.pop(player_id, None)
        return entry[0] if entry else None


quickmatch_queue = QuickMatchQueue()
