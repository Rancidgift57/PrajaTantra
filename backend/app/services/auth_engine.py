"""
AuthEngine
----------
Authentication + player-profile + leaderboard service for PrajaTantra.

Dual-mode:
  - DATABASE_URL set (Supabase/Postgres)  -> every call hits real tables,
    rows actually persist across backend restarts/redeploys.
  - DATABASE_URL unset                    -> falls back to the original
    in-memory dict store, so `uvicorn app.main:app --reload` with zero DB
    configured still works exactly like before (good for quick local demos).

Router code and the frontend never need to know which mode is active —
every public method keeps the same signature either way.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app import db
from app.schemas.auth import (
    AuthResponse,
    LeaderboardEntry,
    LeaderboardResponse,
    LoginRequest,
    PlayerProfile,
    RegisterRequest,
    RenameCityRequest,
    RenameCityResponse,
)

# ── Password hashing (PBKDF2-HMAC-SHA256, stdlib only — no extra dependency) ─
_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return hmac.compare_digest(expected.hex(), digest_hex)


# ── Lightweight signed token (HMAC) — swap for real JWT lib in production ──
_TOKEN_SECRET = os.getenv("PRAJATANTRA_TOKEN_SECRET", "prajatantra-dev-secret-change-me")


def _issue_token(player_id: str) -> str:
    payload = f"{player_id}.{int(time.time())}"
    signature = hmac.new(_TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def _verify_token(token: str) -> str | None:
    try:
        player_id, ts, signature = token.split(".")
    except ValueError:
        return None
    payload = f"{player_id}.{ts}"
    expected = hmac.new(_TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    return player_id


def _seed_uuid(short_id: str) -> str:
    """Postgres `players.id` is a UUID. Real player ids are already random
    UUIDs (Postgres generates them via gen_random_uuid()); this helper only
    exists so hardcoded seed-rival ids like 'seed-brazil' map deterministically
    onto a valid UUID — same input always produces the same UUID, so
    re-running seed_rivals() on every startup stays idempotent."""
    return str(uuid.uuid5(uuid.NAMESPACE_OID, short_id))


# ── Internal in-memory record (fallback mode only) ─────────────────────────

@dataclass
class _StoredPlayer:
    id: str
    username: str
    email: str
    password_hash: str
    city_id: str
    city_name: str
    ideology: str
    political_mmr: int = 1000
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    owned_percent: float = 0.6
    gold: int = 64_000
    max_troops: int = 19_800


_SEED_RIVALS: list[_StoredPlayer] = [
    _StoredPlayer(
        id="seed-brazil", username="Brazil", email="bot@prajatantra.local",
        password_hash="", city_id="BOT-BRA", city_name="Brasília Sangh",
        ideology="Industrialist", owned_percent=0.7, gold=64_000, max_troops=21_000,
    ),
    _StoredPlayer(
        id="seed-russia", username="Russia", email="bot@prajatantra.local",
        password_hash="", city_id="BOT-RUS", city_name="Moskva Rajya",
        ideology="Nationalist", owned_percent=0.7, gold=64_000, max_troops=20_200,
    ),
    _StoredPlayer(
        id="seed-siberia", username="Siberia", email="bot@prajatantra.local",
        password_hash="", city_id="BOT-SIB", city_name="Siberia Pradesh",
        ideology="Technocrat", owned_percent=0.6, gold=64_000, max_troops=19_800,
    ),
    _StoredPlayer(
        id="seed-australia", username="Australia", email="bot@prajatantra.local",
        password_hash="", city_id="BOT-AUS", city_name="Canberra Lok",
        ideology="Green", owned_percent=0.6, gold=91_000, max_troops=19_600,
    ),
]

# SQL column order used everywhere a full player row is selected.
_PLAYER_COLUMNS = (
    "id, username, email, password_hash, city_id, city_name, ideology, "
    "political_mmr, owned_percent, gold, max_troops, created_at"
)


def _row_to_profile(row) -> PlayerProfile:
    return PlayerProfile(
        id=str(row["id"]),
        username=row["username"],
        email=row["email"],
        city_id=row["city_id"],
        city_name=row["city_name"],
        ideology=row["ideology"],
        political_mmr=row["political_mmr"],
        created_at=row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
    )


class AuthEngine:
    def __init__(self) -> None:
        # In-memory fallback stores — only ever touched when db.is_configured() is False.
        self._players_by_id: dict[str, _StoredPlayer] = {p.id: p for p in _SEED_RIVALS}
        self._players_by_username: dict[str, str] = {p.username.lower(): p.id for p in _SEED_RIVALS}
        self._players_by_email: dict[str, str] = {}

    # ── Startup: seed AI rival rows into Postgres (idempotent) ────────────

    async def seed_rivals(self) -> None:
        if not db.is_configured():
            return
        async with db.pool().acquire() as conn:
            for rival in _SEED_RIVALS:
                await conn.execute(
                    """
                    INSERT INTO players (id, username, email, password_hash, city_id,
                                          city_name, ideology, political_mmr, owned_percent,
                                          gold, max_troops)
                    VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    _seed_uuid(rival.id), rival.username, rival.email, rival.password_hash,
                    rival.city_id, rival.city_name, rival.ideology, rival.political_mmr,
                    rival.owned_percent, rival.gold, rival.max_troops,
                )

    # ── Registration / login ───────────────────────────────────────────────

    async def register(self, payload: RegisterRequest) -> AuthResponse:
        if db.is_configured():
            return await self._register_db(payload)
        return self._register_memory(payload)

    async def login(self, payload: LoginRequest) -> AuthResponse:
        if db.is_configured():
            return await self._login_db(payload)
        return self._login_memory(payload)

    async def me(self, token: str) -> PlayerProfile:
        if db.is_configured():
            return await self._me_db(token)
        return self._me_memory(token)

    # ── City naming ─────────────────────────────────────────────────────────

    async def rename_city(self, payload: RenameCityRequest) -> RenameCityResponse:
        if db.is_configured():
            return await self._rename_city_db(payload)
        return self._rename_city_memory(payload)

    # ── Leaderboard ─────────────────────────────────────────────────────────

    async def leaderboard(self, viewer_token: str | None = None, limit: int = 5) -> LeaderboardResponse:
        if db.is_configured():
            return await self._leaderboard_db(viewer_token, limit)
        return self._leaderboard_memory(viewer_token, limit)

    async def sync_player_stats(self, token: str, gold: int, max_troops: int, owned_percent: float) -> None:
        """Called after each city action so the leaderboard reflects live
        treasury / influence growth."""
        player_id = _verify_token(token)
        if not player_id:
            return
        if db.is_configured():
            async with db.pool().acquire() as conn:
                await conn.execute(
                    "UPDATE players SET gold = $2, max_troops = $3, owned_percent = $4 WHERE id = $1::uuid",
                    _seed_uuid(player_id), gold, max_troops, owned_percent,
                )
            return
        stored = self._players_by_id.get(player_id)
        if stored:
            stored.gold = gold
            stored.max_troops = max_troops
            stored.owned_percent = owned_percent

    # ── Postgres implementations ────────────────────────────────────────────

    async def _register_db(self, payload: RegisterRequest) -> AuthResponse:
        async with db.pool().acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM players WHERE lower(username) = lower($1) OR lower(email) = lower($2)",
                payload.username, str(payload.email),
            )
            if existing:
                raise ValueError("Username or email is already taken. Choose another.")

            city_id = f"CITY-{secrets.token_hex(3).upper()}"
            row = await conn.fetchrow(
                f"""
                INSERT INTO players (username, email, password_hash, city_id, city_name,
                                      ideology, political_mmr, owned_percent, gold, max_troops)
                VALUES ($1, $2, $3, $4, $5, $6, 1000, 0.6, 180000, 22000)
                RETURNING {_PLAYER_COLUMNS}
                """,
                payload.username, str(payload.email), _hash_password(payload.password),
                city_id, payload.city_name, payload.ideology,
            )
        token = _issue_token(str(row["id"]))
        return AuthResponse(
            token=token,
            player=_row_to_profile(row),
            message=f"Swagat hai, {payload.username}! {payload.city_name} ki sthapna ho gayi.",
        )

    async def _login_db(self, payload: LoginRequest) -> AuthResponse:
        async with db.pool().acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_PLAYER_COLUMNS} FROM players WHERE lower(username) = lower($1) OR lower(email) = lower($1)",
                payload.username_or_email,
            )
        if not row:
            raise ValueError("No account found with that username or email.")
        if not row["password_hash"] or not _verify_password(payload.password, row["password_hash"]):
            raise ValueError("Incorrect password.")

        token = _issue_token(str(row["id"]))
        return AuthResponse(
            token=token,
            player=_row_to_profile(row),
            message=f"Wapsi par swagat hai, {row['username']}.",
        )

    async def _me_db(self, token: str) -> PlayerProfile:
        player_id = _verify_token(token)
        if not player_id:
            raise PermissionError("Session expired or invalid. Please log in again.")
        async with db.pool().acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_PLAYER_COLUMNS} FROM players WHERE id = $1::uuid", _seed_uuid(player_id),
            )
        if not row:
            raise PermissionError("Session expired or invalid. Please log in again.")
        return _row_to_profile(row)

    async def _rename_city_db(self, payload: RenameCityRequest) -> RenameCityResponse:
        player_id = _verify_token(payload.token)
        if not player_id:
            raise PermissionError("Session expired or invalid. Please log in again.")
        async with db.pool().acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE players SET city_name = $2 WHERE id = $1::uuid RETURNING city_id, city_name",
                _seed_uuid(player_id), payload.new_name,
            )
        if not row:
            raise PermissionError("Session expired or invalid. Please log in again.")
        return RenameCityResponse(
            city_id=row["city_id"],
            city_name=row["city_name"],
            message=f"Shehar ka naam badal kar '{payload.new_name}' rakha gaya.",
        )

    async def _leaderboard_db(self, viewer_token: str | None, limit: int) -> LeaderboardResponse:
        viewer_id = _verify_token(viewer_token) if viewer_token else None
        async with db.pool().acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_PLAYER_COLUMNS} FROM players ORDER BY owned_percent DESC"
            )

        entries: list[LeaderboardEntry] = []
        your_rank: int | None = None
        for idx, row in enumerate(rows, start=1):
            is_you = viewer_id is not None and str(row["id"]) == viewer_id
            if is_you:
                your_rank = idx
            if idx <= limit or is_you:
                entries.append(LeaderboardEntry(
                    rank=idx, player_id=str(row["id"]), player_username=row["username"],
                    city_name=row["city_name"], owned_percent=float(row["owned_percent"]),
                    gold=row["gold"], max_troops=row["max_troops"], is_you=is_you,
                ))

        top = [e for e in entries if e.rank <= limit]
        if your_rank and your_rank > limit:
            viewer_entry = next((e for e in entries if e.is_you), None)
            if viewer_entry:
                top.append(viewer_entry)

        return LeaderboardResponse(entries=top, total_players=len(rows), your_rank=your_rank)

    # ── In-memory fallback implementations (unchanged behavior) ────────────

    def _register_memory(self, payload: RegisterRequest) -> AuthResponse:
        uname_key = payload.username.lower()
        if uname_key in self._players_by_username:
            raise ValueError("Username is already taken. Choose another.")
        if payload.email.lower() in self._players_by_email:
            raise ValueError("An account with this email already exists.")

        player_id = secrets.token_hex(8)
        city_id = f"CITY-{secrets.token_hex(3).upper()}"
        stored = _StoredPlayer(
            id=player_id, username=payload.username, email=str(payload.email),
            password_hash=_hash_password(payload.password), city_id=city_id,
            city_name=payload.city_name, ideology=payload.ideology,
            political_mmr=1000, owned_percent=0.6, gold=180_000, max_troops=22_000,
        )
        self._players_by_id[player_id] = stored
        self._players_by_username[uname_key] = player_id
        self._players_by_email[payload.email.lower()] = player_id

        token = _issue_token(player_id)
        return AuthResponse(
            token=token, player=self._to_profile(stored),
            message=f"Swagat hai, {payload.username}! {payload.city_name} ki sthapna ho gayi.",
        )

    def _login_memory(self, payload: LoginRequest) -> AuthResponse:
        key = payload.username_or_email.lower()
        player_id = self._players_by_username.get(key) or self._players_by_email.get(key)
        if not player_id:
            raise ValueError("No account found with that username or email.")
        stored = self._players_by_id[player_id]
        if not stored.password_hash or not _verify_password(payload.password, stored.password_hash):
            raise ValueError("Incorrect password.")

        token = _issue_token(player_id)
        return AuthResponse(
            token=token, player=self._to_profile(stored),
            message=f"Wapsi par swagat hai, {stored.username}.",
        )

    def _me_memory(self, token: str) -> PlayerProfile:
        player_id = _verify_token(token)
        if not player_id or player_id not in self._players_by_id:
            raise PermissionError("Session expired or invalid. Please log in again.")
        return self._to_profile(self._players_by_id[player_id])

    def _rename_city_memory(self, payload: RenameCityRequest) -> RenameCityResponse:
        player_id = _verify_token(payload.token)
        if not player_id or player_id not in self._players_by_id:
            raise PermissionError("Session expired or invalid. Please log in again.")
        stored = self._players_by_id[player_id]
        stored.city_name = payload.new_name
        return RenameCityResponse(
            city_id=stored.city_id, city_name=stored.city_name,
            message=f"Shehar ka naam badal kar '{payload.new_name}' rakha gaya.",
        )

    def _leaderboard_memory(self, viewer_token: str | None, limit: int) -> LeaderboardResponse:
        viewer_id = _verify_token(viewer_token) if viewer_token else None
        ranked = sorted(self._players_by_id.values(), key=lambda p: p.owned_percent, reverse=True)
        entries: list[LeaderboardEntry] = []
        your_rank: int | None = None

        for idx, player in enumerate(ranked, start=1):
            is_you = player.id == viewer_id
            if is_you:
                your_rank = idx
            if idx <= limit or is_you:
                entries.append(LeaderboardEntry(
                    rank=idx, player_id=player.id, player_username=player.username,
                    city_name=player.city_name, owned_percent=player.owned_percent,
                    gold=player.gold, max_troops=player.max_troops, is_you=is_you,
                ))

        top = [e for e in entries if e.rank <= limit]
        if your_rank and your_rank > limit:
            viewer_entry = next((e for e in entries if e.is_you), None)
            if viewer_entry:
                top.append(viewer_entry)

        return LeaderboardResponse(entries=top, total_players=len(ranked), your_rank=your_rank)

    def _to_profile(self, stored: _StoredPlayer) -> PlayerProfile:
        return PlayerProfile(
            id=stored.id, username=stored.username, email=stored.email,
            city_id=stored.city_id, city_name=stored.city_name,
            ideology=stored.ideology, political_mmr=stored.political_mmr,
            created_at=stored.created_at,
        )


auth_engine = AuthEngine()
