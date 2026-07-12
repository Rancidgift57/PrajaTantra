"""
CoalitionEngine + CoalitionRegistry — "The Coalition Era" (5-player mode).

Mirrors match_registry.py's philosophy (in-memory, dataclass-backed, one
instance owns every live 5-seat match) but layers on the coalition-politics
mechanics from the design doc: no player starts with a majority, a 5-minute
negotiation window forms a Ruling Coalition vs an Opposition Bloc, the CM
allocates ministries and decides how much black money to cut partners in on,
any player can call a Floor Test once an hour, and a betrayed partner can
withdraw support to collapse the government instantly. The game closes with
a round-by-round (24-round / 1hr) final election where War Chests buy seats.

Completely additive: does not import or mutate match_registry.py,
sovereign_engine.py, or anything from the 2-player game.
"""
from __future__ import annotations

import random
import secrets
import string
import time
from dataclasses import dataclass, field

from app.schemas.coalition import (
    MAGIC_NUMBER,
    TOTAL_SEATS,
    CoalitionMatchInfo,
    CoalitionProposal,
    CoalitionSeatInfo,
    CoalitionStatus,
    FloorTestState,
    Ministry,
)
from app.schemas.prajatantra import CountingRoundResult, Ideology, SeatResult, TenRoundSimulationResponse

IDEOLOGIES: list[Ideology] = ["Industrialist", "Green", "Socialist", "Nationalist", "Technocrat"]

NEGOTIATION_WINDOW_SECONDS = 5 * 60
FLOOR_TEST_COOLDOWN_SECONDS = 60 * 60          # "once every real-time hour"
FLOOR_TEST_VOTE_WINDOW_SECONDS = 90
ELECTION_TOTAL_ROUNDS = 24
ELECTION_BATCH_SIZE = 4                        # revealed together
ELECTION_BATCH_INTERVAL_SECONDS = 10 * 60      # every 10 real-time minutes
ELECTION_DURATION_SECONDS = (ELECTION_TOTAL_ROUNDS // ELECTION_BATCH_SIZE) * ELECTION_BATCH_INTERVAL_SECONDS  # 1hr
STARTING_TREASURY = 15_000_000


def _new_id(n: int = 8) -> str:
    return secrets.token_hex(n)


def _new_join_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _random_seat_split(n_players: int = 5, total: int = TOTAL_SEATS) -> list[int]:
    """Random seats per player, each >=1, summing to `total`, nobody >=51
    alone (re-rolls the rare case where one party would already have a
    majority, since the whole game hinges on nobody starting with 51+)."""
    for _ in range(200):
        cuts = sorted(random.sample(range(1, total), n_players - 1))
        parts = [cuts[0]] + [cuts[i] - cuts[i - 1] for i in range(1, len(cuts))] + [total - cuts[-1]]
        if all(p >= 1 for p in parts) and max(parts) < MAGIC_NUMBER:
            random.shuffle(parts)
            return parts
    # Fallback: deterministic split resembling the example in the design doc.
    return sorted([30, 25, 20, 15, 11], reverse=True)


@dataclass
class CoalitionSeat:
    player_id: str
    username: str
    ideology: Ideology
    party_seats: int
    role: str | None = None
    ministry: Ministry | None = None
    war_chest: int = 0
    public_image_score: int = 50
    connected: bool = False


@dataclass
class CoalitionMatch:
    id: str = field(default_factory=lambda: _new_id())
    join_code: str = field(default_factory=_new_join_code)
    status: CoalitionStatus = "waiting"
    seats: dict[str, CoalitionSeat] = field(default_factory=dict)  # player_id -> seat
    seat_order: list[str] = field(default_factory=list)
    government_ids: list[str] = field(default_factory=list)
    opposition_ids: list[str] = field(default_factory=list)
    cm_id: str | None = None
    lop_id: str | None = None
    siphon_percentage: int = 0
    treasury: int = STARTING_TREASURY
    pending_proposals: dict[str, CoalitionProposal] = field(default_factory=dict)
    floor_test: FloorTestState = field(default_factory=FloorTestState)
    negotiation_deadline: float | None = None
    floor_test_cooldown_until: float = 0.0
    election_started_at: float | None = None
    election_result: TenRoundSimulationResponse | None = None
    election_seats_by_player: dict[str, int] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    tick_task: object | None = field(default=None, repr=False, compare=False)
    created_at: str = field(default_factory=lambda: str(time.time()))

    def _log(self, message: str) -> None:
        self.log.append(message)
        self.log = self.log[-40:]

    def seat_for(self, player_id: str) -> CoalitionSeat | None:
        return self.seats.get(player_id)


class CoalitionEngine:
    """Stateless game-rule logic operating on a CoalitionMatch instance."""

    # ── Seating / setup ────────────────────────────────────────────────
    def add_player(self, match: CoalitionMatch, player_id: str, username: str) -> None:
        if player_id in match.seats or len(match.seats) >= 5:
            return
        match.seats[player_id] = CoalitionSeat(
            player_id=player_id, username=username, ideology="Industrialist", party_seats=0,
        )
        match.seat_order.append(player_id)
        if len(match.seats) == 5:
            self._start_negotiation(match)

    def _start_negotiation(self, match: CoalitionMatch) -> None:
        seat_counts = _random_seat_split(5)
        for player_id, seats, ideology in zip(match.seat_order, seat_counts, random.sample(IDEOLOGIES, 5)):
            seat = match.seats[player_id]
            seat.party_seats = seats
            seat.ideology = ideology
        match.status = "negotiating"
        match.negotiation_deadline = time.time() + NEGOTIATION_WINDOW_SECONDS
        largest = max(match.seat_order, key=lambda pid: match.seats[pid].party_seats)
        match._log(
            f"Assembly formed: 101 seats declared. {match.seats[largest].username} "
            f"({match.seats[largest].ideology}) leads with {match.seats[largest].party_seats} seats. "
            f"51 needed to govern — 5 minute negotiation window is open."
        )

    # ── Coalition negotiation ──────────────────────────────────────────
    def propose_coalition(self, match: CoalitionMatch, proposer_id: str, partner_ids: list[str]) -> CoalitionProposal:
        self._require_status(match, ["negotiating", "governing", "floor_test"])
        partner_ids = [pid for pid in partner_ids if pid != proposer_id and pid in match.seats]
        proposal = CoalitionProposal(
            proposal_id=_new_id(4), proposer_id=proposer_id, partner_ids=partner_ids,
            accepted_by=[proposer_id], created_at=time.time(),
        )
        match.pending_proposals[proposal.proposal_id] = proposal
        names = ", ".join(match.seats[pid].username for pid in partner_ids)
        match._log(f"{match.seats[proposer_id].username} proposed a coalition with {names}.")
        return proposal

    def respond_to_proposal(self, match: CoalitionMatch, player_id: str, proposal_id: str, accept: bool) -> None:
        proposal = match.pending_proposals.get(proposal_id)
        if not proposal or player_id not in proposal.partner_ids:
            raise ValueError("No such pending coalition proposal for you.")
        if not accept:
            del match.pending_proposals[proposal_id]
            match._log(f"{match.seats[player_id].username} rejected the coalition offer.")
            return
        if player_id not in proposal.accepted_by:
            proposal.accepted_by.append(player_id)
        all_members = set([proposal.proposer_id, *proposal.partner_ids])
        if all_members.issubset(set(proposal.accepted_by)):
            self._form_government(match, list(all_members))
            # _form_government() already clears every pending proposal
            # (a fresh government invalidates any other offers in flight).

    def _form_government(self, match: CoalitionMatch, member_ids: list[str]) -> None:
        seat_total = sum(match.seats[pid].party_seats for pid in member_ids)
        if seat_total < MAGIC_NUMBER:
            match._log("Coalition formed but falls short of the Magic Number (51) — no government yet.")
            return
        # Reset all roles first (a re-negotiation after a collapse).
        for seat in match.seats.values():
            seat.role = None
            seat.ministry = None
        match.government_ids = sorted(member_ids, key=lambda pid: -match.seats[pid].party_seats)
        match.opposition_ids = [pid for pid in match.seat_order if pid not in member_ids]
        cm_id = match.government_ids[0]
        match.cm_id = cm_id
        match.seats[cm_id].role = "CM"
        for i, pid in enumerate(match.government_ids[1:]):
            match.seats[pid].role = "Deputy CM" if i == 0 else "Minister"
        if match.opposition_ids:
            lop_id = max(match.opposition_ids, key=lambda pid: match.seats[pid].party_seats)
            match.lop_id = lop_id
            for pid in match.opposition_ids:
                match.seats[pid].role = "Leader of Opposition" if pid == lop_id else (
                    "Fringe" if match.seats[pid].party_seats <= 12 else "Opposition"
                )
        else:
            match.lop_id = None
        match.status = "governing"
        match.negotiation_deadline = None
        match.pending_proposals.clear()
        match._log(
            f"🏛️ Government formed! {match.seats[cm_id].username} is CM with "
            f"{seat_total}/{TOTAL_SEATS} seats. {match.seats[cm_id].username}'s coalition: "
            + ", ".join(match.seats[pid].username for pid in match.government_ids)
        )

    def government_seat_total(self, match: CoalitionMatch) -> int:
        return sum(match.seats[pid].party_seats for pid in match.government_ids)

    # ── Ministries ──────────────────────────────────────────────────────
    def allocate_ministry(self, match: CoalitionMatch, cm_id: str, minister_id: str, ministry: Ministry) -> None:
        self._require_status(match, ["governing", "floor_test"])
        if cm_id != match.cm_id:
            raise PermissionError("Only the Chief Minister can allocate ministries.")
        if minister_id not in match.government_ids or minister_id == cm_id:
            raise ValueError("Ministries can only go to a coalition partner, not the CM themself.")
        for seat in match.seats.values():
            if seat.ministry == ministry:
                seat.ministry = None
        match.seats[minister_id].ministry = ministry
        match._log(f"{match.seats[cm_id].username} handed the {ministry} portfolio to {match.seats[minister_id].username}.")

    # ── Corruption: the CM siphons, then decides who gets cut in ────────
    def siphon_funds(self, match: CoalitionMatch, cm_id: str, amount: int, cuts: dict[str, float]) -> dict[str, int]:
        self._require_status(match, ["governing", "floor_test"])
        if cm_id != match.cm_id:
            raise PermissionError("Only the CM controls the treasury siphon.")
        amount = min(amount, match.treasury)
        match.treasury -= amount
        payouts: dict[str, int] = {}
        remaining = amount
        for partner_id, fraction in cuts.items():
            if partner_id not in match.government_ids or partner_id == cm_id:
                continue
            fraction = max(0.0, min(1.0, fraction))
            cut = round(amount * fraction)
            cut = min(cut, remaining)
            match.seats[partner_id].war_chest += cut
            payouts[partner_id] = cut
            remaining -= cut
        match.seats[cm_id].war_chest += remaining
        payouts[cm_id] = remaining
        # Uncut partners get angry — small public-image / trust penalty risk
        # they can act on later (withdraw support / leak to Opposition).
        uncut = [pid for pid in match.government_ids if pid != cm_id and payouts.get(pid, 0) == 0]
        if uncut:
            names = ", ".join(match.seats[pid].username for pid in uncut)
            match._log(f"⚠️ {match.seats[cm_id].username} siphoned ₹{amount:,} and cut {names} out entirely.")
        else:
            match._log(f"💰 {match.seats[cm_id].username} siphoned ₹{amount:,} and shared cuts across the coalition.")
        return payouts

    # ── Floor test / no-confidence ───────────────────────────────────────
    def trigger_floor_test(self, match: CoalitionMatch, initiator_id: str) -> None:
        self._require_status(match, ["governing"])
        now = time.time()
        if now < match.floor_test_cooldown_until:
            wait = int(match.floor_test_cooldown_until - now)
            raise ValueError(f"A Floor Test was already called recently — try again in {wait}s.")
        match.status = "floor_test"
        match.floor_test = FloorTestState(
            active=True, triggered_by=initiator_id, deadline=now + FLOOR_TEST_VOTE_WINDOW_SECONDS,
        )
        match.floor_test_cooldown_until = now + FLOOR_TEST_COOLDOWN_SECONDS
        match._log(f"🚨 {match.seats[initiator_id].username} called a No-Confidence Motion! Floor Test is live.")

    def cast_floor_vote(self, match: CoalitionMatch, player_id: str, vote: str) -> None:
        if not match.floor_test.active:
            raise ValueError("No Floor Test is currently active.")
        match.floor_test.votes[player_id] = vote  # type: ignore[assignment]
        if len(match.floor_test.votes) >= len(match.seats):
            self._resolve_floor_test(match)

    def maybe_timeout_floor_test(self, match: CoalitionMatch) -> None:
        ft = match.floor_test
        if ft.active and ft.deadline is not None and time.time() >= ft.deadline:
            self._resolve_floor_test(match)

    def _resolve_floor_test(self, match: CoalitionMatch) -> None:
        ft = match.floor_test
        # Non-voters (didn't respond in time) default to backing their own bloc.
        for pid in match.seat_order:
            if pid not in ft.votes:
                ft.votes[pid] = "confidence" if pid in match.government_ids else "no_confidence"
        confidence_seats = sum(
            match.seats[pid].party_seats for pid, v in ft.votes.items() if v == "confidence"
        )
        ft.active = False
        ft.last_resolved_at = time.time()
        if confidence_seats >= MAGIC_NUMBER:
            match.status = "governing"
            match._log(f"✅ Government survives the Floor Test — {confidence_seats}/{TOTAL_SEATS} confidence votes.")
            match.floor_test = FloorTestState(last_resolved_at=ft.last_resolved_at)
        else:
            match._log(f"💥 Government FALLS — only {confidence_seats}/{TOTAL_SEATS} confidence votes secured.")
            self._collapse_government(match)

    def withdraw_support(self, match: CoalitionMatch, player_id: str) -> None:
        self._require_status(match, ["governing", "floor_test"])
        if player_id not in match.government_ids or player_id == match.cm_id:
            raise ValueError("Only a coalition partner (not the CM) can withdraw support.")
        match._log(f"🗡️ {match.seats[player_id].username} withdrew support from the coalition — betrayal!")
        match.government_ids.remove(player_id)
        if self.government_seat_total(match) < MAGIC_NUMBER:
            self._collapse_government(match)
        else:
            match.opposition_ids.append(player_id)
            match.seats[player_id].role = "Opposition"
            match.seats[player_id].ministry = None

    def _collapse_government(self, match: CoalitionMatch) -> None:
        match._log("🏛️💔 The government has collapsed. Treasury frozen. New negotiation window opens.")
        match.cm_id = None
        match.lop_id = None
        match.government_ids = []
        match.opposition_ids = []
        for seat in match.seats.values():
            seat.role = None
            seat.ministry = None
        match.status = "negotiating"
        match.negotiation_deadline = time.time() + NEGOTIATION_WINDOW_SECONDS
        match.pending_proposals.clear()
        match.floor_test = FloorTestState()

    def maybe_timeout_negotiation(self, match: CoalitionMatch) -> None:
        if match.status == "negotiating" and match.negotiation_deadline and time.time() >= match.negotiation_deadline:
            # Nobody managed to form 51 in time — auto-refresh the window
            # rather than soft-locking the match.
            match.negotiation_deadline = time.time() + NEGOTIATION_WINDOW_SECONDS
            match._log("⏰ Negotiation window expired with no government formed — window reopened.")

    # ── Final election: round-by-round reveal over 1hr (24 rounds) ──────
    def start_election(self, match: CoalitionMatch) -> None:
        match.election_started_at = time.time()
        match.status = "election"
        total_image = sum(s.public_image_score for s in match.seats.values()) or 1
        total_chest = sum(s.war_chest for s in match.seats.values()) or 1
        base_shares = {}
        for pid, seat in match.seats.items():
            # Base pull: original party seats + public image; War Chest buys
            # extra vote-multipliers in wards on top, per the design doc.
            base = seat.party_seats * 0.55 + (seat.public_image_score / total_image) * TOTAL_SEATS * 0.20
            chest_bonus = (seat.war_chest / total_chest) * TOTAL_SEATS * 0.25
            base_shares[pid] = max(1.0, base + chest_bonus)
        scale = TOTAL_SEATS / sum(base_shares.values())
        final_seats = {pid: max(0, round(share * scale)) for pid, share in base_shares.items()}
        # Reconcile rounding drift onto the largest party so totals hit 101.
        drift = TOTAL_SEATS - sum(final_seats.values())
        if drift != 0:
            top = max(final_seats, key=lambda pid: final_seats[pid])
            final_seats[top] += drift
        match.election_seats_by_player = final_seats

        winner_id = max(final_seats, key=lambda pid: final_seats[pid])
        anchor_id = match.cm_id or winner_id
        anchor_final_votes = final_seats.get(anchor_id, 0) * 1000
        rest_final_votes = sum(v for pid, v in final_seats.items() if pid != anchor_id) * 1000
        rounds: list[CountingRoundResult] = []
        prev_inc, prev_opp = 0, 0
        for r in range(1, ELECTION_TOTAL_ROUNDS + 1):
            running_inc = round(anchor_final_votes * r / ELECTION_TOTAL_ROUNDS)
            running_opp = round(rest_final_votes * r / ELECTION_TOTAL_ROUNDS)
            total_r = max(1, running_inc - prev_inc + running_opp - prev_opp)
            rounds.append(CountingRoundResult(
                round=r,
                incumbent_votes=running_inc - prev_inc,
                opposition_votes=running_opp - prev_opp,
                incumbent_share=round((running_inc - prev_inc) / total_r, 3),
                opposition_share=round((running_opp - prev_opp) / total_r, 3),
                running_incumbent_total=running_inc,
                running_opposition_total=running_opp,
            ))
            prev_inc, prev_opp = running_inc, running_opp
        margin = abs(anchor_final_votes - rest_final_votes)
        margin_pct = round(margin / max(1, anchor_final_votes + rest_final_votes) * 100, 1)

        colors = ["#FF9933", "#138808", "#0F52BA", "#B8860B", "#8B0000"]
        seat_blocs = [
            SeatResult(
                party=match.seats[pid].username,
                role="Incumbent" if pid == anchor_id else "Opposition",
                seats=count,
                color=colors[i % len(colors)],
                seat_share_pct=round(count / TOTAL_SEATS * 100, 1),
            )
            for i, (pid, count) in enumerate(final_seats.items())
        ]

        match.election_result = TenRoundSimulationResponse(
            incumbency_factor=0.0,
            wave_label="Coalition Verdict",
            rounds=rounds,
            final_incumbent_votes=anchor_final_votes,
            final_opposition_votes=rest_final_votes,
            winner=match.seats[winner_id].username,
            margin=margin,
            margin_pct=margin_pct,
            incumbent_name=match.seats[anchor_id].username,
            opposition_name="Opposition Bloc",
            election_cycle_days=0,
            counting_duration_hours=1,
            total_rounds=ELECTION_TOTAL_ROUNDS,
            total_seats=TOTAL_SEATS,
            incumbent_seats=final_seats.get(anchor_id, 0),
            opposition_seats=sum(v for pid, v in final_seats.items() if pid != anchor_id),
            independent_seats=0,
            seats=seat_blocs,
        )
        match._log(
            f"🗳️ 2029 Election called! Counting runs 1hr in 24 rounds "
            f"(4 rounds revealed every 10 minutes). War Chests are buying ward multipliers now."
        )

    def election_reveal_state(self, match: CoalitionMatch) -> dict:
        """How many of the 24 rounds/seats should be visible to clients right
        now, purely as a function of elapsed real time — keeps every viewer's
        client in sync without a server push per tick."""
        if not match.election_started_at:
            return {"rounds_revealed": 0, "batches_revealed": 0, "complete": False}
        elapsed = time.time() - match.election_started_at
        batches_revealed = min(
            ELECTION_TOTAL_ROUNDS // ELECTION_BATCH_SIZE,
            int(elapsed // ELECTION_BATCH_INTERVAL_SECONDS) + 1,
        )
        rounds_revealed = min(ELECTION_TOTAL_ROUNDS, batches_revealed * ELECTION_BATCH_SIZE)
        complete = elapsed >= ELECTION_DURATION_SECONDS
        if complete:
            rounds_revealed = ELECTION_TOTAL_ROUNDS
        return {"rounds_revealed": rounds_revealed, "batches_revealed": batches_revealed, "complete": complete}

    # ── Helpers ───────────────────────────────────────────────────────
    def _require_status(self, match: CoalitionMatch, allowed: list[str]) -> None:
        if match.status not in allowed:
            raise ValueError(f"Not allowed in match status '{match.status}'.")

    def to_info(self, match: CoalitionMatch, viewer_player_id: str | None = None) -> CoalitionMatchInfo:
        self.maybe_timeout_negotiation(match)
        self.maybe_timeout_floor_test(match)
        seats = [
            CoalitionSeatInfo(
                player_id=s.player_id, username=s.username, ideology=s.ideology,
                party_seats=s.party_seats, role=s.role, ministry=s.ministry,
                war_chest=s.war_chest, public_image_score=s.public_image_score,
                in_government=s.player_id in match.government_ids, connected=s.connected,
            )
            for s in (match.seats[pid] for pid in match.seat_order)
        ]
        return CoalitionMatchInfo(
            match_id=match.id, join_code=match.join_code, status=match.status, seats=seats,
            government_player_ids=match.government_ids, opposition_player_ids=match.opposition_ids,
            government_seat_total=self.government_seat_total(match), cm_player_id=match.cm_id,
            lop_player_id=match.lop_id, siphon_percentage=match.siphon_percentage, treasury=match.treasury,
            pending_proposals=list(match.pending_proposals.values()), floor_test=match.floor_test,
            negotiation_deadline=match.negotiation_deadline, floor_test_cooldown_until=match.floor_test_cooldown_until,
            election_started_at=match.election_started_at, election_result=match.election_result,
            election_seats_by_player=match.election_seats_by_player, your_player_id=viewer_player_id,
            log=match.log,
        )


class CoalitionRegistry:
    def __init__(self) -> None:
        self._matches: dict[str, CoalitionMatch] = {}
        self._by_join_code: dict[str, str] = {}

    def create_match(self, host_player_id: str, host_username: str) -> CoalitionMatch:
        match = CoalitionMatch()
        engine.add_player(match, host_player_id, host_username)
        self._matches[match.id] = match
        self._by_join_code[match.join_code] = match.id
        return match

    def join_match(self, join_code: str, player_id: str, username: str) -> CoalitionMatch:
        match_id = self._by_join_code.get(join_code.strip().upper())
        if not match_id or match_id not in self._matches:
            raise ValueError("No 5-player match found with that join code.")
        match = self._matches[match_id]
        if player_id in match.seats:
            return match
        if len(match.seats) >= 5:
            raise ValueError("This coalition match already has 5 players.")
        engine.add_player(match, player_id, username)
        return match

    def get_match(self, match_id: str) -> CoalitionMatch:
        match = self._matches.get(match_id)
        if not match:
            raise ValueError("Coalition match not found.")
        return match

    def require_seat(self, match_id: str, player_id: str) -> CoalitionMatch:
        match = self.get_match(match_id)
        if player_id not in match.seats:
            raise PermissionError("You are not seated in this coalition match.")
        return match


engine = CoalitionEngine()
coalition_registry = CoalitionRegistry()
