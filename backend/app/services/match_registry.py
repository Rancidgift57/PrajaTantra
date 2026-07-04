"""
MatchRegistry
-------------
Owns every live multiplayer match. Each Match gets its own SovereignEngine +
DevelopmentEngine pair (see development_engine.py's injectable constructor),
so two concurrent matches never share city state — unlike the legacy
singleton `sovereign_engine` used by the original single-player routes,
which is left completely untouched for backward compatibility.

Swap-in path to Postgres/Redis: replace `self._matches` dict with rows in a
`matches` table (see database/postgres/ for the existing schema style) and
serialize SovereignMemory as JSONB. Every method signature below can stay
the same — only the storage backing changes.
"""
from __future__ import annotations

import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.schemas.prajatantra import PlayerRole
from app.services.development_engine import DevelopmentEngine
from app.services.sovereign_engine import SovereignEngine


def _new_id() -> str:
    return secrets.token_hex(8)


def _new_join_code() -> str:
    # Short, human-typeable code e.g. "K4N7QX"
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


@dataclass
class Seat:
    player_id: str
    username: str


@dataclass
class Match:
    id: str = field(default_factory=_new_id)
    join_code: str = field(default_factory=_new_join_code)
    status: str = "waiting"  # waiting -> active -> finished
    sovereign: SovereignEngine = field(default_factory=SovereignEngine)
    development: DevelopmentEngine | None = None
    incumbent: Seat | None = None
    opposition: Seat | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.development is None:
            self.development = DevelopmentEngine(self.sovereign)

    def seat_role_for(self, player_id: str) -> PlayerRole | None:
        if self.incumbent and self.incumbent.player_id == player_id:
            return "Incumbent"
        if self.opposition and self.opposition.player_id == player_id:
            return "Opposition"
        return None

    def has_player(self, player_id: str) -> bool:
        return self.seat_role_for(player_id) is not None


class MatchRegistry:
    def __init__(self) -> None:
        self._matches: dict[str, Match] = {}
        self._by_join_code: dict[str, str] = {}  # join_code -> match_id

    def create_match(self, host_player_id: str, host_username: str) -> Match:
        match = Match()
        match.incumbent = Seat(player_id=host_player_id, username=host_username)
        self._matches[match.id] = match
        self._by_join_code[match.join_code] = match.id
        return match

    def join_match(self, join_code: str, player_id: str, username: str) -> Match:
        match_id = self._by_join_code.get(join_code.strip().upper())
        if not match_id or match_id not in self._matches:
            raise ValueError("No match found with that join code.")
        match = self._matches[match_id]

        if match.incumbent and match.incumbent.player_id == player_id:
            return match  # host re-joining, no-op
        if match.opposition and match.opposition.player_id == player_id:
            return match  # opposition re-joining, no-op

        if match.opposition is not None:
            raise ValueError("This match already has two players.")

        match.opposition = Seat(player_id=player_id, username=username)
        match.status = "active"
        return match

    def get_match(self, match_id: str) -> Match:
        match = self._matches.get(match_id)
        if not match:
            raise ValueError("Match not found.")
        return match

    def require_seat(self, match_id: str, player_id: str) -> tuple[Match, PlayerRole]:
        match = self.get_match(match_id)
        role = match.seat_role_for(player_id)
        if role is None:
            raise PermissionError("You are not seated in this match.")
        return match, role


match_registry = MatchRegistry()
