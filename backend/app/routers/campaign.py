"""
Campaign routes — the multi-city "Command Center" API.

Mounted independently from routers/match.py (single-city, 2-seat matches),
which is left completely untouched. A Campaign links 3-5 cities, each still
a full SovereignEngine instance, under two players holding opposite roles
in every city.

Auth note: these routes take player_id directly in the request body rather
than resolving it from a bearer token (unlike routers/match.py). That's a
deliberate scope-cut for this feature slice — swap in the same
`_resolve_player(token)` pattern used in routers/match.py before shipping
to production so a client can't spoof another player's player_id.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.campaign import (
    AdvancePhaseRequest,
    AdvancePhaseResponse,
    CampaignStateResponse,
    CreateCampaignRequest,
    ExposeLaunderingRequest,
    ExposeLaunderingResponse,
    FundOppositionRequest,
    FundOppositionResponse,
    JoinCampaignRequest,
    RetaliationRequest,
    RetaliationResponse,
    RunCityElectionRequest,
    RunCityElectionResponse,
    SiphonConstructRequest,
    SiphonConstructResponse,
)
from app.services.campaign_engine import campaign_engine

router = APIRouter(prefix="/api/campaign", tags=["campaign"])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


# ── Setup ────────────────────────────────────────────────────────────────

@router.post("/create", response_model=CampaignStateResponse)
async def create_campaign(payload: CreateCampaignRequest, host_player_id: str) -> CampaignStateResponse:
    campaign = campaign_engine.create_campaign(host_player_id, payload)
    return campaign_engine.state(campaign)


@router.post("/join", response_model=CampaignStateResponse)
async def join_campaign(payload: JoinCampaignRequest, player_id: str) -> CampaignStateResponse:
    try:
        campaign = campaign_engine.join_campaign(payload.join_code, player_id, payload.username)
    except ValueError as exc:
        raise _http_error(exc) from exc
    return campaign_engine.state(campaign)


@router.get("/{campaign_id}/state", response_model=CampaignStateResponse)
async def get_campaign_state(campaign_id: str) -> CampaignStateResponse:
    try:
        campaign = campaign_engine.get_campaign(campaign_id)
    except ValueError as exc:
        raise _http_error(exc) from exc
    return campaign_engine.state(campaign)


# ── 1. The Black Money Pipeline ────────────────────────────────────────

@router.post("/{campaign_id}/siphon-construct", response_model=SiphonConstructResponse)
async def siphon_construct(campaign_id: str, payload: SiphonConstructRequest) -> SiphonConstructResponse:
    try:
        campaign = campaign_engine.get_campaign(campaign_id)
        return await campaign_engine.siphon_construct(campaign, payload)
    except (PermissionError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.post("/{campaign_id}/fund-opposition", response_model=FundOppositionResponse)
async def fund_opposition(campaign_id: str, payload: FundOppositionRequest) -> FundOppositionResponse:
    try:
        campaign = campaign_engine.get_campaign(campaign_id)
        return campaign_engine.fund_opposition(campaign, payload.player_id, payload.target_city_id, payload.amount)
    except (PermissionError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.post("/{campaign_id}/expose-laundering", response_model=ExposeLaunderingResponse)
async def expose_laundering(campaign_id: str, payload: ExposeLaunderingRequest) -> ExposeLaunderingResponse:
    try:
        campaign = campaign_engine.get_campaign(campaign_id)
        return campaign_engine.expose_laundering(
            campaign, payload.exposer_player_id, payload.source_city_id, payload.audit_level
        )
    except (PermissionError, ValueError) as exc:
        raise _http_error(exc) from exc


# ── 2. Staggered Election Phases ───────────────────────────────────────

@router.post("/{campaign_id}/elections/run", response_model=RunCityElectionResponse)
async def run_city_election(campaign_id: str, payload: RunCityElectionRequest) -> RunCityElectionResponse:
    try:
        campaign = campaign_engine.get_campaign(campaign_id)
        return campaign_engine.run_city_election(campaign, payload.player_id, payload.city_id)
    except (PermissionError, ValueError) as exc:
        raise _http_error(exc) from exc


@router.post("/{campaign_id}/phase/advance", response_model=AdvancePhaseResponse)
async def advance_phase(campaign_id: str, payload: AdvancePhaseRequest) -> AdvancePhaseResponse:
    try:
        campaign = campaign_engine.get_campaign(campaign_id)
        campaign.player_by_id(payload.requesting_player_id)  # must be seated
        return campaign_engine.advance_phase(campaign)
    except (PermissionError, ValueError) as exc:
        raise _http_error(exc) from exc


# ── 4. Asymmetric Retaliation ──────────────────────────────────────────

@router.post("/{campaign_id}/retaliate", response_model=RetaliationResponse)
async def retaliate(campaign_id: str, payload: RetaliationRequest) -> RetaliationResponse:
    try:
        campaign = campaign_engine.get_campaign(campaign_id)
        return campaign_engine.retaliate(campaign, payload.actor_player_id, payload.source_city_id)
    except (PermissionError, ValueError) as exc:
        raise _http_error(exc) from exc
