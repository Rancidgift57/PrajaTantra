"""
Match routes for PrajaTantra multiplayer.

Mounted separately from the legacy `prajatantra` / `development` routers so
those single-player endpoints are never touched. A match is a 2-seat room
(Incumbent + Opposition) with its own isolated SovereignEngine +
DevelopmentEngine pair. Every mutating action:

  1. resolves the caller's identity from their auth token,
  2. looks up which seat (role) that player_id holds in the match — the
     client never gets to just claim a role,
  3. runs the existing engine logic (unchanged) scoped to that match,
  4. broadcasts the fresh state to both connected WebSocket clients so the
     other player sees the update in real time without polling.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.schemas.development import BuildFromCatalogRequest, LaunchSchemeRequest
from app.schemas.match import (
    CreateMatchRequest,
    JoinMatchRequest,
    MatchActionEnvelope,
    MatchInfo,
    MatchStateResponse,
    SeatInfo,
)
from app.schemas.prajatantra import (
    ConstructionRequest,
    EmergencyRequest,
    FederalGrantRequest,
    LeakRequest,
    StrikeRequest,
    TradeDuelRequest,
)
from app.services.auth_engine import auth_engine
from app.services.connection_manager import connection_manager
from app.services.match_registry import Match, match_registry

router = APIRouter(prefix="/api/match", tags=["match"])


# ── Helpers ──────────────────────────────────────────────────────────────

async def _resolve_player(token: str) -> tuple[str, str]:
    try:
        profile = await auth_engine.me(token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return profile.id, profile.username


def _match_info(match: Match, viewer_player_id: str | None = None) -> MatchInfo:
    return MatchInfo(
        match_id=match.id,
        join_code=match.join_code,
        status=match.status,
        incumbent=(
            SeatInfo(player_id=match.incumbent.player_id, username=match.incumbent.username, role="Incumbent")
            if match.incumbent
            else None
        ),
        opposition=(
            SeatInfo(player_id=match.opposition.player_id, username=match.opposition.username, role="Opposition")
            if match.opposition
            else None
        ),
        your_role=match.seat_role_for(viewer_player_id) if viewer_player_id else None,
    )


async def _broadcast_state(match: Match) -> None:
    await connection_manager.broadcast(
        match.id,
        {"type": "state", "match": _match_info(match).model_dump(), "state": match.sovereign.state().model_dump()},
    )


# ── Lobby: create / join ─────────────────────────────────────────────────

@router.post("/create", response_model=MatchInfo)
async def create_match(payload: CreateMatchRequest) -> MatchInfo:
    player_id, username = await _resolve_player(payload.token)
    match = match_registry.create_match(player_id, username)
    return _match_info(match, player_id)


@router.post("/join", response_model=MatchInfo)
async def join_match(payload: JoinMatchRequest) -> MatchInfo:
    player_id, username = await _resolve_player(payload.token)
    try:
        match = match_registry.join_match(payload.join_code, player_id, username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast_state(match)  # let the host know someone joined
    return _match_info(match, player_id)


@router.get("/{match_id}", response_model=MatchStateResponse)
async def get_match_state(match_id: str, token: str = Query(...)) -> MatchStateResponse:
    player_id, _ = await _resolve_player(token)
    try:
        match, _role = match_registry.require_seat(match_id, player_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return MatchStateResponse(match=_match_info(match, player_id), state=match.sovereign.state())


# ── Seat-scoped gameplay actions ─────────────────────────────────────────
# Each of these mirrors an existing single-player endpoint, but (a) resolves
# role from the authenticated seat rather than trusting the request body,
# and (b) broadcasts the resulting state to both players over WebSocket.

async def _seated(match_id: str, token: str) -> tuple[Match, str, str]:
    player_id, username = await _resolve_player(token)
    try:
        match, role = match_registry.require_seat(match_id, player_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return match, role, username


@router.post("/{match_id}/construction/build")
async def match_build(match_id: str, envelope: MatchActionEnvelope):
    match, role, username = await _seated(match_id, envelope.token)
    request = ConstructionRequest(**{**envelope.payload, "role": role, "player_username": username})
    try:
        response = await match.sovereign.construct(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast_state(match)
    return response


@router.post("/{match_id}/opposition/strike")
async def match_strike(match_id: str, envelope: MatchActionEnvelope):
    match, role, _username = await _seated(match_id, envelope.token)
    request = StrikeRequest(**{**envelope.payload, "role": role})
    try:
        response = match.sovereign.strike(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast_state(match)
    return response


@router.post("/{match_id}/opposition/leak")
async def match_leak(match_id: str, envelope: MatchActionEnvelope):
    match, role, _username = await _seated(match_id, envelope.token)
    request = LeakRequest(**{**envelope.payload, "role": role})
    try:
        response = match.sovereign.leak(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast_state(match)
    return response


@router.post("/{match_id}/federal/grant")
async def match_federal_grant(match_id: str, envelope: MatchActionEnvelope):
    match, _role, username = await _seated(match_id, envelope.token)
    request = FederalGrantRequest(**{**envelope.payload, "mayor_username": username})
    response = match.sovereign.federal_grant(request)
    await _broadcast_state(match)
    return response


@router.post("/{match_id}/global/trade-duel")
async def match_trade_duel(match_id: str, envelope: MatchActionEnvelope):
    match, _role, _username = await _seated(match_id, envelope.token)
    request = TradeDuelRequest(**envelope.payload)
    response = match.sovereign.trade_duel(request)
    await _broadcast_state(match)
    return response


@router.post("/{match_id}/development/buildings/build")
async def match_build_from_catalog(match_id: str, envelope: MatchActionEnvelope):
    match, role, username = await _seated(match_id, envelope.token)
    request = BuildFromCatalogRequest(**{**envelope.payload, "role": role, "player_username": username})
    try:
        response = await match.development.build_from_catalog(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast_state(match)
    return response


@router.post("/{match_id}/development/schemes/launch")
async def match_launch_scheme(match_id: str, envelope: MatchActionEnvelope):
    match, role, _username = await _seated(match_id, envelope.token)
    request = LaunchSchemeRequest(**{**envelope.payload, "role": role})
    try:
        response = match.development.launch_scheme(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast_state(match)
    return response


@router.post("/{match_id}/emergency/declare")
async def match_declare_emergency(match_id: str, envelope: MatchActionEnvelope):
    match, role, _username = await _seated(match_id, envelope.token)
    request = EmergencyRequest(**{**envelope.payload, "role": role})
    try:
        response = match.sovereign.declare_emergency(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast_state(match)
    return response


# ── Live sync over WebSocket ─────────────────────────────────────────────

@router.websocket("/ws/{match_id}")
async def match_socket(websocket: WebSocket, match_id: str, token: str = Query(...)) -> None:
    try:
        profile = await auth_engine.me(token)
    except PermissionError:
        await websocket.close(code=4401)
        return

    try:
        match, role = match_registry.require_seat(match_id, profile.id)
    except (ValueError, PermissionError):
        await websocket.close(code=4404)
        return

    await connection_manager.connect(match_id, profile.id, websocket)
    # Send an initial snapshot immediately on connect so the client doesn't
    # have to wait for the other player to act before it has real data.
    await connection_manager.send_to(
        match_id,
        profile.id,
        {"type": "state", "match": _match_info(match, profile.id).model_dump(), "state": match.sovereign.state().model_dump()},
    )
    # Let the other seat know this player is now live.
    await connection_manager.broadcast(
        match_id,
        {"type": "presence", "player_id": profile.id, "role": role, "connected": True},
    )

    try:
        while True:
            # We don't expect the client to send gameplay actions over the
            # socket (those go through the REST endpoints above so they get
            # validation + HTTP error codes) — this just keeps the
            # connection alive and detects disconnects. A client can send
            # "ping" and will get "pong" back for simple heartbeats.
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        connection_manager.disconnect(match_id, profile.id)
        await connection_manager.broadcast(
            match_id,
            {"type": "presence", "player_id": profile.id, "role": role, "connected": False},
        )
