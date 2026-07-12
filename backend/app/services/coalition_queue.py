"""
Coalition Quick Match Queue — auto-groups FIVE free players instead of two.

Mirrors quickmatch_queue.py's shape (in-memory, TTL-pruned, "ready" handoff
for passively-waiting players) but groups in batches of 5 rather than
pairing 1:1, since MatchmakingEngine's compatibility scoring is inherently
pairwise and doesn't generalize cleanly to a 5-way group. Zero knowledge of
CoalitionMatch — it only decides WHO plays together; routers/coalition.py
calls into both this queue and coalition_registry to actually seat them.
"""
import time
from dataclasses import dataclass, field

GROUP_SIZE = 5
QUEUE_ENTRY_TTL_SECONDS = 180.0
READY_RESULT_TTL_SECONDS = 90.0


@dataclass
class QueueEntry:
    player_id: str
    username: str
    joined_at: float = field(default_factory=time.time)


class CoalitionQuickMatchQueue:
    def __init__(self) -> None:
        self._waiting: dict[str, QueueEntry] = {}
        self._ready: dict[str, tuple[str, float]] = {}  # player_id -> (match_id, set_at)

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

    def add(self, player_id: str, username: str) -> None:
        self._waiting[player_id] = QueueEntry(player_id=player_id, username=username)

    def remove(self, player_id: str) -> None:
        self._waiting.pop(player_id, None)

    def try_form_group(self, exclude_player_id: str | None = None) -> list[QueueEntry] | None:
        """FIFO grouping: once >=5 distinct players (including the caller,
        if they're in the queue) are waiting, pop the oldest 5 and return
        them. Caller is responsible for seating the CoalitionMatch."""
        self._prune_stale()
        if len(self._waiting) < GROUP_SIZE:
            return None
        ordered = sorted(self._waiting.values(), key=lambda e: e.joined_at)[:GROUP_SIZE]
        for entry in ordered:
            del self._waiting[entry.player_id]
        return ordered

    def mark_ready(self, player_id: str, match_id: str) -> None:
        self._ready[player_id] = (match_id, time.time())

    def pop_ready(self, player_id: str) -> str | None:
        self._prune_stale()
        entry = self._ready.pop(player_id, None)
        return entry[0] if entry else None


coalition_quickmatch_queue = CoalitionQuickMatchQueue()
