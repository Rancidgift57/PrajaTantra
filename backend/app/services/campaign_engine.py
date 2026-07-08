"""
CampaignEngine — the multi-city "Black Money Pipeline" war room.
==================================================================
Wraps N (3-5) independent SovereignEngine instances — one per city — under
two players who hold OPPOSITE roles in every city: whoever is Incumbent in
City A is automatically Opposition in City B, and vice versa. That
asymmetry is what makes the four headline mechanics possible:

  1. Black Money Pipeline   — siphon from your Incumbent city's projects
     into a Private Offshore Account, then spend that account funding YOUR
     OWN opposition campaign in a city where you're Opposition.
  2. Staggered Election Phases — cities vote in waves; winning Phase 1
     grants a Momentum Buff (+10% base Trust) to that player's races in the
     next phase's cities.
  3. Command Center state — CampaignStateResponse is shaped for a
     multi-city sidebar UI (per-city warnings, phase, roles) in one call.
  4. Asymmetric Retaliation — "Arrest Opposition Leaders", playable from
     any city you're Incumbent in, docks the rival's Influence Points in
     every city they hold a seat in for 5 minutes.

This module never modifies SovereignEngine/SovereignMemory — it only reads
`.state()` and calls its existing public methods (`construct`, `run_election`,
etc.), so single-city matches (routers/match.py, routers/prajatantra.py)
are completely unaffected.
"""
from __future__ import annotations

import secrets
import string
import time
from dataclasses import dataclass, field
from uuid import uuid4

from app.schemas.campaign import (
    RETALIATION_DEBUFF_SECONDS,
    RETALIATION_IP_MULTIPLIER,
    AdvancePhaseResponse,
    CampaignCityInfo,
    CampaignStateResponse,
    CreateCampaignRequest,
    ExposeLaunderingResponse,
    FundOppositionResponse,
    OffshoreAccountInfo,
    RetaliationResponse,
    RunCityElectionResponse,
    SiphonConstructRequest,
    SiphonConstructResponse,
)
from app.schemas.prajatantra import ConstructionRequest, PlayerRole, RunElectionRequest
from app.services.sovereign_engine import SovereignEngine

LAUNDERING_FEE_PCT = 5.0
LAUNDER_TRACE_FREEZE_SECONDS = 240
EXPOSE_TRUST_PENALTY = 22
FUND_OPPOSITION_IP_RATE = 1 / 3_500  # gold spent -> Influence Points granted
FUND_OPPOSITION_UNREST_PER_10K = 1
FUND_OPPOSITION_TRUST_DRAG_PER_10K = 1


def _new_id() -> str:
    return secrets.token_hex(8)


def _new_join_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _phase_schedule(n_cities: int) -> list[list[int]]:
    """Domino-effect schedule. City 0 always votes alone on Day 1 so its
    result can cast a Momentum Buff shadow over everything after it."""
    if n_cities <= 3:
        return [[i] for i in range(n_cities)]
    if n_cities == 4:
        return [[0], [1, 2], [3]]
    return [[0], [1, 2], [3, 4]]


@dataclass
class CampaignPlayer:
    player_id: str
    username: str
    offshore_balance: int = 0
    account_frozen_until: float | None = None
    account_traced: bool = False
    ip_debuff_multiplier: float = 1.0
    ip_debuff_until: float | None = None

    def is_frozen(self) -> bool:
        return self.account_frozen_until is not None and time.time() < self.account_frozen_until

    def ip_multiplier(self) -> float:
        if self.ip_debuff_until is not None and time.time() < self.ip_debuff_until:
            return self.ip_debuff_multiplier
        return 1.0


@dataclass
class CampaignCity:
    city_id: str
    name: str
    phase: int  # 1-indexed
    sovereign: SovereignEngine
    incumbent_player_id: str
    opposition_player_id: str
    voting_open: bool = False
    election_completed: bool = False
    winner_player_id: str | None = None
    momentum_trust_buff: int = 0

    def role_of(self, player_id: str) -> PlayerRole | None:
        if player_id == self.incumbent_player_id:
            return "Incumbent"
        if player_id == self.opposition_player_id:
            return "Opposition"
        return None

    def warnings(self) -> list[str]:
        warnings: list[str] = []
        state = self.sovereign.state()
        if state.active_crisis is not None:
            warnings.append("⚠️ Strike")
        if any(b.frozen_until is not None for b in state.blocks):
            warnings.append("🚨 Audit in Progress")
        if state.emergency_powers:
            warnings.append("🛑 Emergency")
        return warnings


@dataclass
class Campaign:
    id: str = field(default_factory=_new_id)
    join_code: str = field(default_factory=_new_join_code)
    status: str = "waiting"  # waiting -> active -> finished
    player_a: CampaignPlayer | None = None
    player_b: CampaignPlayer | None = None
    cities: dict[str, CampaignCity] = field(default_factory=dict)
    phase_order: list[list[str]] = field(default_factory=list)  # city_ids, grouped by phase
    current_phase: int = 1
    headlines: list[str] = field(default_factory=list)

    def players(self) -> list[CampaignPlayer]:
        return [p for p in (self.player_a, self.player_b) if p is not None]

    def player_by_id(self, player_id: str) -> CampaignPlayer:
        for p in self.players():
            if p.player_id == player_id:
                return p
        raise PermissionError("You are not seated in this campaign.")

    def opponent_of(self, player_id: str) -> CampaignPlayer:
        for p in self.players():
            if p.player_id != player_id:
                return p
        raise ValueError("No opponent seated yet.")

    def cities_for_player(self, player_id: str) -> list[CampaignCity]:
        return [c for c in self.cities.values() if c.role_of(player_id) is not None]


class CampaignEngine:
    def __init__(self) -> None:
        self._campaigns: dict[str, Campaign] = {}
        self._by_join_code: dict[str, str] = {}

    # ── Setup ──────────────────────────────────────────────────────────

    def create_campaign(self, host_player_id: str, payload: CreateCampaignRequest) -> Campaign:
        campaign = Campaign()
        campaign.player_a = CampaignPlayer(player_id=host_player_id, username=payload.host_username)

        n = len(payload.city_names)
        schedule = _phase_schedule(n)
        campaign.phase_order = []
        for phase_idx, indices in enumerate(schedule, start=1):
            phase_city_ids: list[str] = []
            for i in indices:
                city_id = f"C{i + 1}_{uuid4().hex[:4].upper()}"
                sovereign = SovereignEngine()
                sovereign.match_id = f"{campaign.id}:{city_id}"
                # Player A is Incumbent in even-indexed cities, Opposition in
                # odd-indexed ones — guaranteed asymmetry once player B joins.
                incumbent_id = host_player_id if i % 2 == 0 else "PENDING_OPPONENT"
                opposition_id = "PENDING_OPPONENT" if i % 2 == 0 else host_player_id
                city = CampaignCity(
                    city_id=city_id,
                    name=payload.city_names[i],
                    phase=phase_idx,
                    sovereign=sovereign,
                    incumbent_player_id=incumbent_id,
                    opposition_player_id=opposition_id,
                    voting_open=(phase_idx == 1),
                )
                sovereign.memory.incumbent = payload.host_username if i % 2 == 0 else "TBD"
                sovereign.memory.opposition = "TBD" if i % 2 == 0 else payload.host_username
                campaign.cities[city_id] = city
                phase_city_ids.append(city_id)
            campaign.phase_order.append(phase_city_ids)

        self._campaigns[campaign.id] = campaign
        self._by_join_code[campaign.join_code] = campaign.id
        return campaign

    def join_campaign(self, join_code: str, player_id: str, username: str) -> Campaign:
        campaign_id = self._by_join_code.get(join_code.strip().upper())
        if not campaign_id or campaign_id not in self._campaigns:
            raise ValueError("No campaign found with that join code.")
        campaign = self._campaigns[campaign_id]

        if campaign.player_a and campaign.player_a.player_id == player_id:
            return campaign
        if campaign.player_b and campaign.player_b.player_id == player_id:
            return campaign
        if campaign.player_b is not None:
            raise ValueError("This campaign already has two players.")

        campaign.player_b = CampaignPlayer(player_id=player_id, username=username)
        for city in campaign.cities.values():
            if city.incumbent_player_id == "PENDING_OPPONENT":
                city.incumbent_player_id = player_id
                city.sovereign.memory.incumbent = username
            if city.opposition_player_id == "PENDING_OPPONENT":
                city.opposition_player_id = player_id
                city.sovereign.memory.opposition = username
        campaign.status = "active"
        campaign.headlines.append(f"🗺️ {username} has taken their seats — the multi-city campaign is live.")
        return campaign

    def get_campaign(self, campaign_id: str) -> Campaign:
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            raise ValueError("Campaign not found.")
        return campaign

    # ── State ──────────────────────────────────────────────────────────

    def state(self, campaign: Campaign) -> CampaignStateResponse:
        cities_info = [
            CampaignCityInfo(
                city_id=c.city_id,
                name=c.name,
                phase=c.phase,
                voting_open=c.voting_open,
                incumbent_player_id=c.incumbent_player_id,
                opposition_player_id=c.opposition_player_id,
                incumbent_username=c.sovereign.memory.incumbent,
                opposition_username=c.sovereign.memory.opposition,
                election_completed=c.election_completed,
                winner_player_id=c.winner_player_id,
                momentum_trust_buff=c.momentum_trust_buff,
                warnings=c.warnings(),
            )
            for c in campaign.cities.values()
        ]
        accounts_info = [
            OffshoreAccountInfo(
                player_id=p.player_id,
                username=p.username,
                balance=p.offshore_balance,
                laundering_fee_pct=LAUNDERING_FEE_PCT,
                traced=p.account_traced,
                frozen_until=p.account_frozen_until,
                ip_debuff_multiplier=p.ip_debuff_multiplier if p.ip_multiplier() != 1.0 else 1.0,
                ip_debuff_until=p.ip_debuff_until,
            )
            for p in campaign.players()
        ]
        return CampaignStateResponse(
            campaign_id=campaign.id,
            join_code=campaign.join_code,
            status=campaign.status,  # type: ignore[arg-type]
            current_phase=campaign.current_phase,
            total_phases=len(campaign.phase_order),
            phase_schedule=campaign.phase_order,
            cities=cities_info,
            accounts=accounts_info,
            headlines=campaign.headlines[-12:],
        )

    def _city(self, campaign: Campaign, city_id: str) -> CampaignCity:
        city = campaign.cities.get(city_id)
        if city is None:
            raise ValueError("Unknown city_id in this campaign.")
        return city

    # ── 1. The Black Money Pipeline ───────────────────────────────────

    async def siphon_construct(self, campaign: Campaign, payload: SiphonConstructRequest) -> SiphonConstructResponse:
        city = self._city(campaign, payload.city_id)
        player = campaign.player_by_id(payload.player_id)
        if city.role_of(payload.player_id) != "Incumbent":
            raise PermissionError("You must be Incumbent in this city to commission a project here.")

        request = payload.construction.model_copy(update={"role": "Incumbent", "player_username": player.username})
        result = await city.sovereign.construct(request)

        gross = int(result.scam.parameters.get("siphoned_amount", 0))
        net = int(result.scam.parameters.get("remitted_amount", round(gross * (1 - LAUNDERING_FEE_PCT / 100))))
        fee = gross - net
        player.offshore_balance += net

        campaign.headlines.append(
            f"💰 {player.username} skimmed ₹{gross:,} off a {city.name} project — "
            f"₹{net:,} landed in their Private Offshore Account after ₹{fee:,} in laundering fees."
        )
        return SiphonConstructResponse(
            city_state=result.state,
            offshore_balance=player.offshore_balance,
            siphoned_gross=gross,
            laundering_fee=fee,
            siphoned_net=net,
            message=f"{request.name} built in {city.name}. Offshore balance now ₹{player.offshore_balance:,}.",
        )

    def fund_opposition(self, campaign: Campaign, player_id: str, target_city_id: str, amount: int) -> FundOppositionResponse:
        player = campaign.player_by_id(player_id)
        target = self._city(campaign, target_city_id)
        if target.role_of(player_id) != "Opposition":
            raise PermissionError("You can only fund an opposition campaign in a city where you ARE the Opposition.")
        if player.is_frozen():
            remaining = round(player.account_frozen_until - time.time())
            raise ValueError(f"Your offshore account was exposed and is frozen for {remaining} more second(s).")
        if amount > player.offshore_balance:
            raise ValueError(f"Not enough in your offshore account (have ₹{player.offshore_balance:,}).")

        player.offshore_balance -= amount
        multiplier = player.ip_multiplier()
        ip_granted = max(1, round(amount * FUND_OPPOSITION_IP_RATE * multiplier))
        target.sovereign.memory.influence_points += ip_granted

        unrest_bump = max(1, round((amount / 10_000) * FUND_OPPOSITION_UNREST_PER_10K))
        trust_drag = max(1, round((amount / 10_000) * FUND_OPPOSITION_TRUST_DRAG_PER_10K))
        target.sovereign.memory.city.worker_unrest = target.sovereign._clamp(
            target.sovereign.memory.city.worker_unrest + unrest_bump
        )
        target.sovereign.memory.city.public_trust = target.sovereign._clamp(
            target.sovereign.memory.city.public_trust - trust_drag
        )
        headline = (
            f"🕵️ Untraceable funds pour into {target.name}'s opposition — riots, strikes and a media "
            f"blitz worth ₹{amount:,} land overnight (+{ip_granted} Influence Points)."
        )
        target.sovereign.memory.headlines.append(headline)
        campaign.headlines.append(headline)

        return FundOppositionResponse(
            city_state=target.sovereign.state(),
            offshore_balance_remaining=player.offshore_balance,
            influence_points_granted=ip_granted,
            message=f"₹{amount:,} funneled from your offshore account into {target.name}.",
        )

    def expose_laundering(self, campaign: Campaign, exposer_player_id: str, source_city_id: str, audit_level: int) -> ExposeLaunderingResponse:
        source = self._city(campaign, source_city_id)
        if source.role_of(exposer_player_id) != "Opposition":
            raise PermissionError("Only the Opposition in this city can audit and expose its projects.")
        exposed_player_id = source.incumbent_player_id
        exposed_player = campaign.player_by_id(exposed_player_id)

        penalty = EXPOSE_TRUST_PENALTY + audit_level
        source.sovereign.memory.city.public_trust = source.sovereign._clamp(
            source.sovereign.memory.city.public_trust - penalty
        )
        source.sovereign.memory.city.corruption_leaks += 1

        exposed_player.account_traced = True
        exposed_player.account_frozen_until = time.time() + LAUNDER_TRACE_FREEZE_SECONDS
        # A frozen account can't fund anything further, so any city where the
        # exposed player is CURRENTLY Opposition sees its "funding" dry up —
        # simulated as an immediate Influence Point haircut there.
        dried_up: list[str] = []
        for city in campaign.cities.values():
            if city.city_id == source_city_id:
                continue
            if city.role_of(exposed_player_id) == "Opposition" and city.sovereign.memory.influence_points > 0:
                lost = round(city.sovereign.memory.influence_points * 0.5)
                city.sovereign.memory.influence_points = max(0, city.sovereign.memory.influence_points - lost)
                city.sovereign.memory.headlines.append(
                    f"💸 {exposed_player.username}'s offshore pipeline was just exposed in {source.name} — "
                    f"funding here dries up instantly (-{lost} Influence Points)."
                )
                dried_up.append(city.city_id)

        headline = (
            f"🚨 SCANDAL: {exposed_player.username}'s offshore laundering pipeline exposed in {source.name} "
            f"— public trust falls {penalty} points, offshore account frozen for {LAUNDER_TRACE_FREEZE_SECONDS // 60} min."
        )
        source.sovereign.memory.headlines.append(headline)
        campaign.headlines.append(headline)

        return ExposeLaunderingResponse(
            source_city_state=source.sovereign.state(),
            exposed_player_id=exposed_player_id,
            trust_penalty_applied=penalty,
            account_frozen=True,
            frozen_until=exposed_player.account_frozen_until,
            dried_up_cities=dried_up,
            message=headline,
        )

    # ── 2. Staggered Election Phases ─────────────────────────────────

    def run_city_election(self, campaign: Campaign, player_id: str, city_id: str) -> RunCityElectionResponse:
        city = self._city(campaign, city_id)
        if not city.voting_open:
            raise ValueError(f"{city.name} hasn't entered its election phase yet.")
        if city.election_completed:
            raise ValueError(f"{city.name} has already voted this campaign.")
        if city.role_of(player_id) != "Incumbent":
            raise PermissionError("Only the sitting Incumbent can call this city's election.")

        incumbent = campaign.player_by_id(city.incumbent_player_id)
        opposition = campaign.player_by_id(city.opposition_player_id)

        request = RunElectionRequest(
            role="Incumbent",
            force_early=True,
            incumbent_name=incumbent.username,
            opposition_name=opposition.username,
        )
        # Bonus base trust already baked into city stats by _apply_momentum,
        # so the underlying simulation just runs on current city_stats.
        result = city.sovereign.run_election(request)

        winner_player_id = incumbent.player_id if result.result.winner == incumbent.username else opposition.player_id
        winner = campaign.player_by_id(winner_player_id)
        city.election_completed = True
        city.winner_player_id = winner_player_id

        momentum_targets = self._apply_momentum(campaign, winner_player_id, city.phase)

        headline = f"🗳️ {city.name} (Phase {city.phase}) declares for {winner.username}!"
        campaign.headlines.append(headline)
        return RunCityElectionResponse(
            state=self.state(campaign),
            winner_player_id=winner_player_id,
            winner_username=winner.username,
            momentum_applied_to=momentum_targets,
            message=headline,
        )

    def _apply_momentum(self, campaign: Campaign, winner_player_id: str, from_phase: int) -> list[str]:
        """+10% base Trust Momentum Buff for the winner's races in the NEXT
        phase's cities — the National Wave effect."""
        targets: list[str] = []
        for city in campaign.cities.values():
            if city.phase != from_phase + 1:
                continue
            if city.role_of(winner_player_id) is None:
                continue
            buff = round(city.sovereign.memory.city.public_trust * 0.10)
            city.sovereign.memory.city.public_trust = city.sovereign._clamp(
                city.sovereign.memory.city.public_trust + buff
            )
            city.momentum_trust_buff += buff
            city.sovereign.memory.headlines.append(
                f"🌊 National Wave: momentum from the last result gives a +{buff} Trust bump here."
            )
            targets.append(city.city_id)
        return targets

    def advance_phase(self, campaign: Campaign) -> AdvancePhaseResponse:
        if campaign.current_phase >= len(campaign.phase_order):
            raise ValueError("Already in the final phase.")
        campaign.current_phase += 1
        newly_opened: list[str] = []
        for city in campaign.cities.values():
            if city.phase == campaign.current_phase:
                city.voting_open = True
                newly_opened.append(city.city_id)
        names = ", ".join(campaign.cities[cid].name for cid in newly_opened)
        message = f"📅 Phase {campaign.current_phase} has begun — polling opens in {names}."
        campaign.headlines.append(message)
        return AdvancePhaseResponse(state=self.state(campaign), newly_opened_cities=newly_opened, message=message)

    # ── 4. Asymmetric Retaliation ─────────────────────────────────────

    def retaliate(self, campaign: Campaign, actor_player_id: str, source_city_id: str) -> RetaliationResponse:
        source = self._city(campaign, source_city_id)
        if source.role_of(actor_player_id) != "Incumbent":
            raise PermissionError("You can only misuse state machinery in a city where you hold power.")
        target = campaign.opponent_of(actor_player_id)

        until = time.time() + RETALIATION_DEBUFF_SECONDS
        target.ip_debuff_multiplier = RETALIATION_IP_MULTIPLIER
        target.ip_debuff_until = until

        affected: list[str] = []
        for city in campaign.cities.values():
            if city.role_of(target.player_id) is None:
                continue
            before = city.sovereign.memory.influence_points
            after = round(before * RETALIATION_IP_MULTIPLIER)
            city.sovereign.memory.influence_points = after
            if before != after:
                city.sovereign.memory.headlines.append(
                    f"🚔 {target.username}'s allies rounded up under state machinery from {source.name} "
                    f"— Influence Points cut from {before} to {after} for {RETALIATION_DEBUFF_SECONDS // 60} min."
                )
            affected.append(city.city_id)

        headline = (
            f"🚔 {source.sovereign.memory.incumbent} orders 'Arrest Opposition Leaders' from {source.name} — "
            f"{target.username}'s Influence Points are slashed campaign-wide for "
            f"{RETALIATION_DEBUFF_SECONDS // 60} minutes."
        )
        source.sovereign.memory.headlines.append(headline)
        campaign.headlines.append(headline)

        return RetaliationResponse(
            source_city_state=source.sovereign.state(),
            target_player_id=target.player_id,
            debuff_multiplier=RETALIATION_IP_MULTIPLIER,
            debuff_seconds=RETALIATION_DEBUFF_SECONDS,
            message=headline,
        )


campaign_engine = CampaignEngine()
