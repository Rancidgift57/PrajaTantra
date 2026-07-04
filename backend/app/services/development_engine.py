"""
DevelopmentEngine
-----------------
Adds real strategic depth to PrajaTantra beyond raw budget/siphon sliders:

  1. A fixed Building Catalog (Port, Mall, Factory, Waste Management Plant,
     Tech Park, Power Grid, School Network, Hospital Chain) — each with a
     genuine tradeoff (jobs vs pollution, trust vs revenue, etc.) instead of
     one generic formula per portfolio type.

  2. Government Schemes — time-limited policy interventions (subsidies,
     welfare programmes) that cost treasury per cycle and apply city-wide
     effects, completely separate from physical construction. This is the
     "not just managing finances" lever: a scheme is a political choice with
     duration and recurring cost, not a one-time purchase.

Both mutate the existing `sovereign_engine.memory` singleton directly so
they integrate with every other system (elections, audits, leaderboard)
without requiring any changes to those engines.
"""
from __future__ import annotations

from uuid import uuid4

from app.schemas.development import (
    ActiveScheme,
    BuildFromCatalogRequest,
    BuildFromCatalogResponse,
    BuildingCatalogEntry,
    BuildingCatalogResponse,
    BuildingId,
    LaunchSchemeRequest,
    LaunchSchemeResponse,
    SchemeCatalogEntry,
    SchemeCatalogResponse,
    SchemeId,
)
from app.schemas.prajatantra import InfrastructureBlock, ScamOperationRequest
from app.services.corruption_graph import corruption_graph
from app.services.sovereign_engine import SovereignEngine, sovereign_engine

# ── Building catalog (static reference data) ────────────────────────────────

BUILDING_CATALOG: dict[BuildingId, BuildingCatalogEntry] = {
    "PORT": BuildingCatalogEntry(
        id="PORT",
        name="Container Port",
        hindi_name="बंदरगाह",
        portfolio_type="Industrial",
        description="Deep-water cargo port. Massive export revenue and jobs, but heavy pollution and worker risk.",
        base_cost=600_000,
        gold_per_tick=140_000,
        maintenance=32_000,
        pollution_delta=16,
        unrest_delta=10,
        trust_delta=-4,
        prestige_delta=6,
        employment_delta=18,
        pros=["Highest gold/tick of any building", "Strong national prestige", "Big employment boost"],
        cons=["Heaviest pollution in the catalog", "High worker unrest from shift labor", "Trust dips on launch"],
    ),
    "MALL": BuildingCatalogEntry(
        id="MALL",
        name="Commercial Mall",
        hindi_name="वाणिज्यिक मॉल",
        portfolio_type="Industrial",
        description="Retail and entertainment complex. Reliable mid-tier revenue with low political risk.",
        base_cost=320_000,
        gold_per_tick=68_000,
        maintenance=21_000,
        pollution_delta=3,
        unrest_delta=-1,
        trust_delta=2,
        prestige_delta=2,
        employment_delta=10,
        pros=["Low pollution for an Industrial building", "Slightly improves trust", "Cheapest Industrial option"],
        cons=["Lower revenue ceiling than a Port or Factory", "Minimal prestige gain"],
    ),
    "FACTORY": BuildingCatalogEntry(
        id="FACTORY",
        name="Manufacturing Factory",
        hindi_name="विनिर्माण कारखाना",
        portfolio_type="Industrial",
        description="Heavy manufacturing. Strong, steady revenue and the biggest jobs number in the game.",
        base_cost=480_000,
        gold_per_tick=104_000,
        maintenance=26_000,
        pollution_delta=12,
        unrest_delta=6,
        trust_delta=-2,
        prestige_delta=3,
        employment_delta=22,
        pros=["Best employment_delta in the catalog", "Solid revenue", "Cheaper than a Port"],
        cons=["Significant pollution", "Unrest creeps up with each shift expansion"],
    ),
    "WASTE_PLANT": BuildingCatalogEntry(
        id="WASTE_PLANT",
        name="Waste Management Plant",
        hindi_name="अपशिष्ट प्रबंधन संयंत्र",
        portfolio_type="Social",
        description="Modern waste processing. The only building that actively REDUCES pollution city-wide.",
        base_cost=260_000,
        gold_per_tick=8_000,
        maintenance=38_000,
        pollution_delta=-18,
        unrest_delta=-4,
        trust_delta=10,
        prestige_delta=1,
        employment_delta=6,
        pros=["Only building that cuts pollution", "Strong trust gain", "Cheap relative to its political payoff"],
        cons=["Negative net revenue (maintenance > gold/tick)", "Low prestige", "No export value"],
    ),
    "TECH_PARK": BuildingCatalogEntry(
        id="TECH_PARK",
        name="Tech Park",
        hindi_name="प्रौद्योगिकी पार्क",
        portfolio_type="Strategic",
        description="IT/software campus. High-skill jobs, low pollution, and a meaningful prestige boost.",
        base_cost=420_000,
        gold_per_tick=58_000,
        maintenance=29_000,
        pollution_delta=1,
        unrest_delta=0,
        trust_delta=3,
        prestige_delta=10,
        employment_delta=14,
        pros=["Near-zero pollution", "Strong prestige gain", "Good employment without unrest"],
        cons=["Highest maintenance-to-revenue ratio among Strategic options", "Slow GDP ramp"],
    ),
    "POWER_GRID": BuildingCatalogEntry(
        id="POWER_GRID",
        name="Renewable Power Grid",
        hindi_name="नवीकरणीय ऊर्जा ग्रिड",
        portfolio_type="Strategic",
        description="Solar/wind grid expansion. Powers every other building more cheaply, cutting city-wide maintenance pressure.",
        base_cost=540_000,
        gold_per_tick=22_000,
        maintenance=44_000,
        pollution_delta=-8,
        unrest_delta=-2,
        trust_delta=6,
        prestige_delta=14,
        employment_delta=8,
        pros=["Reduces pollution AND unrest simultaneously", "Highest prestige_delta in the catalog", "Green credentials boost trust"],
        cons=["Most expensive base_cost", "Lowest gold_per_tick relative to cost", "Long payback period"],
    ),
    "SCHOOL_NETWORK": BuildingCatalogEntry(
        id="SCHOOL_NETWORK",
        name="Public School Network",
        hindi_name="सार्वजनिक विद्यालय नेटवर्क",
        portfolio_type="Social",
        description="Expanded primary/secondary education access. Builds long-term human capital and voter goodwill.",
        base_cost=300_000,
        gold_per_tick=4_000,
        maintenance=34_000,
        pollution_delta=-1,
        unrest_delta=-6,
        trust_delta=14,
        prestige_delta=3,
        employment_delta=9,
        pros=["Best unrest reduction of any Social building", "Strong trust gain", "Creates teaching jobs"],
        cons=["Almost no direct revenue", "Net treasury drain every cycle"],
    ),
    "HOSPITAL_CHAIN": BuildingCatalogEntry(
        id="HOSPITAL_CHAIN",
        name="Public Hospital Chain",
        hindi_name="सार्वजनिक अस्पताल श्रृंखला",
        portfolio_type="Social",
        description="Multi-ward hospital expansion. The single biggest trust generator, at real treasury cost.",
        base_cost=380_000,
        gold_per_tick=6_000,
        maintenance=46_000,
        pollution_delta=-2,
        unrest_delta=-5,
        trust_delta=18,
        prestige_delta=2,
        employment_delta=11,
        pros=["Highest trust_delta in the catalog", "Strong unrest reduction", "Good employment from medical staff"],
        cons=["Highest maintenance of any Social building", "Negative net revenue", "Slow to pay for itself"],
    ),
}


# ── Government Scheme catalog (static reference data) ──────────────────────

SCHEME_CATALOG: dict[SchemeId, SchemeCatalogEntry] = {
    "SUBSIDY_MSME": SchemeCatalogEntry(
        id="SUBSIDY_MSME",
        name="MSME Subsidy Scheme",
        hindi_name="एमएसएमई सब्सिडी योजना",
        description="Tax breaks and low-interest loans for small/medium industry. Quick GDP bump, modest cost.",
        upfront_cost=180_000,
        cost_per_tick=12_000,
        duration_cycles=6,
        trust_delta=6,
        unrest_delta=-3,
        employment_delta=12,
        pollution_delta=2,
        gdp_multiplier_percent=8,
        pros=["Fast employment gain", "Immediate GDP bump", "Popular with the Industrialist base"],
        cons=["Small pollution uptick", "Recurring treasury drain for 6 cycles"],
    ),
    "FREE_HEALTHCARE": SchemeCatalogEntry(
        id="FREE_HEALTHCARE",
        name="Universal Free Healthcare",
        hindi_name="सार्वभौमिक मुफ्त स्वास्थ्य सेवा",
        description="City-wide free clinics and medicine. The single strongest trust play in the scheme catalog.",
        upfront_cost=260_000,
        cost_per_tick=22_000,
        duration_cycles=10,
        trust_delta=16,
        unrest_delta=-8,
        employment_delta=4,
        pollution_delta=0,
        gdp_multiplier_percent=-2,
        pros=["Highest trust_delta of any scheme", "Strongest unrest reduction", "Long-lasting (10 cycles)"],
        cons=["Most expensive cost_per_tick", "Small negative GDP drag", "Long-term treasury commitment"],
    ),
    "SWACHH_ABHIYAN": SchemeCatalogEntry(
        id="SWACHH_ABHIYAN",
        name="Swachh Shehar Abhiyan (Clean City Mission)",
        hindi_name="स्वच्छ शहर अभियान",
        description="City-wide cleanliness and anti-littering drive. Cheap, fast pollution relief.",
        upfront_cost=90_000,
        cost_per_tick=8_000,
        duration_cycles=5,
        trust_delta=8,
        unrest_delta=0,
        employment_delta=3,
        pollution_delta=-14,
        gdp_multiplier_percent=0,
        pros=["Cheapest scheme to launch", "Strong pollution reduction without a Waste Plant", "Quick trust win"],
        cons=["No GDP benefit", "Short duration (5 cycles)", "Minimal employment impact"],
    ),
    "SKILL_MISSION": SchemeCatalogEntry(
        id="SKILL_MISSION",
        name="National Skill Mission",
        hindi_name="राष्ट्रीय कौशल मिशन",
        description="Vocational training centers for unemployed youth. Slow burn but compounds with Industrial buildings.",
        upfront_cost=140_000,
        cost_per_tick=10_000,
        duration_cycles=8,
        trust_delta=5,
        unrest_delta=-5,
        employment_delta=16,
        pollution_delta=0,
        gdp_multiplier_percent=4,
        pros=["Best pure employment_delta among schemes", "Synergizes with Factory/Port building", "Reduces unrest"],
        cons=["Slowest to show GDP results", "8-cycle commitment"],
    ),
    "GREEN_ENERGY_SUBSIDY": SchemeCatalogEntry(
        id="GREEN_ENERGY_SUBSIDY",
        name="Green Energy Subsidy",
        hindi_name="हरित ऊर्जा सब्सिडी",
        description="Rebates for solar adoption and EV infrastructure. Pairs naturally with a Power Grid.",
        upfront_cost=200_000,
        cost_per_tick=14_000,
        duration_cycles=7,
        trust_delta=7,
        unrest_delta=-2,
        employment_delta=6,
        pollution_delta=-10,
        gdp_multiplier_percent=3,
        pros=["Strong pollution reduction", "Decent trust gain", "Stacks with Power Grid building"],
        cons=["Mid-tier cost for mid-tier results", "Doesn't move unrest much"],
    ),
    "FARMER_LOAN_WAIVER": SchemeCatalogEntry(
        id="FARMER_LOAN_WAIVER",
        name="Farmer Loan Waiver",
        hindi_name="किसान ऋण माफी",
        description="One-time debt relief for agricultural loans. Huge immediate trust spike, real fiscal cost, hurts GDP perception.",
        upfront_cost=420_000,
        cost_per_tick=0,
        duration_cycles=1,
        trust_delta=22,
        unrest_delta=-12,
        employment_delta=0,
        pollution_delta=0,
        gdp_multiplier_percent=-6,
        pros=["Single biggest trust_delta of any scheme or building", "Massive unrest relief", "One-time cost only, no recurring drain"],
        cons=["Very expensive upfront", "Hurts GDP perception (creditors/investors react badly)", "No employment or pollution benefit"],
    ),
}


class DevelopmentEngine:
    """Mutates `sovereign_engine.memory` to add catalog buildings and active
    government schemes. Deliberately stateless itself — all state lives on
    the shared sovereign_engine singleton, same pattern the rest of the app
    uses, so /api/prajatantra/state automatically reflects everything here."""

    def __init__(self, sovereign: SovereignEngine | None = None) -> None:
        # Defaults to the global singleton so existing single-player routes
        # (development.py router) behave exactly as before. Multiplayer
        # matches instead pass in their own dedicated SovereignEngine.
        self._sovereign = sovereign or sovereign_engine
        self._active_schemes: dict[SchemeId, ActiveScheme] = {}

    # ── Catalog listing ──────────────────────────────────────────────────

    def building_catalog(self) -> BuildingCatalogResponse:
        return BuildingCatalogResponse(buildings=list(BUILDING_CATALOG.values()))

    def scheme_catalog(self) -> SchemeCatalogResponse:
        return SchemeCatalogResponse(schemes=list(SCHEME_CATALOG.values()))

    def active_schemes(self) -> list[ActiveScheme]:
        return list(self._active_schemes.values())

    # ── Building construction from catalog ──────────────────────────────

    async def build_from_catalog(self, payload: BuildFromCatalogRequest) -> BuildFromCatalogResponse:
        if payload.role != "Incumbent":
            raise PermissionError("Only the Incumbent can develop the city.")

        entry = BUILDING_CATALOG[payload.building_id]
        if payload.budget < entry.base_cost:
            raise ValueError(
                f"{entry.name} requires at least Rs {entry.base_cost:,} to break ground. "
                f"Increase the budget or choose a cheaper building."
            )

        memory = self._sovereign.memory
        siphon_drag = round(payload.siphon_percent / 10)
        scale = payload.budget / entry.base_cost  # bigger budget = a bigger version of the same building

        block = InfrastructureBlock(
            id=f"{payload.building_id}-{uuid4().hex[:5].upper()}",
            name=payload.custom_name or entry.name,
            portfolio_type=entry.portfolio_type,
            level=1,
            gold_per_tick=round(entry.gold_per_tick * scale),
            maintenance=round(entry.maintenance * scale),
            pollution_delta=entry.pollution_delta + siphon_drag,
            unrest_delta=entry.unrest_delta + siphon_drag,
            trust_delta=entry.trust_delta - siphon_drag,
            prestige_delta=entry.prestige_delta,
        )

        memory.blocks.append(block)
        memory.city.treasury = max(0, memory.city.treasury - payload.budget)
        memory.city.gdp += max(0, block.gold_per_tick - block.maintenance) * 3
        memory.city.public_trust = self._clamp(memory.city.public_trust + block.trust_delta)
        memory.city.pollution = self._clamp(memory.city.pollution + block.pollution_delta)
        memory.city.worker_unrest = self._clamp(memory.city.worker_unrest + block.unrest_delta)
        memory.city.national_prestige = self._clamp(memory.city.national_prestige + block.prestige_delta)
        # employment_delta is positive-good, but unemployment is positive-bad — invert when applying
        memory.city.unemployment = self._clamp(memory.city.unemployment - entry.employment_delta)

        # Every catalog building still leaves an auditable corruption trail,
        # exactly like generic construction — siphoning is universal.
        await corruption_graph.create_layered_scam(
            ScamOperationRequest(
                city_id="BLR_01",
                incumbent_username=payload.player_username,
                department_name=f"{entry.portfolio_type} Development",
                portfolio_type=entry.portfolio_type,
                project_name=block.name,
                public_budget=payload.budget,
                siphon_percent=payload.siphon_percent,
                layer_depth=payload.layer_depth,
                vendor_name=f"{block.name} Prime Contractor",
            )
        )
        # Note: the scam record is intentionally not surfaced on this response
        # to keep the contract simple — the audit/graph panel already
        # discovers it the same way it discovers generic construction scams,
        # via /api/prajatantra/audits/project.

        memory.headlines.append(
            f"{block.name} ({entry.hindi_name}) commissioned under {entry.portfolio_type} portfolio "
            f"- {'jobs up' if entry.employment_delta > 0 else 'jobs steady'}, "
            f"{'pollution cut' if entry.pollution_delta < 0 else 'pollution rising'}."
        )

        return BuildFromCatalogResponse(
            state=self._sovereign.state(),
            block=block,
            message=f"{block.name} is operational. {entry.description}",
        )

    # ── Government schemes ──────────────────────────────────────────────

    def launch_scheme(self, payload: LaunchSchemeRequest) -> LaunchSchemeResponse:
        if payload.role != "Incumbent":
            raise PermissionError("Only the Incumbent can launch a government scheme.")
        if payload.scheme_id in self._active_schemes:
            raise ValueError(f"{SCHEME_CATALOG[payload.scheme_id].name} is already active in this city.")

        entry = SCHEME_CATALOG[payload.scheme_id]
        memory = self._sovereign.memory

        if memory.city.treasury < entry.upfront_cost:
            raise ValueError(
                f"Treasury cannot cover the Rs {entry.upfront_cost:,} upfront cost of {entry.name}."
            )

        memory.city.treasury -= entry.upfront_cost
        memory.city.public_trust = self._clamp(memory.city.public_trust + entry.trust_delta)
        memory.city.worker_unrest = self._clamp(memory.city.worker_unrest + entry.unrest_delta)
        memory.city.pollution = self._clamp(memory.city.pollution + entry.pollution_delta)
        memory.city.unemployment = self._clamp(memory.city.unemployment - entry.employment_delta)
        memory.city.gdp = round(memory.city.gdp * (1 + entry.gdp_multiplier_percent / 100))

        active = ActiveScheme(
            scheme_id=entry.id,
            name=entry.name,
            hindi_name=entry.hindi_name,
            cycles_remaining=entry.duration_cycles,
            cost_per_tick=entry.cost_per_tick,
        )
        self._active_schemes[entry.id] = active

        memory.headlines.append(
            f"{entry.name} ({entry.hindi_name}) launched city-wide - "
            f"{'trust surges' if entry.trust_delta >= 10 else 'cautious public reaction'}."
        )

        return LaunchSchemeResponse(
            state=self._sovereign.state(),
            active_scheme=active,
            message=f"{entry.name} is now live for {entry.duration_cycles} cycles. {entry.description}",
        )

    def tick_schemes(self) -> None:
        """Called once per simulated cycle (e.g. alongside cycle_day advance)
        to drain ongoing scheme costs and expire finished schemes. Not yet
        wired to an automatic clock - call manually or from a future
        cycle-advance endpoint."""
        memory = self._sovereign.memory
        expired: list[SchemeId] = []
        for scheme_id, active in self._active_schemes.items():
            memory.city.treasury = max(0, memory.city.treasury - active.cost_per_tick)
            active.cycles_remaining -= 1
            if active.cycles_remaining <= 0:
                expired.append(scheme_id)
        for scheme_id in expired:
            entry = SCHEME_CATALOG[scheme_id]
            del self._active_schemes[scheme_id]
            memory.headlines.append(f"{entry.name} has concluded its run.")

    def _clamp(self, value: int) -> int:
        return max(0, min(100, value))


development_engine = DevelopmentEngine()