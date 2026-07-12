"""
Coalition schemas — "The Coalition Era" 5-player mode.

Purely additive alongside schemas/match.py's 2-seat Match. A CoalitionMatch
is a 5-seat room: 101 Assembly seats are randomly split across 5 players by
ideology, nobody starts with a majority (51 needed), and players must
negotiate a Ruling Coalition vs an Opposition Bloc. Nothing here is imported
by match.py / prajatantra.py, so the existing 2-player game is untouched.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.prajatantra import Ideology, TenRoundSimulationResponse

MAGIC_NUMBER = 51
TOTAL_SEATS = 101

Ministry = Literal["Infrastructure", "Welfare", "Finance"]
CoalitionStatus = Literal[
    "waiting",          # < 5 players seated
    "negotiating",      # 5-minute window to form a government
    "governing",        # a coalition with >=51 seats is running the city
    "floor_test",       # a no-confidence vote is actively being cast
    "election",         # final 2029 election, round-by-round reveal
    "finished",
]


class CoalitionSeatInfo(BaseModel):
    player_id: str
    username: str
    ideology: Ideology
    party_seats: int
    # None while negotiating / in Opposition and not yet ranked.
    role: Literal["CM", "Deputy CM", "Minister", "Leader of Opposition", "Opposition", "Fringe", None] = None
    ministry: Ministry | None = None
    war_chest: int = 0            # black money successfully siphoned + hidden
    public_image_score: int = 50  # 0-100, damaged by leaks/blackmail
    in_government: bool = False
    connected: bool = False


class CoalitionProposal(BaseModel):
    proposal_id: str
    proposer_id: str
    partner_ids: list[str]
    accepted_by: list[str] = Field(default_factory=list)
    created_at: float


class FloorTestState(BaseModel):
    active: bool = False
    triggered_by: str | None = None
    deadline: float | None = None
    votes: dict[str, Literal["confidence", "no_confidence"]] = Field(default_factory=dict)
    last_resolved_at: float | None = None


class SiphonRequest(BaseModel):
    token: str
    amount: int = Field(gt=0)
    # partner_id -> fraction of the siphoned amount cut to them (0..1).
    # Whatever isn't cut to partners stays in the CM's own war chest.
    cuts: dict[str, float] = Field(default_factory=dict)


class MinistryAllocationRequest(BaseModel):
    token: str
    minister_id: str
    ministry: Ministry


class ProposeCoalitionRequest(BaseModel):
    token: str
    partner_ids: list[str] = Field(min_length=1)


class RespondCoalitionRequest(BaseModel):
    token: str
    proposal_id: str
    accept: bool


class WithdrawSupportRequest(BaseModel):
    token: str


class TriggerFloorTestRequest(BaseModel):
    token: str


class CastFloorVoteRequest(BaseModel):
    token: str
    vote: Literal["confidence", "no_confidence"]


class BlackmailRequest(BaseModel):
    token: str
    target_id: str
    evidence_note: str = Field(max_length=280)
    # If not paid off / support withdrawn, the sender can later leak it.
    demand: Literal["withdraw_support", "leak_share"] = "withdraw_support"


class CoalitionMatchInfo(BaseModel):
    match_id: str
    join_code: str
    status: CoalitionStatus
    seats: list[CoalitionSeatInfo]
    government_player_ids: list[str] = Field(default_factory=list)
    opposition_player_ids: list[str] = Field(default_factory=list)
    government_seat_total: int = 0
    cm_player_id: str | None = None
    lop_player_id: str | None = None
    siphon_percentage: int = 0
    treasury: int = 15_000_000
    pending_proposals: list[CoalitionProposal] = Field(default_factory=list)
    floor_test: FloorTestState = Field(default_factory=FloorTestState)
    negotiation_deadline: float | None = None
    floor_test_cooldown_until: float = 0.0
    election_started_at: float | None = None
    election_result: TenRoundSimulationResponse | None = None
    election_seats_by_player: dict[str, int] = Field(default_factory=dict)
    your_player_id: str | None = None
    log: list[str] = Field(default_factory=list)


class CoalitionStateResponse(BaseModel):
    match: CoalitionMatchInfo


class CreateCoalitionMatchRequest(BaseModel):
    token: str


class JoinCoalitionMatchRequest(BaseModel):
    token: str
    join_code: str


class CoalitionQuickMatchJoinRequest(BaseModel):
    token: str


class CoalitionQuickMatchStatusResponse(BaseModel):
    status: Literal["matched", "waiting", "idle"]
    match: CoalitionMatchInfo | None = None
    queue_size: int = 0
    needed: int = 5
