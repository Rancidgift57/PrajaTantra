from dataclasses import dataclass, field
from uuid import uuid4

from app.schemas.prajatantra import (
    AuditResponse,
    CityStats,
    ConstructionRequest,
    ConstructionResponse,
    EmergencyRequest,
    EmergencyResponse,
    FederalGrantRequest,
    FederalGrantResponse,
    InfrastructureBlock,
    LeakRequest,
    LeakResponse,
    ScamOperationRequest,
    SovereignStateResponse,
    StrikeRequest,
    StrikeResponse,
    TradeDuelRequest,
    TradeDuelResponse,
)
from app.services.corruption_graph import corruption_graph


@dataclass
class SovereignMemory:
    cycle_day: int = 4
    active_role: str = "Incumbent"
    incumbent: str = "Mayor_Nikhil"
    opposition: str = "Councillor_Asha"
    city: CityStats = field(default_factory=CityStats)
    blocks: list[InfrastructureBlock] = field(default_factory=list)
    influence_points: int = 54
    audit_level: int = 2
    headlines: list[str] = field(
        default_factory=lambda: ["Municipal desk watching procurement and labor risk as campaign week tightens."]
    )
    federal_grants: list[str] = field(default_factory=list)
    trade_buffs: list[str] = field(default_factory=list)
    national_treasury: int = 2_800_000
    emergency_powers: bool = False


class SovereignEngine:
    def __init__(self) -> None:
        self.memory = SovereignMemory()
        if not self.memory.blocks:
            self.memory.blocks.extend(
                [
                    InfrastructureBlock(
                        id="IND-001",
                        name="Textile Export Cluster",
                        portfolio_type="Industrial",
                        level=2,
                        gold_per_tick=92_000,
                        maintenance=18_000,
                        pollution_delta=9,
                        unrest_delta=7,
                        trust_delta=-3,
                        prestige_delta=1,
                    ),
                    InfrastructureBlock(
                        id="SOC-001",
                        name="Ward Health Network",
                        portfolio_type="Social",
                        level=1,
                        gold_per_tick=12_000,
                        maintenance=42_000,
                        pollution_delta=-2,
                        unrest_delta=-3,
                        trust_delta=9,
                        prestige_delta=1,
                    ),
                    InfrastructureBlock(
                        id="STR-001",
                        name="Orbital Research Desk",
                        portfolio_type="Strategic",
                        level=1,
                        gold_per_tick=28_000,
                        maintenance=52_000,
                        pollution_delta=1,
                        unrest_delta=0,
                        trust_delta=1,
                        prestige_delta=12,
                    ),
                ]
            )

    def state(self) -> SovereignStateResponse:
        return SovereignStateResponse(
            cycle_day=self.memory.cycle_day,
            active_role=self.memory.active_role,  # type: ignore[arg-type]
            incumbent=self.memory.incumbent,
            opposition=self.memory.opposition,
            city=self.memory.city,
            blocks=self.memory.blocks,
            influence_points=self.memory.influence_points,
            audit_level=self.memory.audit_level,
            headlines=self.memory.headlines[-6:],
            federal_grants=self.memory.federal_grants[-4:],
            trade_buffs=self.memory.trade_buffs[-4:],
            emergency_powers=self.memory.emergency_powers,
        )

    def declare_emergency(self, payload: EmergencyRequest) -> EmergencyResponse:
        """
        Only reachable once a counting simulation reports the Incumbent
        cleared the seat-share threshold (default >80%). Grants sweeping
        construction powers: Industrial blocks may now be built directly on
        Residential zones on the City Map, bypassing normal zoning rules.
        """
        self._require_role(payload.role, "Incumbent", "Only the Incumbent can declare Emergency.")
        seat_share_pct = round((payload.incumbent_seats / payload.total_seats) * 100, 2) if payload.total_seats else 0.0
        if seat_share_pct <= payload.threshold_pct:
            raise ValueError(
                f"Emergency requires more than {payload.threshold_pct}% of seats "
                f"(currently {seat_share_pct}%)."
            )

        already_declared = self.memory.emergency_powers
        self.memory.emergency_powers = True
        if not already_declared:
            self.memory.city.public_trust = self._clamp(self.memory.city.public_trust - 6)
            self.memory.headlines.append(
                f"🚨 Emergency declared: {payload.incumbent_seats}/{payload.total_seats} seats "
                f"({seat_share_pct}%). Industrial zoning restrictions suspended citywide."
            )

        return EmergencyResponse(
            state=self.state(),
            granted=True,
            seat_share_pct=seat_share_pct,
            message=(
                "Emergency powers already in effect — Industrial construction bypasses "
                "Residential zoning."
                if already_declared
                else "Emergency powers granted. Industrial construction can now be built "
                "directly on Residential zones, like a dictatorship overriding city planning."
            ),
        )

    async def construct(self, payload: ConstructionRequest) -> ConstructionResponse:
        self._require_role(payload.role, "Incumbent", "Only the Incumbent can open the Construction Tab.")

        block = self._block_from_request(payload)
        self.memory.blocks.append(block)
        self.memory.city.treasury = max(0, self.memory.city.treasury - payload.budget)
        self.memory.city.gdp += max(0, block.gold_per_tick - block.maintenance) * 3
        self.memory.city.public_trust = self._clamp(self.memory.city.public_trust + block.trust_delta)
        self.memory.city.pollution = self._clamp(self.memory.city.pollution + block.pollution_delta)
        self.memory.city.worker_unrest = self._clamp(self.memory.city.worker_unrest + block.unrest_delta)
        self.memory.city.national_prestige = self._clamp(self.memory.city.national_prestige + block.prestige_delta)

        scam = await corruption_graph.create_layered_scam(
            ScamOperationRequest(
                city_id="BLR_01",
                incumbent_username=payload.player_username,
                department_name=f"{payload.block_type} Development",
                portfolio_type=payload.block_type,
                project_name=payload.name,
                public_budget=payload.budget,
                siphon_percent=payload.siphon_percent,
                layer_depth=payload.layer_depth,
                vendor_name=f"{payload.name} Prime Contractor",
            )
        )

        self.memory.headlines.append(
            f"{payload.name} commissioned under {payload.block_type} portfolio; opposition auditors log a new data point."
        )
        return ConstructionResponse(
            state=self.state(),
            scam=scam,
            message=f"{payload.name} is live. The build improves the city but leaves an auditable trail.",
        )

    def strike(self, payload: StrikeRequest) -> StrikeResponse:
        self._require_role(payload.role, "Opposition", "Only the Opposition can organize labor strikes.")
        block = self._find_block(payload.target_block_id)
        if payload.influence_spend > self.memory.influence_points:
            raise ValueError("Not enough Influence Points for this strike.")

        is_industrial = block.portfolio_type == "Industrial"
        multiplier = 2 if is_industrial else 1
        revenue_loss = min(block.gold_per_tick, payload.influence_spend * 2_800 * multiplier)
        unrest_added = 4 * multiplier
        block.gold_per_tick = max(0, block.gold_per_tick - revenue_loss)
        block.unrest_delta += unrest_added
        self.memory.influence_points -= payload.influence_spend
        self.memory.city.gdp = max(0, self.memory.city.gdp - revenue_loss * 2)
        self.memory.city.worker_unrest = self._clamp(self.memory.city.worker_unrest + unrest_added)
        self.memory.city.public_trust = self._clamp(self.memory.city.public_trust - (2 * multiplier))
        self.memory.headlines.append(
            f"Strike alert: {block.name} revenue stalls as labor organizers pressure the ruling council."
        )
        return StrikeResponse(
            state=self.state(),
            revenue_loss=revenue_loss,
            unrest_added=unrest_added,
            message=f"{block.name} disrupted. Industrial targets suffer the hardest revenue shock.",
        )

    def leak(self, payload: LeakRequest) -> LeakResponse:
        self._require_role(payload.role, "Opposition", "Only the Opposition can leak audit findings.")
        best_suspicion = max((path.suspicion_score for path in payload.audit.paths), default=0)
        trust_damage = 6 + round(best_suspicion / 10)
        if payload.audit.corruption_detected:
            trust_damage += 12
            headline = f"Smoking-gun ledger leak shakes City Hall: {payload.audit.smoking_gun}."
        else:
            headline = f"Opposition leak raises procurement questions around {payload.audit.project_name}."

        self.memory.city.public_trust = self._clamp(self.memory.city.public_trust - trust_damage)
        self.memory.city.corruption_leaks += 1
        self.memory.influence_points += 8 if payload.audit.corruption_detected else 3
        self.memory.headlines.append(headline)
        return LeakResponse(state=self.state(), trust_damage=trust_damage, headline=headline)

    def federal_grant(self, payload: FederalGrantRequest) -> FederalGrantResponse:
        grant = min(payload.amount, self.memory.national_treasury)
        self.memory.national_treasury -= grant
        self.memory.city.treasury += grant
        trust_delta = 5 if payload.alignment == "ally" else -4 if payload.alignment == "rival" else 2
        self.memory.city.public_trust = self._clamp(self.memory.city.public_trust + trust_delta)
        message = (
            f"{payload.prime_minister} routed {grant} gold to {payload.mayor_username} "
            f"as a {payload.alignment} grant."
        )
        self.memory.federal_grants.append(message)
        self.memory.headlines.append(f"Federal grant desk confirms {grant} gold for {payload.target_city_id}.")
        return FederalGrantResponse(
            state=self.state(),
            national_treasury_remaining=self.memory.national_treasury,
            message=message,
        )

    def trade_duel(self, payload: TradeDuelRequest) -> TradeDuelResponse:
        country_score = self._trade_score(payload.net_exports, payload.tariff_rate, payload.supply_chain_resilience)
        rival_score = self._trade_score(payload.rival_net_exports, payload.rival_tariff_rate, payload.rival_supply_chain_resilience)
        winner = payload.country_name if country_score >= rival_score else payload.rival_country_name
        buff = 20 if winner == payload.country_name else 0
        if buff:
            self.memory.city.gdp = round(self.memory.city.gdp * 1.2)
            self.memory.city.national_prestige = self._clamp(self.memory.city.national_prestige + 8)
            self.memory.trade_buffs.append(f"{payload.country_name} wins a 20% GDP buff from trade-war leverage.")
        else:
            self.memory.city.public_trust = self._clamp(self.memory.city.public_trust - 4)
            self.memory.trade_buffs.append(f"{payload.rival_country_name} wins the trade duel; BLR_01 gets no buff.")

        return TradeDuelResponse(
            winner=winner,
            country_score=country_score,
            rival_score=rival_score,
            gdp_buff_percent=buff,
            state=self.state(),
        )

    def _block_from_request(self, payload: ConstructionRequest) -> InfrastructureBlock:
        siphon_drag = round(payload.siphon_percent / 10)
        if payload.block_type == "Industrial":
            return InfrastructureBlock(
                id=f"IND-{uuid4().hex[:5].upper()}",
                name=payload.name,
                portfolio_type=payload.block_type,
                level=1,
                gold_per_tick=round(payload.budget * 0.26),
                maintenance=round(payload.budget * 0.06),
                pollution_delta=10 + siphon_drag,
                unrest_delta=7 + siphon_drag,
                trust_delta=-3 - siphon_drag,
                prestige_delta=2,
            )
        if payload.block_type == "Social":
            return InfrastructureBlock(
                id=f"SOC-{uuid4().hex[:5].upper()}",
                name=payload.name,
                portfolio_type=payload.block_type,
                level=1,
                gold_per_tick=round(payload.budget * 0.06),
                maintenance=round(payload.budget * 0.14),
                pollution_delta=-2,
                unrest_delta=-5,
                trust_delta=12 - siphon_drag,
                prestige_delta=2,
            )
        return InfrastructureBlock(
            id=f"STR-{uuid4().hex[:5].upper()}",
            name=payload.name,
            portfolio_type=payload.block_type,
            level=1,
            gold_per_tick=round(payload.budget * 0.1),
            maintenance=round(payload.budget * 0.13),
            pollution_delta=2,
            unrest_delta=1,
            trust_delta=1 - siphon_drag,
            prestige_delta=14,
        )

    def _find_block(self, block_id: str) -> InfrastructureBlock:
        for block in self.memory.blocks:
            if block.id == block_id:
                return block
        raise ValueError("Target block does not exist.")

    def _require_role(self, role: str, required: str, message: str) -> None:
        if role != required:
            raise PermissionError(message)

    def _trade_score(self, exports: int, tariff: int, resilience: int) -> int:
        tariff_drag = abs(tariff - 15)
        return max(0, round((exports * 0.5) + (resilience * 0.4) + (max(0, 30 - tariff_drag) * 0.1)))

    def _clamp(self, value: int) -> int:
        return max(0, min(100, value))


sovereign_engine = SovereignEngine()

