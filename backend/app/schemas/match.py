"""
Match schemas for PrajaTantra multiplayer.

A "match" is a 2-seat game room: one player is the Incumbent, one is the
Opposition. Each match owns its own SovereignEngine + DevelopmentEngine
instance, so two matches never see each other's city state.
"""
from __future__ import annotations

from pydantic import BaseModel

from app.schemas.prajatantra import PlayerRole, SovereignStateResponse


class CreateMatchRequest(BaseModel):
    token: str  # auth token of the player creating the match (becomes Incumbent)


class JoinMatchRequest(BaseModel):
    token: str  # auth token of the joining player (becomes Opposition)
    join_code: str


class SeatInfo(BaseModel):
    player_id: str
    username: str
    role: PlayerRole


class MatchInfo(BaseModel):
    match_id: str
    join_code: str
    status: str  # "waiting" | "active" | "finished"
    incumbent: SeatInfo | None = None
    opposition: SeatInfo | None = None
    your_role: PlayerRole | None = None


class MatchStateResponse(BaseModel):
    match: MatchInfo
    state: SovereignStateResponse


class MatchActionEnvelope(BaseModel):
    """Generic wrapper so any existing request payload (ConstructionRequest,
    StrikeRequest, BuildFromCatalogRequest, ...) can be sent scoped to a
    match without duplicating every schema. `token` identifies the caller;
    the server derives `role` from the seat assignment rather than trusting
    whatever the client claims."""

    token: str
    payload: dict
