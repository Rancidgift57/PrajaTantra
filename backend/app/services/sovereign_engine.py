import random
import time
from dataclasses import dataclass, field
from uuid import uuid4

from app.schemas.prajatantra import (
    AuditResponse,
    CardAvailability,
    CityStats,
    ConstructionRequest,
    ConstructionResponse,
    CrisisActionRequest,
    CrisisActionResponse,
    CrisisEvent,
    EmergencyRequest,
    EmergencyResponse,
    FederalGrantRequest,
    FederalGrantResponse,
    InfrastructureBlock,
    LeakRequest,
    LeakResponse,
    PlayCardRequest,
    PlayCardResponse,
    RunElectionRequest,
    RunElectionResponse,
    ScamOperationRequest,
    SovereignStateResponse,
    StrikeRequest,
    StrikeResponse,
    TenRoundSimulationResponse,
    TradeDuelRequest,
    TradeDuelResponse,
    Ward,
)
from app.services.cooldown_store import cooldown_store
from app.services.corruption_graph import corruption_graph
from app.services.incumbency_engine import incumbency_engine
from app.services.seat_projection_engine import project_seats
from app.services.tactical_cards import CARD_CATALOG, get_card

# Elections can only be held once every ELECTION_COOLDOWN_DAYS. A "snap"
# election can be called explicitly (force_early=True) once at least
# EARLY_ELECTION_MIN_DAYS have passed — a deliberate political gamble that
# costs a little public trust, mirroring real-world early-election drama.
ELECTION_COOLDOWN_DAYS = 3.0
EARLY_ELECTION_MIN_DAYS = 2.5

# ── Flash Crises ─────────────────────────────────────────────────────────
CRISIS_CHANCE_PER_TICK = 0.15
CRISIS_WINDOW_SECONDS = 60.0
CRISIS_PATCH_COST_PER_SEVERITY = 60_000
CRISIS_AMPLIFY_IP_COST = 20
WARDS: list[Ward] = ["North", "East", "South", "West"]
_CRISIS_TEMPLATES = [
    ("Industrial Fire", "A blaze breaks out on a factory floor — workers evacuated, news cameras rolling.", 6),
    ("Water Pipeline Burst", "A major pipeline bursts, flooding a market street.", 5),
    ("Transport Strike Threat", "Auto-rickshaw unions threaten a flash strike over fuel prices.", 4),
    ("Hospital Overcrowding", "A ward hospital reports overcrowding after a viral outbreak.", 5),
    ("Bridge Crack Reported", "Engineers flag hairline cracks on a flyover support pillar.", 7),
]

# ── Tactical Cards ───────────────────────────────────────────────────────
SECTION144_STRIKE_BLOCK_SECONDS = 180
RTI_STING_FREEZE_SECONDS = 90
TOOLDOWN_HALT_SECONDS = 60


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
    # Epoch seconds of the last election held in this match; None = never
    # held one yet, so the very first election is always available.
    last_election_at: float | None = None
    # The most recent counting result, kept around so `state()` can embed
    # it in every WS broadcast — both players pace the same live,
    # round-by-round reveal off its counting_started_at timestamp, not just
    # whoever happened to click "Hold Election".
    last_election_result: TenRoundSimulationResponse | None = None
    # One-shot consumable set by the Incumbent's Media Distraction card;
    # halves the very next leak's trust damage, then resets to 1.0.
    leak_damage_multiplier_next: float = 1.0
    # A Flash Crisis currently awaiting a response (60s window), if any.
    active_crisis: CrisisEvent | None = None


class SovereignEngine:
    def __init__(self) -> None:
        self.memory = SovereignMemory()
        # Set by MatchRegistry right after creation so cooldown_store can
        # scope Tactical Card cooldowns per-match. None for the legacy
        # singleton `sovereign_engine` used by single-player routes.
        self.match_id: str | None = None
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
        available, early_available, seconds_remaining = self._election_status()
        self._unfreeze_expired_blocks()
        self.resolve_expired_crisis()
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
            election_available=available,
            # Only meaningful as a distinct "snap election" state while the
            # regular 3-day cooldown hasn't cleared yet.
            early_election_available=early_available and not available,
            election_cooldown_seconds_remaining=seconds_remaining,
            # Live Exit Poll — recalculated fresh on every state build, so
            # every WebSocket broadcast (any action, or the periodic tick)
            # carries an up-to-date projection.
            seat_projection=project_seats(self.memory.city, self.memory.blocks, self.memory.incumbent, self.memory.opposition),
            active_crisis=self.memory.active_crisis,
            card_availability=self._card_availability(),
            last_election_result=self.memory.last_election_result,
        )

    def _unfreeze_expired_blocks(self) -> None:
        now = time.time()
        for block in self.memory.blocks:
            if block.frozen_until is not None and now >= block.frozen_until:
                block.frozen_until = None
            if block.strike_blocked_until is not None and now >= block.strike_blocked_until:
                block.strike_blocked_until = None

    def _card_availability(self) -> list[CardAvailability]:
        match_id = self.match_id or "unscoped"
        results: list[CardAvailability] = []
        for card in CARD_CATALOG:
            ready_at = cooldown_store.get_ready_at(match_id, card.role, card.id)
            remaining = cooldown_store.seconds_remaining(match_id, card.role, card.id)
            results.append(
                CardAvailability(
                    card_id=card.id,
                    ready=remaining <= 0,
                    ready_at=ready_at if ready_at > 0 else None,
                    seconds_remaining=remaining,
                )
            )
        return results

    def _election_status(self) -> tuple[bool, bool, float]:
        """Returns (available, early_available, seconds_remaining_until_available)."""
        if self.memory.last_election_at is None:
            return True, False, 0.0
        elapsed_days = (time.time() - self.memory.last_election_at) / 86_400.0
        available = elapsed_days >= ELECTION_COOLDOWN_DAYS
        early_available = elapsed_days >= EARLY_ELECTION_MIN_DAYS
        remaining_days = max(0.0, ELECTION_COOLDOWN_DAYS - elapsed_days)
        return available, early_available, remaining_days * 86_400.0

    # ── Flash Crises ────────────────────────────────────────────────────────

    def maybe_trigger_crisis(self) -> None:
        """Called from the match's periodic tick loop only (never from a
        plain state() read) so crises spawn on a steady cadence rather than
        every time anyone happens to fetch state."""
        if self.memory.active_crisis is not None:
            return
        if random.random() > CRISIS_CHANCE_PER_TICK:
            return
        ward = random.choice(WARDS)
        headline, description, penalty = random.choice(_CRISIS_TEMPLATES)
        now = time.time()
        self.memory.active_crisis = CrisisEvent(
            id=uuid4().hex[:10],
            ward=ward,
            headline=f"{headline} in {ward} Ward",
            description=description,
            started_at=now,
            expires_at=now + CRISIS_WINDOW_SECONDS,
            base_trust_penalty=penalty,
        )
        self.memory.headlines.append(
            f"⏱️ FLASH: {headline} reported in {ward} Ward — 60 seconds to respond!"
        )

    def resolve_expired_crisis(self) -> None:
        crisis = self.memory.active_crisis
        if crisis is None or crisis.resolved:
            return
        if time.time() < crisis.expires_at:
            return
        if not crisis.patched:
            penalty = crisis.base_trust_penalty * (2 if crisis.amplified else 1)
            self.memory.city.public_trust = self._clamp(self.memory.city.public_trust - penalty)
            self.memory.headlines.append(
                f"📉 {crisis.ward} Ward crisis went unanswered — public trust fell by {penalty}."
                + (" Opposition's amplification doubled the damage." if crisis.amplified else "")
            )
        crisis.resolved = True
        self.memory.active_crisis = None

    def patch_crisis(self, payload: CrisisActionRequest) -> CrisisActionResponse:
        self._require_role(payload.role, "Incumbent", "Only the Incumbent can patch a crisis.")
        crisis = self.memory.active_crisis
        if crisis is None or crisis.id != payload.crisis_id or crisis.resolved:
            raise ValueError("No matching active crisis to patch.")
        if time.time() >= crisis.expires_at:
            raise ValueError("Too late — the response window already closed.")
        cost = crisis.base_trust_penalty * CRISIS_PATCH_COST_PER_SEVERITY
        if self.memory.city.treasury < cost:
            raise ValueError(f"Not enough treasury to patch this crisis (need ₹{cost:,}).")
        self.memory.city.treasury -= cost
        crisis.patched = True
        crisis.resolved = True
        self.memory.active_crisis = None
        self.memory.headlines.append(
            f"🛠️ {crisis.ward} Ward crisis contained — ₹{cost:,} spent, public trust held."
        )
        return CrisisActionResponse(state=self.state(), message=f"Crisis patched for ₹{cost:,}.")

    def amplify_crisis(self, payload: CrisisActionRequest) -> CrisisActionResponse:
        self._require_role(payload.role, "Opposition", "Only the Opposition can amplify a crisis narrative.")
        crisis = self.memory.active_crisis
        if crisis is None or crisis.id != payload.crisis_id or crisis.resolved:
            raise ValueError("No matching active crisis to amplify.")
        if time.time() >= crisis.expires_at:
            raise ValueError("Too late — the response window already closed.")
        if crisis.amplified:
            raise ValueError("This crisis is already amplified.")
        if self.memory.influence_points < CRISIS_AMPLIFY_IP_COST:
            raise ValueError(f"Not enough Influence Points to amplify (need {CRISIS_AMPLIFY_IP_COST} IP).")
        self.memory.influence_points -= CRISIS_AMPLIFY_IP_COST
        crisis.amplified = True
        self.memory.headlines.append(
            f"📢 Opposition is amplifying the {crisis.ward} Ward crisis narrative — "
            "the trust penalty will double if the Incumbent doesn't pay in time."
        )
        return CrisisActionResponse(
            state=self.state(),
            message="Narrative amplified — penalty doubles if the Incumbent doesn't pay in time.",
        )

    # ── Tactical Cards ──────────────────────────────────────────────────────

    def play_card(self, payload: PlayCardRequest) -> PlayCardResponse:
        card = get_card(payload.card_id)
        if card is None:
            raise ValueError("Unknown tactical card.")
        self._require_role(payload.role, card.role, f"Only the {card.role} can play {card.name}.")

        match_id = self.match_id or "unscoped"
        if not cooldown_store.is_ready(match_id, card.role, card.id):
            remaining = round(cooldown_store.seconds_remaining(match_id, card.role, card.id))
            raise ValueError(f"{card.name} is on cooldown for {remaining} more second(s).")

        now = time.time()
        if card.id == "SECTION_144":
            block = self._find_block(payload.target_block_id or "")
            block.strike_blocked_until = now + SECTION144_STRIKE_BLOCK_SECONDS
            message = f"🚧 Section 144 imposed on {block.name} — strikes blocked for 3 minutes."
        elif card.id == "MEDIA_DISTRACTION":
            self.memory.leak_damage_multiplier_next = 0.5
            message = "📺 Media Distraction primed — the next leaked scam will do half damage."
        elif card.id == "RTI_STING":
            block = self._find_block(payload.target_block_id or "")
            block.frozen_until = now + RTI_STING_FREEZE_SECONDS
            clawback = max(0, block.gold_per_tick)
            self.memory.city.treasury = max(0, self.memory.city.treasury - clawback)
            message = f"📄 RTI Sting freezes {block.name}'s revenue for 90s — ₹{clawback:,} clawed back immediately."
        elif card.id == "TOOLDOWN":
            block = self._find_block(payload.target_block_id or "")
            block.frozen_until = now + TOOLDOWN_HALT_SECONDS
            self.memory.city.worker_unrest = self._clamp(self.memory.city.worker_unrest + 15)
            message = f"🛑 {block.name} halted — citywide worker unrest spiked."
        else:
            raise ValueError("Unhandled tactical card.")

        cooldown_store.set_cooldown(match_id, card.role, card.id, card.cooldown_seconds)
        self.memory.headlines.append(message)
        return PlayCardResponse(state=self.state(), card_id=card.id, message=message)

    def run_election(self, payload: RunElectionRequest) -> RunElectionResponse:
        """
        Elections are rate-limited: by default one every 3 in-game days.
        An Incumbent who's confident (or desperate) can call an explicit
        early/snap election once at least 2.5 days have passed — but it
        costs a small public-trust hit for the political gamble.
        """
        self._require_role(payload.role, "Incumbent", "Only the Incumbent can call an election.")
        available, early_available, seconds_remaining = self._election_status()
        days_remaining = seconds_remaining / 86_400.0

        was_early = False
        if not available:
            if payload.force_early and early_available:
                was_early = True
            elif early_available:
                raise ValueError(
                    f"The next scheduled election isn't due for {days_remaining:.1f} more day(s). "
                    "A snap election is available now — call it explicitly if you want to risk it early."
                )
            else:
                raise ValueError(
                    f"Elections can only be held once every {ELECTION_COOLDOWN_DAYS:g} days. "
                    f"Next election in {days_remaining:.1f} day(s)."
                )

        result = incumbency_engine.simulate_ten_rounds(payload)
        self.memory.last_election_at = time.time()
        self.memory.last_election_result = result

        if was_early:
            self.memory.city.public_trust = self._clamp(self.memory.city.public_trust - 5)
            self.memory.headlines.append(
                f"⚡ Snap election called early! {result.winner} wins "
                f"{result.incumbent_seats}-{result.opposition_seats}-{result.independent_seats}."
            )
        else:
            self.memory.headlines.append(
                f"🗳️ Election held on schedule. {result.winner} wins "
                f"{result.incumbent_seats}-{result.opposition_seats}-{result.independent_seats}."
            )

        return RunElectionResponse(
            state=self.state(),
            result=result,
            was_early=was_early,
            message=(
                "⚡ Snap election called — public trust dipped slightly from the gamble."
                if was_early
                else "🗳️ Election held on schedule."
            ),
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
        if block.strike_blocked_until is not None and time.time() < block.strike_blocked_until:
            remaining = round(block.strike_blocked_until - time.time())
            raise ValueError(
                f"{block.name} is under Section 144 — strikes are blocked for {remaining} more second(s)."
            )
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

        # Media Distraction (Incumbent tactical card) halves the next leak's
        # damage — consumed here, one-shot.
        if self.memory.leak_damage_multiplier_next != 1.0:
            trust_damage = round(trust_damage * self.memory.leak_damage_multiplier_next)
            headline += " (Media Distraction blunted the story's impact.)"
            self.memory.leak_damage_multiplier_next = 1.0

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
