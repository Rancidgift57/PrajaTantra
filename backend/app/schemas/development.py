"""
City Development schemas for PrajaTantra.

Adds a real building catalog (Ports, Malls, Factories, Waste Management
Plants, etc.) and a Government Scheme system, both layered on top of the
existing Industrial/Social/Strategic portfolio system in `prajatantra.py`.

Kept in a separate module so the existing construction flow
(ConstructionRequest/ConstructionResponse/InfrastructureBlock) is never
touched — this file is purely additive, same pattern as auth.py.
"""
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.prajatantra import InfrastructureBlock, PlayerRole, PortfolioType, SovereignStateResponse

BuildingId = Literal[
    "PORT",
    "MALL",
    "FACTORY",
    "WASTE_PLANT",
    "TECH_PARK",
    "POWER_GRID",
    "SCHOOL_NETWORK",
    "HOSPITAL_CHAIN",
]

SchemeId = Literal[
    "SUBSIDY_MSME",
    "FREE_HEALTHCARE",
    "SWACHH_ABHIYAN",
    "SKILL_MISSION",
    "GREEN_ENERGY_SUBSIDY",
    "FARMER_LOAN_WAIVER",
]


# ── Building catalog ────────────────────────────────────────────────────────

class BuildingCatalogEntry(BaseModel):
    id: BuildingId
    name: str
    hindi_name: str
    portfolio_type: PortfolioType
    description: str
    base_cost: int = Field(gt=0)
    # Per-tick effects at level 1 — scale with level on construction
    gold_per_tick: int
    maintenance: int
    pollution_delta: int = Field(ge=-20, le=30)
    unrest_delta: int = Field(ge=-20, le=30)
    trust_delta: int = Field(ge=-20, le=20)
    prestige_delta: int = Field(ge=-10, le=20)
    employment_delta: int = Field(
        ge=-20,
        le=30,
        description=(
            "Effect on jobs. Positive values REDUCE city.unemployment (more jobs created); "
            "negative values increase it. Maps onto the existing CityStats.unemployment field."
        ),
    )
    # Strategic tradeoff tags shown in the UI so the choice has real weight
    pros: list[str]
    cons: list[str]


class BuildingCatalogResponse(BaseModel):
    buildings: list[BuildingCatalogEntry]


class BuildFromCatalogRequest(BaseModel):
    role: PlayerRole = "Incumbent"
    player_username: str = "Mayor_Nikhil"
    building_id: BuildingId
    custom_name: str | None = Field(default=None, max_length=60)
    budget: int = Field(default=300_000, gt=0)
    siphon_percent: float = Field(default=15, ge=0, le=80)
    layer_depth: int = Field(default=1, ge=1, le=6)


class BuildFromCatalogResponse(BaseModel):
    state: SovereignStateResponse
    block: InfrastructureBlock
    message: str


# ── Government Scheme catalog ───────────────────────────────────────────────

class SchemeCatalogEntry(BaseModel):
    id: SchemeId
    name: str
    hindi_name: str
    description: str
    upfront_cost: int = Field(ge=0)
    cost_per_tick: int = Field(
        ge=0, description="Ongoing treasury drain each cycle while the scheme is active."
    )
    duration_cycles: int = Field(ge=1, le=20)
    # City-wide effects applied immediately on launch, distinct from
    # building effects — these represent policy, not physical infrastructure.
    trust_delta: int = Field(ge=-10, le=25)
    unrest_delta: int = Field(ge=-25, le=10)
    employment_delta: int = Field(
        ge=-10,
        le=25,
        description="Positive values REDUCE city.unemployment; negative values increase it.",
    )
    pollution_delta: int = Field(ge=-25, le=10)
    gdp_multiplier_percent: int = Field(
        ge=-10, le=30, description="One-time % GDP bump (or drag) on launch."
    )
    pros: list[str]
    cons: list[str]


class SchemeCatalogResponse(BaseModel):
    schemes: list[SchemeCatalogEntry]


class LaunchSchemeRequest(BaseModel):
    role: PlayerRole = "Incumbent"
    scheme_id: SchemeId


class ActiveScheme(BaseModel):
    scheme_id: SchemeId
    name: str
    hindi_name: str
    cycles_remaining: int
    cost_per_tick: int


class LaunchSchemeResponse(BaseModel):
    state: SovereignStateResponse
    active_scheme: ActiveScheme
    message: str