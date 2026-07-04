from fastapi import APIRouter, HTTPException

from app.schemas.prajatantra import (
    AuditRequest,
    AuditResponse,
    ElectionScoreRequest,
    ElectionScoreResponse,
    ConstructionRequest,
    ConstructionResponse,
    EmergencyRequest,
    EmergencyResponse,
    FederalGrantRequest,
    FederalGrantResponse,
    HeadlineRequest,
    IncumbencyWaveRequest,
    IncumbencyWaveResponse,
    LeakRequest,
    LeakResponse,
    MatchmakingRequest,
    MatchmakingResponse,
    ScamOperationRequest,
    ScamOperationResponse,
    SovereignStateResponse,
    StrikeRequest,
    StrikeResponse,
    TenRoundSimulationRequest,
    TenRoundSimulationResponse,
    TradeDuelRequest,
    TradeDuelResponse,
)
from app.services.corruption_graph import corruption_graph
from app.services.election_engine import election_engine
from app.services.incumbency_engine import incumbency_engine
from app.services.matchmaking import matchmaking_engine
from app.services.media_engine import media_engine
from app.services.sovereign_engine import sovereign_engine


router = APIRouter(prefix="/api/prajatantra", tags=["prajatantra"])


@router.get("/state", response_model=SovereignStateResponse)
async def get_sovereign_state() -> SovereignStateResponse:
    return sovereign_engine.state()


@router.post("/construction/build", response_model=ConstructionResponse)
async def build_infrastructure(payload: ConstructionRequest) -> ConstructionResponse:
    try:
        return await sovereign_engine.construct(payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/opposition/strike", response_model=StrikeResponse)
async def organize_strike(payload: StrikeRequest) -> StrikeResponse:
    try:
        return sovereign_engine.strike(payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/opposition/leak", response_model=LeakResponse)
async def leak_audit(payload: LeakRequest) -> LeakResponse:
    try:
        return sovereign_engine.leak(payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/federal/grant", response_model=FederalGrantResponse)
async def issue_federal_grant(payload: FederalGrantRequest) -> FederalGrantResponse:
    return sovereign_engine.federal_grant(payload)


@router.post("/global/trade-duel", response_model=TradeDuelResponse)
async def resolve_trade_duel(payload: TradeDuelRequest) -> TradeDuelResponse:
    return sovereign_engine.trade_duel(payload)


@router.post("/scams/layered", response_model=ScamOperationResponse)
async def create_layered_scam(payload: ScamOperationRequest) -> ScamOperationResponse:
    return await corruption_graph.create_layered_scam(payload)


@router.post("/audits/project", response_model=AuditResponse)
async def audit_project(payload: AuditRequest) -> AuditResponse:
    return await corruption_graph.audit_project(payload)


@router.post("/elections/grade", response_model=ElectionScoreResponse)
async def grade_election(payload: ElectionScoreRequest) -> ElectionScoreResponse:
    return election_engine.grade(payload)


@router.post("/media/headlines")
async def generate_headlines(payload: HeadlineRequest) -> dict[str, list[str]]:
    return {"headlines": media_engine.generate(payload)}


@router.post("/matchmaking/pair", response_model=MatchmakingResponse)
async def pair_players(payload: MatchmakingRequest) -> MatchmakingResponse:
    return matchmaking_engine.pair(payload)


# ── Incumbency Wave endpoints ───────────────────────────────────────────────

@router.post("/elections/incumbency-wave", response_model=IncumbencyWaveResponse)
async def compute_incumbency_wave(payload: IncumbencyWaveRequest) -> IncumbencyWaveResponse:
    """
    Calculate the macro Incumbency Factor (I_f) for an election.

    I_f = (global_trust - 50) - (scams_exposed × 15) - (consecutive_terms × 5)

    Positive I_f → Pro-Incumbency wave.
    Negative I_f → Anti-Incumbency wave.
    """
    return incumbency_engine.compute_wave(payload)


@router.post("/elections/simulate-counting", response_model=TenRoundSimulationResponse)
async def simulate_ten_round_counting(payload: TenRoundSimulationRequest) -> TenRoundSimulationResponse:
    """
    Run a full 24-round vote-counting simulation with the incumbency wave
    applied to each round's jittered ballot packet, then convert the final
    tally into a seat map (default 101 seats).

    Election day recurs every 3 in-game days; counting is a live 2-hour
    window split into 24 rounds:
    - Rounds 1–6   → postal ballots / rural pockets
    - Rounds 7–18  → urban centres
    - Rounds 19–24 → volatile swing zones (highest jitter)

    If the winning side clears an 80% seat supermajority, the response sets
    `emergency_eligible=True`; the Incumbent can then call
    `/emergency/declare` to unlock dictatorship-style construction powers.
    """
    return incumbency_engine.simulate_ten_rounds(payload)


@router.post("/emergency/declare", response_model=EmergencyResponse)
async def declare_emergency(payload: EmergencyRequest) -> EmergencyResponse:
    """
    Declares Emergency once the Incumbent holds more than the seat-share
    threshold (default 80%). Grants sweeping powers: Industrial blocks can
    now be built directly on Residential zones on the City Map.
    """
    try:
        return sovereign_engine.declare_emergency(payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc