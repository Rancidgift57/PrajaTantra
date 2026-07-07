"""
Seat Projection Engine — the "Live Exit Poll"
==============================================
Continuously recalculates a projected 101-seat hemicycle split from the
CURRENT city/ward stats. This is deliberately NOT an election result — it's
a live-fluctuating forecast recalculated every time SovereignState is
rebuilt (i.e. after every action, or on the periodic match tick), so
players watch it move in near-real-time as they play.

Ward model
----------
The 8x8 City Map grid is split into 4 quadrants:

    cols 0-3      cols 4-7
    ┌───────────┬───────────┐
    │   North   │   East    │  rows 0-3
    ├───────────┼───────────┤
    │   West    │   South   │  rows 4-7
    └───────────┴───────────┘

Each ward gets SEATS_PER_WARD (25) seats. Buildings placed on the City Map
carry a `ward` tag; a building's pollution/unrest/trust impact is
attributed to whichever ward it physically sits in. Buildings with no ward
(built via the non-grid Sarkari Yojana panel, or legacy blocks from before
this feature) don't skew any single ward — they only count toward the
city-wide baseline every ward starts from.

4 wards x 25 seats = 100, plus 1 fixed national Independent seat = 101,
matching the reference 101-seat hemicycle.
"""

from app.schemas.prajatantra import (
    CityStats,
    InfrastructureBlock,
    SeatProjection,
    SeatResult,
    Ward,
    WardProjection,
)

WARDS: list[Ward] = ["North", "East", "South", "West"]
SEATS_PER_WARD = 25
NATIONAL_INDEPENDENT_SEATS = 1  # rounds 4x25=100 up to 101
WARD_INDEPENDENT_SHARE = 0.04   # ~1 seat per ward reserved as local independents

INCUMBENT_COLOR = "#FF6B00"    # var(--pt-saffron)
OPPOSITION_COLOR = "#C0292A"   # var(--pt-red)
INDEPENDENT_COLOR = "#8A8070"  # var(--pt-muted)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _incumbent_share(trust: float, unrest: float, pollution: float, corruption_leaks: int) -> float:
    """Base share purely from live stats — no manifesto, no campaign, no
    incumbency wave. That's what makes this a *projection*, not a result."""
    share = trust / 100.0
    share -= min(unrest / 100.0 * 0.25, 0.25)
    share -= min(pollution / 100.0 * 0.20, 0.20)
    share -= min(corruption_leaks * 0.04, 0.20)
    return _clamp(share, 0.04, 0.96)


def _allocate(total_seats: int, incumbent_share: float, independent_share: float) -> tuple[int, int, int]:
    """Largest-remainder seat allocation, same method used by the official
    post-election counting engine, so the two systems feel consistent."""
    independent_seats = max(1, round(total_seats * independent_share))
    independent_seats = min(independent_seats, total_seats - 2) if total_seats >= 3 else 0
    contested = total_seats - independent_seats

    inc_exact = contested * incumbent_share
    opp_exact = contested - inc_exact
    inc_seats = int(inc_exact)
    opp_seats = int(opp_exact)
    remainder = contested - inc_seats - opp_seats
    if remainder > 0:
        if (inc_exact - inc_seats) >= (opp_exact - opp_seats):
            inc_seats += remainder
        else:
            opp_seats += remainder
    return inc_seats, opp_seats, independent_seats


def _ward_stat_deltas(blocks: list[InfrastructureBlock]) -> dict[Ward, dict[str, float]]:
    """
    Distributes the city's CURRENT pollution/unrest/trust-harm proportionally
    across wards, based on which ward's buildings actually caused how much
    of it. A ward with no ward-tagged buildings gets an even 1/4 share
    (i.e. tracks the city average) — concentration only shows up once
    buildings are actually clustered in one ward.
    """
    contrib: dict[Ward, dict[str, float]] = {w: {"pollution": 0.0, "unrest": 0.0, "harm": 0.0} for w in WARDS}
    totals = {"pollution": 0.0, "unrest": 0.0, "harm": 0.0}

    for block in blocks:
        if block.ward is None:
            continue
        pollution = max(0, block.pollution_delta)
        unrest = max(0, block.unrest_delta)
        harm = max(0, -block.trust_delta)  # negative trust_delta = damage
        contrib[block.ward]["pollution"] += pollution
        contrib[block.ward]["unrest"] += unrest
        contrib[block.ward]["harm"] += harm
        totals["pollution"] += pollution
        totals["unrest"] += unrest
        totals["harm"] += harm

    shares: dict[Ward, dict[str, float]] = {}
    for w in WARDS:
        shares[w] = {
            "pollution": (contrib[w]["pollution"] / totals["pollution"]) if totals["pollution"] > 0 else 0.25,
            "unrest": (contrib[w]["unrest"] / totals["unrest"]) if totals["unrest"] > 0 else 0.25,
            "harm": (contrib[w]["harm"] / totals["harm"]) if totals["harm"] > 0 else 0.25,
        }
    return shares


def project_seats(
    city: CityStats,
    blocks: list[InfrastructureBlock],
    incumbent_name: str,
    opposition_name: str,
) -> SeatProjection:
    shares = _ward_stat_deltas(blocks)
    ward_projections: list[WardProjection] = []
    total_inc = total_opp = total_ind = 0

    for w in WARDS:
        # Scale by len(WARDS) so an even distribution reproduces the exact
        # city-wide average, while concentration in one ward spikes that
        # ward well above (and depresses the others well below) it.
        ward_pollution = _clamp(city.pollution * shares[w]["pollution"] * len(WARDS))
        ward_unrest = _clamp(city.worker_unrest * shares[w]["unrest"] * len(WARDS))
        harm_skew = (shares[w]["harm"] * len(WARDS) - 1.0) * 10.0  # +/- trust nudge
        ward_trust = _clamp(city.public_trust - harm_skew)

        inc_share = _incumbent_share(ward_trust, ward_unrest, ward_pollution, city.corruption_leaks)
        inc_seats, opp_seats, ind_seats = _allocate(SEATS_PER_WARD, inc_share, WARD_INDEPENDENT_SHARE)

        ward_projections.append(
            WardProjection(
                ward=w,
                public_trust=round(ward_trust),
                pollution=round(ward_pollution),
                worker_unrest=round(ward_unrest),
                incumbent_seats=inc_seats,
                opposition_seats=opp_seats,
                independent_seats=ind_seats,
                seats_total=SEATS_PER_WARD,
            )
        )
        total_inc += inc_seats
        total_opp += opp_seats
        total_ind += ind_seats

    # +1 fixed national independent seat rounds 100 -> 101.
    total_ind += NATIONAL_INDEPENDENT_SEATS
    total_seats = total_inc + total_opp + total_ind

    seats = [
        SeatResult(
            party=incumbent_name, role="Incumbent", seats=total_inc, color=INCUMBENT_COLOR,
            seat_share_pct=round(total_inc / total_seats * 100, 2),
        ),
        SeatResult(
            party=opposition_name, role="Opposition", seats=total_opp, color=OPPOSITION_COLOR,
            seat_share_pct=round(total_opp / total_seats * 100, 2),
        ),
        SeatResult(
            party="Independents", role="Independent", seats=total_ind, color=INDEPENDENT_COLOR,
            seat_share_pct=round(total_ind / total_seats * 100, 2),
        ),
    ]

    return SeatProjection(
        total_seats=total_seats,
        incumbent_seats=total_inc,
        opposition_seats=total_opp,
        independent_seats=total_ind,
        seats=seats,
        wards=ward_projections,
    )
