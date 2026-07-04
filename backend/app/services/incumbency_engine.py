"""
Incumbency Wave Engine
======================
Calculates the macro-level Pro-Incumbency or Anti-Incumbency wave that
sweeps across all 24 counting rounds during an election.

Election-day timing (flavour + UI countdowns)
-----------------------------------------------
  - Polling day recurs every 3 in-game days (ELECTION_CYCLE_DAYS).
  - Vote counting is a live 2-hour window (COUNTING_DURATION_HOURS)
    split into 24 rounds (COUNTING_ROUNDS): rounds 1-6 are postal/rural
    ballots, 7-18 are urban centres, 19-24 are volatile swing zones.

Formula
-------
  I_f = (global_trust - 50) - (scams_exposed x 15) - (consecutive_terms x 5)

  Clamped to the range [-40, +40] so it never fully erases a candidate.

Impact on Counting Rounds
-------------------------
  incumbent_final   = candidate_match_score + I_f
  opposition_final  = candidate_match_score - (I_f x 0.5)

  Both scores are floored at 10 (hardcore loyalists never reach zero).

Seats
-----
  Once all 24 rounds are tallied, the popular vote is converted into an
  assembly seat map (default 101 seats, matching the reference hemicycle
  chart). A small independents/fringe bloc is always reserved so the
  chart never shows a 100% wipeout, then the remaining seats are split
  between Incumbent and Opposition by the largest-remainder method.
  `manifesto_trust_score` (from the ElectionEngine — manifesto practicality,
  rhetoric, city performance, and HuggingFace AI judging) nudges the swing
  a little further so campaign quality and real development delivery move
  seats, not just raw vote share.
"""

import random
from dataclasses import dataclass

from app.schemas.prajatantra import (
    IncumbencyWaveRequest,
    IncumbencyWaveResponse,
    CountingRoundResult,
    SeatResult,
    TenRoundSimulationRequest,
    TenRoundSimulationResponse,
)

ELECTION_CYCLE_DAYS = 3
COUNTING_DURATION_HOURS = 2
COUNTING_ROUNDS = 24

INDEPENDENT_SEAT_SHARE = 0.03  # small fringe/independent bloc, never contested
EMERGENCY_THRESHOLD_PCT = 80.0

INCUMBENT_COLOR = "#FF6B00"    # var(--pt-saffron)
OPPOSITION_COLOR = "#C0292A"   # var(--pt-red)
INDEPENDENT_COLOR = "#8A8070"  # var(--pt-muted)


# ---------------------------------------------------------------------------
# Core wave calculation
# ---------------------------------------------------------------------------

def calculate_incumbency_wave(
    global_trust: float,
    scams_exposed: int,
    consecutive_terms: int,
) -> float:
    """
    Returns the Incumbency Factor (I_f).
    Positive  → Pro-Incumbency wave (good governance pays off).
    Negative  → Anti-Incumbency wave (scams, fatigue, distrust).
    Clamped to [-40, +40].
    """
    trust_delta = global_trust - 50.0
    scandal_weight = scams_exposed * 15.0
    fatigue_weight = consecutive_terms * 5.0
    raw = trust_delta - scandal_weight - fatigue_weight
    return max(min(raw, 40.0), -40.0)


def wave_label(i_f: float) -> str:
    """Human-readable wave classification."""
    if i_f >= 20:
        return "Strong Pro-Incumbency Wave"
    if i_f >= 5:
        return "Mild Pro-Incumbency Wave"
    if i_f >= -5:
        return "Neutral / Swing"
    if i_f >= -20:
        return "Mild Anti-Incumbency Wave"
    return "Strong Anti-Incumbency Wave"


# ---------------------------------------------------------------------------
# Single round simulation
# ---------------------------------------------------------------------------

def simulate_voting_round(
    incumbent_match_score: float,
    opposition_match_score: float,
    incumbency_factor: float,
    round_number: int,
    total_electorate: int = 100_000,
) -> dict:
    """
    Executes a single counting-round factoring in the incumbency wave and
    per-booth jitter.  Returns a dict with vote counts and share breakdown.
    """
    # Apply wave to base scores
    adjusted_incumbent = incumbent_match_score + incumbency_factor
    adjusted_opposition = opposition_match_score - (incumbency_factor * 0.5)

    # Floor at 10 — hardcore loyalist base
    adjusted_incumbent = max(adjusted_incumbent, 10.0)
    adjusted_opposition = max(adjusted_opposition, 10.0)

    # Round-specific polling jitter (±15 %)
    jitter_inc = random.uniform(0.85, 1.15)
    jitter_opp = random.uniform(0.85, 1.15)

    incumbent_power = adjusted_incumbent * jitter_inc
    opposition_power = adjusted_opposition * jitter_opp
    total_power = incumbent_power + opposition_power

    incumbent_share = incumbent_power / total_power
    opposition_share = opposition_power / total_power

    round_votes = total_electorate // COUNTING_ROUNDS
    incumbent_votes = int(round_votes * incumbent_share)
    opposition_votes = round_votes - incumbent_votes

    return {
        "round": round_number,
        "incumbent_votes": incumbent_votes,
        "opposition_votes": opposition_votes,
        "incumbent_share": round(incumbent_share, 4),
        "opposition_share": round(opposition_share, 4),
        "jitter_inc": round(jitter_inc, 4),
        "jitter_opp": round(jitter_opp, 4),
    }


# ---------------------------------------------------------------------------
# Engine class
# ---------------------------------------------------------------------------

class IncumbencyEngine:
    """Stateless engine — all results are deterministic given the same seed."""

    def compute_wave(self, payload: IncumbencyWaveRequest) -> IncumbencyWaveResponse:
        i_f = calculate_incumbency_wave(
            global_trust=payload.global_trust,
            scams_exposed=payload.scams_exposed,
            consecutive_terms=payload.consecutive_terms,
        )
        return IncumbencyWaveResponse(
            incumbency_factor=round(i_f, 2),
            wave_label=wave_label(i_f),
            is_pro_incumbency=i_f > 0,
            trust_delta=round(payload.global_trust - 50.0, 2),
            scandal_drag=round(payload.scams_exposed * 15.0, 2),
            fatigue_drag=round(payload.consecutive_terms * 5.0, 2),
        )

    def simulate_ten_rounds(self, payload: TenRoundSimulationRequest) -> TenRoundSimulationResponse:
        i_f = calculate_incumbency_wave(
            global_trust=payload.global_trust,
            scams_exposed=payload.scams_exposed,
            consecutive_terms=payload.consecutive_terms,
        )

        # Manifesto/rhetoric/city-performance/AI-judged trust nudges the wave a
        # little further, so campaign quality and development delivery move
        # seats on top of raw popular-vote share.
        if payload.manifesto_trust_score is not None:
            i_f += (payload.manifesto_trust_score - 50.0) * 0.15
            i_f = max(min(i_f, 40.0), -40.0)

        rounds: list[CountingRoundResult] = []
        inc_total = 0
        opp_total = 0

        for r in range(1, COUNTING_ROUNDS + 1):
            result = simulate_voting_round(
                incumbent_match_score=payload.incumbent_match_score,
                opposition_match_score=payload.opposition_match_score,
                incumbency_factor=i_f,
                round_number=r,
                total_electorate=payload.total_electorate,
            )
            rounds.append(
                CountingRoundResult(
                    round=r,
                    incumbent_votes=result["incumbent_votes"],
                    opposition_votes=result["opposition_votes"],
                    incumbent_share=result["incumbent_share"],
                    opposition_share=result["opposition_share"],
                    running_incumbent_total=inc_total + result["incumbent_votes"],
                    running_opposition_total=opp_total + result["opposition_votes"],
                )
            )
            inc_total += result["incumbent_votes"]
            opp_total += result["opposition_votes"]

        winner = (
            payload.incumbent_name
            if inc_total >= opp_total
            else payload.opposition_name
        )
        margin = abs(inc_total - opp_total)
        margin_pct = round(margin / max(1, inc_total + opp_total) * 100, 2)

        inc_seats, opp_seats, ind_seats = allocate_seats(
            incumbent_votes=inc_total,
            opposition_votes=opp_total,
            total_seats=payload.total_seats,
        )
        seats = [
            SeatResult(
                party=payload.incumbent_name,
                role="Incumbent",
                seats=inc_seats,
                color=INCUMBENT_COLOR,
                seat_share_pct=round(inc_seats / payload.total_seats * 100, 2),
            ),
            SeatResult(
                party=payload.opposition_name,
                role="Opposition",
                seats=opp_seats,
                color=OPPOSITION_COLOR,
                seat_share_pct=round(opp_seats / payload.total_seats * 100, 2),
            ),
            SeatResult(
                party="Independents",
                role="Independent",
                seats=ind_seats,
                color=INDEPENDENT_COLOR,
                seat_share_pct=round(ind_seats / payload.total_seats * 100, 2),
            ),
        ]

        leading_seats = max(inc_seats, opp_seats)
        leading_share_pct = round(leading_seats / payload.total_seats * 100, 2)
        emergency_eligible = leading_share_pct > EMERGENCY_THRESHOLD_PCT and leading_seats == inc_seats
        emergency_message = (
            (
                f"{payload.incumbent_name} crossed a {leading_share_pct}% supermajority "
                f"({inc_seats}/{payload.total_seats} seats). Emergency powers can now be "
                "declared — Industrial construction would bypass Residential zoning citywide."
            )
            if emergency_eligible
            else None
        )

        return TenRoundSimulationResponse(
            incumbency_factor=round(i_f, 2),
            wave_label=wave_label(i_f),
            rounds=rounds,
            final_incumbent_votes=inc_total,
            final_opposition_votes=opp_total,
            winner=winner,
            margin=margin,
            margin_pct=margin_pct,
            incumbent_name=payload.incumbent_name,
            opposition_name=payload.opposition_name,
            election_cycle_days=ELECTION_CYCLE_DAYS,
            counting_duration_hours=COUNTING_DURATION_HOURS,
            total_rounds=COUNTING_ROUNDS,
            total_seats=payload.total_seats,
            incumbent_seats=inc_seats,
            opposition_seats=opp_seats,
            independent_seats=ind_seats,
            seats=seats,
            emergency_eligible=emergency_eligible,
            emergency_threshold_pct=EMERGENCY_THRESHOLD_PCT,
            emergency_message=emergency_message,
        )


def allocate_seats(
    incumbent_votes: int,
    opposition_votes: int,
    total_seats: int,
) -> tuple[int, int, int]:
    """
    Converts the popular vote into a seat map using the largest-remainder
    method. A small independents/fringe bloc (~3%, minimum 1 seat) is
    reserved first so the hemicycle chart always shows a sliver of grey,
    then the remaining contested seats are split between Incumbent and
    Opposition proportional to their vote share.
    """
    independent_seats = max(1, round(total_seats * INDEPENDENT_SEAT_SHARE))
    independent_seats = min(independent_seats, total_seats - 2) if total_seats >= 3 else 0
    contested_seats = total_seats - independent_seats

    total_votes = max(1, incumbent_votes + opposition_votes)
    inc_exact = contested_seats * incumbent_votes / total_votes
    opp_exact = contested_seats * opposition_votes / total_votes

    inc_seats = int(inc_exact)
    opp_seats = int(opp_exact)
    remainder = contested_seats - inc_seats - opp_seats

    if remainder > 0:
        if (inc_exact - inc_seats) >= (opp_exact - opp_seats):
            inc_seats += remainder
        else:
            opp_seats += remainder

    return inc_seats, opp_seats, independent_seats


incumbency_engine = IncumbencyEngine()