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

import asyncio

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.schemas.development import BuildFromCatalogRequest, LaunchSchemeRequest
from app.schemas.match import (
    CreateMatchRequest,
    JoinMatchRequest,
    MatchActionEnvelope,
    MatchInfo,
    MatchStateResponse,
    QuickMatchJoinRequest,
    QuickMatchStatusResponse,
    SeatInfo,
)
from app.schemas.prajatantra import (
    ConstructionRequest,
    CrisisActionRequest,
    EmergencyRequest,
    FederalGrantRequest,
    LeakRequest,
    PlayCardRequest,
    RunElectionRequest,
    StrikeRequest,
    TacticalCardCatalogResponse,
    TradeDuelRequest,
)
from app.services.auth_engine import auth_engine
from app.services.connection_manager import connection_manager
from app.services.match_registry import Match, match_registry
from app.services.quickmatch_queue import quickmatch_queue
from app.services.tactical_cards import CARD_CATALOG

router = APIRouter(prefix="/api/match", tags=["match"])

# How often the background tick loop recalculates + broadcasts state and
# rolls the dice on a new Flash Crisis, per match. Self-terminates once
# both seats disconnect (checked each iteration).
MATCH_TICK_SECONDS = 6.0


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


# ── Quick Match — auto-pairs two free players instead of sharing a join
# code. Purely additive: /create and /join above are completely untouched
# and remain the code-based flow. Poll /quickmatch/status after a "waiting"
# response until it flips to "matched". ───────────────────────────────────

@router.post("/quickmatch/join", response_model=QuickMatchStatusResponse)
async def quickmatch_join(payload: QuickMatchJoinRequest) -> QuickMatchStatusResponse:
    try:
        profile = await auth_engine.me(payload.token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    # We might already be the "waiting" side of a pairing that happened
    # since our last call — pick that up instead of re-queueing.
    ready_match_id = quickmatch_queue.pop_ready(profile.id)
    if ready_match_id:
        match = match_registry.get_match(ready_match_id)
        return QuickMatchStatusResponse(status="matched", match=_match_info(match, profile.id))

    opponent = quickmatch_queue.find_opponent(profile.id, profile.username, profile.ideology, profile.political_mmr)
    if opponent is None:
        quickmatch_queue.add(profile.id, profile.username, profile.ideology, profile.political_mmr)
        return QuickMatchStatusResponse(status="waiting", queue_size=quickmatch_queue.queue_size())

    # Found a waiting opponent — stand up a real match the exact same way
    # the code-based flow does (create_match + join_match, unmodified),
    # we just skip the "share a code" step. Whoever waited longer becomes
    # the host/Incumbent; the player who just triggered the pairing becomes
    # Opposition.
    match = match_registry.create_match(opponent.player_id, opponent.username)
    match = match_registry.join_match(match.join_code, profile.id, profile.username)
    quickmatch_queue.mark_ready(opponent.player_id, match.id)
    await _broadcast_state(match)
    return QuickMatchStatusResponse(status="matched", match=_match_info(match, profile.id))


@router.get("/quickmatch/status", response_model=QuickMatchStatusResponse)
async def quickmatch_status(token: str = Query(...)) -> QuickMatchStatusResponse:
    try:
        profile = await auth_engine.me(token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    ready_match_id = quickmatch_queue.pop_ready(profile.id)
    if ready_match_id:
        match = match_registry.get_match(ready_match_id)
        return QuickMatchStatusResponse(status="matched", match=_match_info(match, profile.id))
    if quickmatch_queue.is_waiting(profile.id):
        return QuickMatchStatusResponse(status="waiting", queue_size=quickmatch_queue.queue_size())
    return QuickMatchStatusResponse(status="idle")


@router.post("/quickmatch/leave")
async def quickmatch_leave(payload: QuickMatchJoinRequest) -> dict:
    try:
        profile = await auth_engine.me(payload.token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    quickmatch_queue.remove(profile.id)
    return {"left": True}


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


@router.post("/{match_id}/elections/simulate-counting")
async def match_run_election(match_id: str, envelope: MatchActionEnvelope):
    """
    Calls an election within this match, subject to SovereignEngine's
    cooldown (every 3 days by default, or a snap election once >= 2.5 days
    have passed via force_early). Rejected with 400 if called too soon.
    """
    match, role, _username = await _seated(match_id, envelope.token)
    request = RunElectionRequest(**{**envelope.payload, "role": role})
    try:
        response = match.sovereign.run_election(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast_state(match)
    return response


# ── Flash Crises — Incumbent patches, Opposition amplifies ───────────────

@router.post("/{match_id}/crisis/patch")
async def match_patch_crisis(match_id: str, envelope: MatchActionEnvelope):
    match, role, _username = await _seated(match_id, envelope.token)
    request = CrisisActionRequest(**{**envelope.payload, "role": role})
    try:
        response = match.sovereign.patch_crisis(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast_state(match)
    return response


@router.post("/{match_id}/crisis/amplify")
async def match_amplify_crisis(match_id: str, envelope: MatchActionEnvelope):
    match, role, _username = await _seated(match_id, envelope.token)
    request = CrisisActionRequest(**{**envelope.payload, "role": role})
    try:
        response = match.sovereign.amplify_crisis(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast_state(match)
    return response


# ── Tactical Cards — the "Midnight Card" deck ─────────────────────────────

@router.get("/cards/catalog", response_model=TacticalCardCatalogResponse)
async def cards_catalog() -> TacticalCardCatalogResponse:
    return TacticalCardCatalogResponse(cards=CARD_CATALOG)


@router.post("/{match_id}/cards/play")
async def match_play_card(match_id: str, envelope: MatchActionEnvelope):
    match, role, _username = await _seated(match_id, envelope.token)
    request = PlayCardRequest(**{**envelope.payload, "role": role})
    try:
        response = match.sovereign.play_card(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast_state(match)
    return response


# ── Live sync over WebSocket ─────────────────────────────────────────────

async def _match_tick_loop(match: Match) -> None:
    """
    Background loop started on first WebSocket connect for a match: every
    MATCH_TICK_SECONDS it rolls the dice on a new Flash Crisis, resolves
    any crisis whose 60s window expired unanswered, and re-broadcasts state
    so the Live Seat Projection visibly ticks even with no player action.
    Self-terminates once nobody is connected to this match anymore.
    """
    try:
        while True:
            await asyncio.sleep(MATCH_TICK_SECONDS)
            if not connection_manager.connected_player_ids(match.id):
                return
            match.sovereign.maybe_trigger_crisis()
            match.sovereign.resolve_expired_crisis()
            await _broadcast_state(match)
    except asyncio.CancelledError:
        return


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
    # Kick off the background tick loop the first time anyone connects to
    # this match (guarded so we never start a second one for the same match).
    if match.tick_task is None or match.tick_task.done():  # type: ignore[union-attr]
        match.tick_task = asyncio.create_task(_match_tick_loop(match))
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
