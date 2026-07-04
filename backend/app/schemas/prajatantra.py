from typing import Literal

from pydantic import BaseModel, Field, computed_field


PortfolioType = Literal["Industrial", "Social", "Strategic"]
Ideology = Literal["Industrialist", "Green", "Socialist", "Nationalist", "Technocrat"]
PlayerRole = Literal["Incumbent", "Opposition"]


class ScamOperationRequest(BaseModel):
    city_id: str = Field(default="BLR_01", min_length=2)
    incumbent_username: str = Field(default="Mayor_Nikhil", min_length=2)
    department_name: str = Field(default="Health", min_length=2)
    portfolio_type: PortfolioType = "Social"
    project_name: str = Field(default="City Hospital", min_length=3)
    public_budget: int = Field(default=1_000_000, gt=0)
    siphon_percent: float = Field(default=30, ge=0, le=80)
    layer_depth: int = Field(default=1, ge=1, le=6)
    vendor_name: str = Field(default="Apex Medical Builders", min_length=2)

    @computed_field
    @property
    def siphoned_amount(self) -> int:
        return round(self.public_budget * self.siphon_percent / 100)

    @computed_field
    @property
    def actual_value(self) -> int:
        return self.public_budget - self.siphoned_amount


class GraphNode(BaseModel):
    id: str
    label: str
    name: str
    properties: dict[str, str | int | float | bool]


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    properties: dict[str, str | int | float | bool]


class ScamOperationResponse(BaseModel):
    project_id: str
    cypher: str
    parameters: dict[str, str | int | float | bool]
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    graph_backend: Literal["neo4j", "memory"]


class AuditRequest(BaseModel):
    project_id: str | None = None
    project_name: str = Field(default="City Hospital", min_length=3)
    audit_level: int = Field(default=2, ge=1, le=8)


class AuditPath(BaseModel):
    hop_count: int
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    suspicion_score: int = Field(ge=0, le=100)


class AuditResponse(BaseModel):
    project_id: str | None
    project_name: str
    audit_level: int
    corruption_detected: bool
    smoking_gun: str | None
    paths: list[AuditPath]
    next_upgrade_hint: str


class CityStats(BaseModel):
    gdp: int = Field(default=840_000, ge=0)
    health: int = Field(default=61, ge=0, le=100)
    treasury: int = Field(default=1_200_000, ge=0)
    unemployment: int = Field(default=18, ge=0, le=100)
    corruption_leaks: int = Field(default=1, ge=0)
    public_trust: int = Field(default=64, ge=0, le=100)
    pollution: int = Field(default=22, ge=0, le=100)
    worker_unrest: int = Field(default=19, ge=0, le=100)
    national_prestige: int = Field(default=31, ge=0, le=100)


class ElectionScoreRequest(BaseModel):
    city_stats: CityStats = Field(default_factory=CityStats)
    crises: list[str] = Field(default_factory=lambda: ["hospital bed shortage", "youth unemployment", "road congestion"])
    manifesto: str = Field(default="", max_length=4000)
    speech_transcript: str = Field(default="", max_length=8000)
    consecutive_terms: int = Field(
        default=1,
        ge=0,
        description="Consecutive terms the incumbent party has held power. Feeds the incumbency wave formula.",
    )


class ElectionScoreResponse(BaseModel):
    practicality_score: int = Field(ge=0, le=100)
    rhetoric_score: int = Field(ge=0, le=100)
    city_performance_score: int = Field(ge=0, le=100)
    trust_score: int = Field(ge=0, le=100)
    penalties: list[str]
    breakdown: dict[str, int | str | float]


class HeadlineRequest(BaseModel):
    mayor_username: str = "Mayor_Nikhil"
    department_name: str = "Health"
    public_budget: int = Field(default=1_000_000, ge=0)
    actual_value: int = Field(default=700_000, ge=0)
    mayor_wealth_delta: int = Field(default=250_000, ge=0)
    health_delta: int = Field(default=-12, ge=-100, le=100)
    gdp_delta: int = Field(default=4, ge=-100, le=100)


class PlayerMatchProfile(BaseModel):
    username: str
    political_mmr: int = Field(ge=0)
    ideology: Ideology
    trust: int = Field(ge=0, le=100)
    gdp_score: int = Field(ge=0, le=100)


class MatchmakingRequest(BaseModel):
    queued_player: PlayerMatchProfile
    candidates: list[PlayerMatchProfile]


class MatchmakingResponse(BaseModel):
    selected: PlayerMatchProfile | None
    friction_score: int = Field(ge=0, le=100)
    reason: str


class InfrastructureBlock(BaseModel):
    id: str
    name: str
    portfolio_type: PortfolioType
    level: int = Field(ge=1, le=5)
    gold_per_tick: int
    maintenance: int
    pollution_delta: int
    unrest_delta: int
    trust_delta: int
    prestige_delta: int


class SovereignStateResponse(BaseModel):
    cycle_day: int = Field(ge=1, le=7)
    active_role: PlayerRole
    incumbent: str
    opposition: str
    city: CityStats
    blocks: list[InfrastructureBlock]
    influence_points: int = Field(ge=0)
    audit_level: int = Field(ge=1, le=8)
    headlines: list[str]
    federal_grants: list[str]
    trade_buffs: list[str]
    emergency_powers: bool = Field(
        default=False,
        description="True once the Incumbent has declared Emergency after a >80% seat supermajority.",
    )


class ConstructionRequest(BaseModel):
    role: PlayerRole = "Incumbent"
    player_username: str = "Mayor_Nikhil"
    block_type: PortfolioType = "Industrial"
    name: str = "Foundry Belt"
    budget: int = Field(default=280_000, gt=0)
    siphon_percent: float = Field(default=15, ge=0, le=80)
    layer_depth: int = Field(default=1, ge=1, le=6)


class ConstructionResponse(BaseModel):
    state: SovereignStateResponse
    scam: ScamOperationResponse
    message: str


class StrikeRequest(BaseModel):
    role: PlayerRole = "Opposition"
    target_block_id: str
    influence_spend: int = Field(default=18, ge=1)


class StrikeResponse(BaseModel):
    state: SovereignStateResponse
    revenue_loss: int = Field(ge=0)
    unrest_added: int = Field(ge=0)
    message: str


class LeakRequest(BaseModel):
    role: PlayerRole = "Opposition"
    audit: AuditResponse


class LeakResponse(BaseModel):
    state: SovereignStateResponse
    trust_damage: int = Field(ge=0)
    headline: str


class FederalGrantRequest(BaseModel):
    prime_minister: str = "PM_Asha"
    target_city_id: str = "BLR_01"
    mayor_username: str = "Mayor_Nikhil"
    amount: int = Field(default=350_000, gt=0)
    alignment: Literal["ally", "rival", "swing"] = "ally"


class FederalGrantResponse(BaseModel):
    state: SovereignStateResponse
    national_treasury_remaining: int = Field(ge=0)
    message: str


class TradeDuelRequest(BaseModel):
    country_name: str = "Dakshin Republic"
    rival_country_name: str = "Northern Compact"
    net_exports: int = Field(default=78, ge=0, le=100)
    tariff_rate: int = Field(default=12, ge=0, le=100)
    supply_chain_resilience: int = Field(default=66, ge=0, le=100)
    rival_net_exports: int = Field(default=62, ge=0, le=100)
    rival_tariff_rate: int = Field(default=22, ge=0, le=100)
    rival_supply_chain_resilience: int = Field(default=58, ge=0, le=100)


class TradeDuelResponse(BaseModel):
    winner: str
    country_score: int
    rival_score: int
    gdp_buff_percent: int
    state: SovereignStateResponse


# ---------------------------------------------------------------------------
# Incumbency Wave schemas
# ---------------------------------------------------------------------------

class IncumbencyWaveRequest(BaseModel):
    """
    Inputs for calculating the macro incumbency factor (I_f).
    I_f = (global_trust - 50) - (scams_exposed × 15) - (consecutive_terms × 5)
    Clamped to [-40, +40].
    """

    global_trust: float = Field(
        default=64.0,
        ge=0.0,
        le=100.0,
        description="City-wide trust score (0–100). Below 50 → negative trust delta.",
    )
    scams_exposed: int = Field(
        default=1,
        ge=0,
        description="Number of corruption scams publicly exposed before election day.",
    )
    consecutive_terms: int = Field(
        default=1,
        ge=0,
        description="Number of consecutive terms the incumbent party has been in power.",
    )


class IncumbencyWaveResponse(BaseModel):
    incumbency_factor: float = Field(description="I_f clamped to [-40, +40].")
    wave_label: str = Field(description="Human-readable wave classification.")
    is_pro_incumbency: bool
    trust_delta: float = Field(description="(global_trust - 50) component.")
    scandal_drag: float = Field(description="(scams_exposed × 15) penalty.")
    fatigue_drag: float = Field(description="(consecutive_terms × 5) fatigue.")


class CountingRoundResult(BaseModel):
    round: int = Field(ge=1, le=24)
    incumbent_votes: int = Field(ge=0)
    opposition_votes: int = Field(ge=0)
    incumbent_share: float
    opposition_share: float
    running_incumbent_total: int = Field(ge=0)
    running_opposition_total: int = Field(ge=0)


class SeatResult(BaseModel):
    """One bloc in the final seat map (rendered as a hemicycle chart)."""

    party: str
    role: Literal["Incumbent", "Opposition", "Independent"]
    seats: int = Field(ge=0)
    color: str
    seat_share_pct: float


class TenRoundSimulationRequest(BaseModel):
    """
    Full 24-round counting simulation across a city's entire electorate.
    Polling day is held once every 3 in-game days; counting itself takes a
    2-hour live window split into 24 rounds (postal -> urban -> swing zones).
    The incumbency_factor is computed internally from the trust/scam/term fields.
    """

    global_trust: float = Field(default=64.0, ge=0.0, le=100.0)
    scams_exposed: int = Field(default=1, ge=0)
    consecutive_terms: int = Field(default=1, ge=0)

    incumbent_name: str = Field(default="Mayor_Nikhil")
    opposition_name: str = Field(default="Councillor_Asha")

    # Raw candidate profile match scores (0-100) before the wave modifier
    incumbent_match_score: float = Field(
        default=60.0,
        ge=0.0,
        le=100.0,
        description="Candidate-to-region profile match score for the incumbent.",
    )
    opposition_match_score: float = Field(
        default=55.0,
        ge=0.0,
        le=100.0,
        description="Candidate-to-region profile match score for the opposition.",
    )

    total_electorate: int = Field(
        default=100_000,
        gt=0,
        description="Total registered voters in the city.",
    )

    total_seats: int = Field(
        default=101,
        ge=1,
        le=999,
        description="Total assembly seats to distribute across the hemicycle seat map.",
    )

    manifesto_trust_score: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description=(
            "Trust score returned by /elections/grade (manifesto practicality + rhetoric + "
            "city performance + AI manifesto judging). When supplied it nudges seat swing on "
            "top of the raw match scores, so manifesto quality and development delivery "
            "actually move seats, not just the popular vote."
        ),
    )


class TenRoundSimulationResponse(BaseModel):
    incumbency_factor: float
    wave_label: str
    rounds: list[CountingRoundResult]
    final_incumbent_votes: int
    final_opposition_votes: int
    winner: str
    margin: int
    margin_pct: float
    # Echo the candidate names back so the frontend chart can label lines
    incumbent_name: str = "Sattadheen Dal"
    opposition_name: str = "Vipaksh Dal"


# ---------------------------------------------------------------------------
# Emergency (supermajority dictatorship-powers) schemas
# ---------------------------------------------------------------------------

class EmergencyRequest(BaseModel):
    """
    Declared by the Incumbent once a counting simulation reports
    emergency_eligible=True (i.e. the Incumbent cleared the seat-share
    threshold, default >80%). Grants sweeping construction powers: Industrial
    blocks can be built directly on Residential zones, bypassing normal
    zoning rules — a deliberate "authoritarian overreach" mechanic.
    """

    role: PlayerRole = "Incumbent"
    incumbent_seats: int = Field(ge=0)
    total_seats: int = Field(gt=0)
    threshold_pct: float = Field(default=80.0, ge=1.0, le=100.0)


class EmergencyResponse(BaseModel):
    state: SovereignStateResponse
    granted: bool
    seat_share_pct: float
    message: str

    # -- Election-day scheduling (flavour + UI countdowns) -------------------
    election_cycle_days: int = Field(default=3, description="Polling day recurs every N in-game days.")
    counting_duration_hours: int = Field(default=2, description="Live counting window length in hours.")
    total_rounds: int = Field(default=24, description="Number of counting rounds within the window.")

    # -- Seat map (hemicycle chart) ------------------------------------------
    total_seats: int = 101
    incumbent_seats: int = 0
    opposition_seats: int = 0
    independent_seats: int = 0
    seats: list[SeatResult] = Field(default_factory=list)

    # -- Emergency / supermajority powers -------------------------------------
    emergency_eligible: bool = Field(
        default=False,
        description="True once the winning side has cleared the seat-share threshold to declare Emergency.",
    )
    emergency_threshold_pct: float = 80.0
    emergency_message: str | None = None