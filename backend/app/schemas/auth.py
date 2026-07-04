"""
Authentication, player-profile, and leaderboard schemas for PrajaTantra.

Kept in a separate module from `prajatantra.py` so the existing simulation
schemas are never touched — this file is purely additive.
"""
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Ideology = Literal["Industrialist", "Green", "Socialist", "Nationalist", "Technocrat"]


# ── Registration / Login ────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=24, pattern=r"^[A-Za-z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    city_name: str = Field(min_length=2, max_length=40)
    ideology: Ideology = "Technocrat"


class LoginRequest(BaseModel):
    username_or_email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6, max_length=128)


class PlayerProfile(BaseModel):
    id: str
    username: str
    email: EmailStr
    city_id: str
    city_name: str
    ideology: Ideology
    political_mmr: int = 1000
    created_at: str


class AuthResponse(BaseModel):
    token: str
    player: PlayerProfile
    message: str


class MeResponse(BaseModel):
    player: PlayerProfile


# ── City naming ──────────────────────────────────────────────────────────

class RenameCityRequest(BaseModel):
    token: str
    new_name: str = Field(min_length=2, max_length=40)


class RenameCityResponse(BaseModel):
    city_id: str
    city_name: str
    message: str


# ── Leaderboard (OpenFront-style "Player / Owned / Gold / Max troops") ────

class LeaderboardEntry(BaseModel):
    rank: int
    player_id: str
    player_username: str
    city_name: str
    owned_percent: float          # share of total simulated world GDP
    gold: int                     # treasury
    max_troops: int               # derived strength stat (influence + blocks)
    is_you: bool = False


class LeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry]
    total_players: int
    your_rank: int | None = None