"""
Campaign schemas — the "multi-city war room" layer.
=====================================================
A Campaign links 3-5 existing SovereignEngine cities under two players who
hold OPPOSITE roles in each city (whoever is Incumbent in City A is
Opposition in City B, etc.) so both players always have something to
defend and something to attack. Everything here is additive: it sits on
top of SovereignEngine/ConstructionRequest/etc. and never modifies them.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.prajatantra import ConstructionRequest, PlayerRole, SovereignStateResponse


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

class CreateCampaignRequest(BaseModel):
    host_username: str = Field(default="Mayor_Nikhil", min_length=2)
    city_names: list[str] = Field(
        default_factory=lambda: ["Bengaluru", "Mumbai", "Chennai", "Delhi"],
        min_length=3,
        max_length=5,
        description="3-5 cities. Phase schedule is derived automatically: "
        "City 1 votes alone on Day 1 (Phase 1), the rest split across "
        "Phase 2 and Phase 3 the way real staggered elections do.",
    )


class JoinCampaignRequest(BaseModel):
    join_code: str
    username: str = Field(min_length=2)


class CampaignCityInfo(BaseModel):
    city_id: str
    name: str
    phase: int
    voting_open: bool
    incumbent_player_id: str
    opposition_player_id: str
    incumbent_username: str
    opposition_username: str
    election_completed: bool
    winner_player_id: str | None
    momentum_trust_buff: int
    warnings: list[str] = Field(
        default_factory=list,
        description="e.g. '⚠️ Strike', '🚨 Audit in Progress' — for the Global Map sidebar icons.",
    )


class OffshoreAccountInfo(BaseModel):
    player_id: str
    username: str
    balance: int
    laundering_fee_pct: float
    traced: bool = Field(
        default=False,
        description="True once an audit has exposed the source project — the account is frozen "
        "and can no longer fund campaigns elsewhere until it cools down.",
    )
    frozen_until: float | None = None
    ip_debuff_multiplier: float = 1.0
    ip_debuff_until: float | None = None


class CampaignStateResponse(BaseModel):
    campaign_id: str
    join_code: str
    status: Literal["waiting", "active", "finished"]
    current_phase: int
    total_phases: int
    phase_schedule: list[list[str]]
    cities: list[CampaignCityInfo]
    accounts: list[OffshoreAccountInfo]
    headlines: list[str]


# ---------------------------------------------------------------------------
# The Black Money Pipeline
# ---------------------------------------------------------------------------

class SiphonConstructRequest(BaseModel):
    """Build a project in one of your Incumbent cities the normal way, but
    route the siphoned cut into your Private Offshore Account instead of it
    vanishing into flavour text."""

    player_id: str
    city_id: str
    construction: ConstructionRequest


class SiphonConstructResponse(BaseModel):
    city_state: SovereignStateResponse
    offshore_balance: int
    siphoned_gross: int
    laundering_fee: int
    siphoned_net: int
    message: str


class FundOppositionRequest(BaseModel):
    """Spend from your Private Offshore Account (built from City A's siphon)
    to fund YOUR OWN opposition campaign in City B — riots, strikes, media
    buys — where you hold the Opposition seat."""

    player_id: str
    target_city_id: str
    amount: int = Field(gt=0)


class FundOppositionResponse(BaseModel):
    city_state: SovereignStateResponse
    offshore_balance_remaining: int
    influence_points_granted: int
    message: str


class ExposeLaunderingRequest(BaseModel):
    """The Incumbent's opponent (i.e. whoever is Opposition in source_city_id)
    audits the Highway/project and exposes the offshore pipeline feeding it."""

    exposer_player_id: str
    source_city_id: str
    audit_level: int = Field(default=3, ge=1, le=8)


class ExposeLaunderingResponse(BaseModel):
    source_city_state: SovereignStateResponse
    exposed_player_id: str
    trust_penalty_applied: int
    account_frozen: bool
    frozen_until: float | None
    dried_up_cities: list[str] = Field(
        default_factory=list,
        description="Cities whose opposition funding dries up instantly because the pipeline was exposed.",
    )
    message: str


# ---------------------------------------------------------------------------
# Staggered Election Phases
# ---------------------------------------------------------------------------

class AdvancePhaseRequest(BaseModel):
    requesting_player_id: str


class AdvancePhaseResponse(BaseModel):
    state: CampaignStateResponse
    newly_opened_cities: list[str]
    message: str


class RunCityElectionRequest(BaseModel):
    player_id: str
    city_id: str


class RunCityElectionResponse(BaseModel):
    state: CampaignStateResponse
    winner_player_id: str
    winner_username: str
    momentum_applied_to: list[str]
    message: str


# ---------------------------------------------------------------------------
# Asymmetric Retaliation (Misusing State Machinery)
# ---------------------------------------------------------------------------

RETALIATION_DEBUFF_SECONDS = 300
RETALIATION_IP_MULTIPLIER = 0.4


class RetaliationRequest(BaseModel):
    """Played from a city where the caller is Incumbent. Docks the rival's
    global Influence Points (in every city they hold a seat in) for 5
    minutes — mutually-assured-destruction, state-machinery-abuse style."""

    actor_player_id: str
    source_city_id: str


class RetaliationResponse(BaseModel):
    source_city_state: SovereignStateResponse
    target_player_id: str
    debuff_multiplier: float
    debuff_seconds: int
    message: str
