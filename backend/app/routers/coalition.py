"""
Coalition routes — the 5-Player "Coalition Era" mode.

Mounted separately from routers/match.py so the 2-player game is never
touched. Every mutating action resolves the caller's identity from their
auth token, checks their seat in the CoalitionMatch, runs CoalitionEngine
logic, then broadcasts the fresh CoalitionMatchInfo to every connected
WebSocket client in the room (same connection_manager used by match.py).
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.schemas.coalition import (
    BlackmailRequest,
    CastFloorVoteRequest,
    CoalitionQuickMatchJoinRequest,
    CoalitionQuickMatchStatusResponse,
    CoalitionStateResponse,
    CreateCoalitionMatchRequest,
    JoinCoalitionMatchRequest,
    MinistryAllocationRequest,
    ProposeCoalitionRequest,
    RespondCoalitionRequest,
    SiphonRequest,
    TriggerFloorTestRequest,
    WithdrawSupportRequest,
)
from app.services.auth_engine import auth_engine
from app.services.coalition_engine import CoalitionMatch, coalition_registry, engine
from app.services.coalition_queue import coalition_quickmatch_queue
from app.services.connection_manager import connection_manager

router = APIRouter(prefix="/api/coalition", tags=["coalition"])

# Ambient tick: resolves expired floor tests / negotiation windows and keeps
# the election round-reveal clock moving for every connected client, even
# if nobody is actively clicking anything.
COALITION_TICK_SECONDS = 5.0


async def _resolve_player(token: str) -> tuple[str, str]:
    try:
        profile = await auth_engine.me(token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return profile.id, profile.username


async def _broadcast(match: CoalitionMatch) -> None:
    await connection_manager.broadcast(
        match.id, {"type": "coalition_state", "match": engine.to_info(match).model_dump()},
    )


def _state_response(match: CoalitionMatch, viewer_player_id: str | None) -> CoalitionStateResponse:
    return CoalitionStateResponse(match=engine.to_info(match, viewer_player_id))


async def _tick_loop(match_id: str) -> None:
    try:
        while True:
            await asyncio.sleep(COALITION_TICK_SECONDS)
            if not connection_manager.connected_player_ids(match_id):
                return
            try:
                match = coalition_registry.get_match(match_id)
            except ValueError:
                return
            before = (match.status, len(match.floor_test.votes) if match.floor_test.active else -1)
            engine.maybe_timeout_negotiation(match)
            engine.maybe_timeout_floor_test(match)
            after = (match.status, len(match.floor_test.votes) if match.floor_test.active else -1)
            # Always push during an active election (rounds reveal purely by
            # elapsed time) or a live floor test countdown; otherwise only
            # push when something actually changed, to save bandwidth.
            if match.status == "election" or match.status == "floor_test" or before != after:
                await _broadcast(match)
    except asyncio.CancelledError:
        return


def _ensure_tick(match: CoalitionMatch) -> None:
    if match.tick_task is None or getattr(match.tick_task, "done", lambda: True)():
        match.tick_task = asyncio.create_task(_tick_loop(match.id))


# ── Create / Join ────────────────────────────────────────────────────────

@router.post("/create", response_model=CoalitionStateResponse)
async def create_coalition_match(payload: CreateCoalitionMatchRequest) -> CoalitionStateResponse:
    player_id, username = await _resolve_player(payload.token)
    match = coalition_registry.create_match(player_id, username)
    return _state_response(match, player_id)


@router.post("/join", response_model=CoalitionStateResponse)
async def join_coalition_match(payload: JoinCoalitionMatchRequest) -> CoalitionStateResponse:
    player_id, username = await _resolve_player(payload.token)
    try:
        match = coalition_registry.join_match(payload.join_code, player_id, username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast(match)
    return _state_response(match, player_id)


@router.get("/{match_id}", response_model=CoalitionStateResponse)
async def get_coalition_state(match_id: str, token: str = Query(...)) -> CoalitionStateResponse:
    player_id, _ = await _resolve_player(token)
    try:
        match = coalition_registry.require_seat(match_id, player_id)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _state_response(match, player_id)


# ── Quick Match — auto-groups 5 free players ────────────────────────────

@router.post("/quickmatch/join", response_model=CoalitionQuickMatchStatusResponse)
async def coalition_quickmatch_join(payload: CoalitionQuickMatchJoinRequest) -> CoalitionQuickMatchStatusResponse:
    player_id, username = await _resolve_player(payload.token)

    ready_match_id = coalition_quickmatch_queue.pop_ready(player_id)
    if ready_match_id:
        match = coalition_registry.get_match(ready_match_id)
        return CoalitionQuickMatchStatusResponse(status="matched", match=engine.to_info(match, player_id), queue_size=0)

    if coalition_quickmatch_queue.is_waiting(player_id):
        return CoalitionQuickMatchStatusResponse(
            status="waiting", match=None, queue_size=coalition_quickmatch_queue.queue_size(),
        )

    coalition_quickmatch_queue.add(player_id, username)
    group = coalition_quickmatch_queue.try_form_group()
    if group is None:
        return CoalitionQuickMatchStatusResponse(
            status="waiting", match=None, queue_size=coalition_quickmatch_queue.queue_size(),
        )

    host, rest = group[0], group[1:]
    match = coalition_registry.create_match(host.player_id, host.username)
    for entry in rest:
        coalition_registry.join_match(match.join_code, entry.player_id, entry.username)
    for entry in group:
        coalition_quickmatch_queue.mark_ready(entry.player_id, match.id)
    coalition_quickmatch_queue.pop_ready(player_id)
    return CoalitionQuickMatchStatusResponse(status="matched", match=engine.to_info(match, player_id), queue_size=0)


@router.get("/quickmatch/status", response_model=CoalitionQuickMatchStatusResponse)
async def coalition_quickmatch_status(token: str = Query(...)) -> CoalitionQuickMatchStatusResponse:
    player_id, _ = await _resolve_player(token)
    ready_match_id = coalition_quickmatch_queue.pop_ready(player_id)
    if ready_match_id:
        match = coalition_registry.get_match(ready_match_id)
        return CoalitionQuickMatchStatusResponse(status="matched", match=engine.to_info(match, player_id), queue_size=0)
    if coalition_quickmatch_queue.is_waiting(player_id):
        return CoalitionQuickMatchStatusResponse(
            status="waiting", match=None, queue_size=coalition_quickmatch_queue.queue_size(),
        )
    return CoalitionQuickMatchStatusResponse(status="idle", match=None, queue_size=coalition_quickmatch_queue.queue_size())


@router.post("/quickmatch/leave")
async def coalition_quickmatch_leave(payload: CoalitionQuickMatchJoinRequest) -> dict[str, bool]:
    player_id, _ = await _resolve_player(payload.token)
    coalition_quickmatch_queue.remove(player_id)
    return {"left": True}


# ── Negotiation ───────────────────────────────────────────────────────────

@router.post("/{match_id}/propose", response_model=CoalitionStateResponse)
async def propose_coalition(match_id: str, payload: ProposeCoalitionRequest) -> CoalitionStateResponse:
    player_id, _ = await _resolve_player(payload.token)
    match = _seat_or_404(match_id, player_id)
    try:
        engine.propose_coalition(match, player_id, payload.partner_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast(match)
    return _state_response(match, player_id)


@router.post("/{match_id}/respond", response_model=CoalitionStateResponse)
async def respond_coalition(match_id: str, payload: RespondCoalitionRequest) -> CoalitionStateResponse:
    player_id, _ = await _resolve_player(payload.token)
    match = _seat_or_404(match_id, player_id)
    try:
        engine.respond_to_proposal(match, player_id, payload.proposal_id, payload.accept)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast(match)
    return _state_response(match, player_id)


# ── Governing ────────────────────────────────────────────────────────────

@router.post("/{match_id}/ministry", response_model=CoalitionStateResponse)
async def allocate_ministry(match_id: str, payload: MinistryAllocationRequest) -> CoalitionStateResponse:
    player_id, _ = await _resolve_player(payload.token)
    match = _seat_or_404(match_id, player_id)
    try:
        engine.allocate_ministry(match, player_id, payload.minister_id, payload.ministry)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast(match)
    return _state_response(match, player_id)


@router.post("/{match_id}/siphon", response_model=CoalitionStateResponse)
async def siphon_funds(match_id: str, payload: SiphonRequest) -> CoalitionStateResponse:
    player_id, _ = await _resolve_player(payload.token)
    match = _seat_or_404(match_id, player_id)
    try:
        engine.siphon_funds(match, player_id, payload.amount, payload.cuts)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast(match)
    return _state_response(match, player_id)


@router.post("/{match_id}/blackmail", response_model=CoalitionStateResponse)
async def send_blackmail(match_id: str, payload: BlackmailRequest) -> CoalitionStateResponse:
    """Opposition -> a government partner, privately: 'withdraw support or
    I leak this to the press.' Kept lightweight (a log entry + image hit)
    rather than a full evidence graph, since corruption_graph.py already
    owns the real audit-trail mechanic."""
    player_id, _ = await _resolve_player(payload.token)
    match = _seat_or_404(match_id, player_id)
    if payload.target_id not in match.seats:
        raise HTTPException(status_code=400, detail="No such player in this match.")
    target = match.seats[payload.target_id]
    target.public_image_score = max(0, target.public_image_score - 8)
    match.log.append(
        f"✉️ {match.seats[player_id].username} privately messaged {target.username}: "
        f"\"{payload.evidence_note}\" — {payload.demand.replace('_', ' ')} or it gets leaked."
    )
    await _broadcast(match)
    return _state_response(match, player_id)


@router.post("/{match_id}/withdraw-support", response_model=CoalitionStateResponse)
async def withdraw_support(match_id: str, payload: WithdrawSupportRequest) -> CoalitionStateResponse:
    player_id, _ = await _resolve_player(payload.token)
    match = _seat_or_404(match_id, player_id)
    try:
        engine.withdraw_support(match, player_id)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast(match)
    return _state_response(match, player_id)


# ── Floor Test ───────────────────────────────────────────────────────────

@router.post("/{match_id}/floor-test/trigger", response_model=CoalitionStateResponse)
async def trigger_floor_test(match_id: str, payload: TriggerFloorTestRequest) -> CoalitionStateResponse:
    player_id, _ = await _resolve_player(payload.token)
    match = _seat_or_404(match_id, player_id)
    try:
        engine.trigger_floor_test(match, player_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast(match)
    return _state_response(match, player_id)


@router.post("/{match_id}/floor-test/vote", response_model=CoalitionStateResponse)
async def cast_floor_vote(match_id: str, payload: CastFloorVoteRequest) -> CoalitionStateResponse:
    player_id, _ = await _resolve_player(payload.token)
    match = _seat_or_404(match_id, player_id)
    try:
        engine.cast_floor_vote(match, player_id, payload.vote)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast(match)
    return _state_response(match, player_id)


# ── Final Election (2029) ───────────────────────────────────────────────

@router.post("/{match_id}/election/start", response_model=CoalitionStateResponse)
async def start_election(match_id: str, payload: TriggerFloorTestRequest) -> CoalitionStateResponse:
    player_id, _ = await _resolve_player(payload.token)
    match = _seat_or_404(match_id, player_id)
    if match.status not in ("governing", "negotiating"):
        raise HTTPException(status_code=400, detail="Election can only be called from a live game.")
    engine.start_election(match)
    await _broadcast(match)
    return _state_response(match, player_id)


# ── WebSocket ────────────────────────────────────────────────────────────

@router.websocket("/ws/{match_id}")
async def coalition_ws(websocket: WebSocket, match_id: str, token: str = Query(...)) -> None:
    try:
        player_id, _ = await _resolve_player(token)
        match = coalition_registry.require_seat(match_id, player_id)
    except (HTTPException, ValueError, PermissionError):
        await websocket.close(code=4001)
        return

    await connection_manager.connect(match_id, player_id, websocket)
    match.seats[player_id].connected = True
    _ensure_tick(match)
    await connection_manager.broadcast(match_id, {"type": "coalition_state", "match": engine.to_info(match).model_dump()})

    try:
        await websocket.send_text(
            json.dumps({"type": "coalition_state", "match": engine.to_info(match, player_id).model_dump()}, default=str)
        )
        while True:
            await websocket.receive_text()  # clients don't send anything meaningful; just keep the socket open
    except WebSocketDisconnect:
        pass
    finally:
        connection_manager.disconnect(match_id, player_id)
        match.seats[player_id].connected = False
        await connection_manager.broadcast(
            match_id, {"type": "coalition_state", "match": engine.to_info(match).model_dump()},
        )


def _seat_or_404(match_id: str, player_id: str) -> CoalitionMatch:
    try:
        return coalition_registry.require_seat(match_id, player_id)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
