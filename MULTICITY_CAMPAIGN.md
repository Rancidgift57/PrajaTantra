# 🗺️ Multi-City Campaign — the "Black Money Pipeline" Expansion

> Companion doc to the main [`README.md`](./README.md). That file covers the
> core 1-city, 2-player game (Incumbent vs Opposition, one City Map, one
> election). **This document covers the Campaign layer added on top of it**:
> 3–5 cities played simultaneously, staggered elections, cross-city money
> laundering, and state-machinery retaliation. Nothing described here
> touches or breaks the base game — see [Compatibility](#compatibility--what-this-does-not-touch).

---

## Table of Contents

1. [What this adds](#what-this-adds)
2. [Quick Start](#quick-start)
3. [Core Concept: Opposite Roles Per City](#core-concept-opposite-roles-per-city)
4. [Mechanic 1 — The Black Money Pipeline](#mechanic-1--the-black-money-pipeline)
5. [Mechanic 2 — Staggered Election Phases](#mechanic-2--staggered-election-phases-the-domino-effect)
6. [Mechanic 3 — The Command Center UI](#mechanic-3--the-command-center-ui)
7. [Mechanic 4 — Asymmetric Retaliation](#mechanic-4--asymmetric-retaliation)
8. [In-App Tutorial](#in-app-tutorial)
9. [Full API Reference](#full-api-reference)
10. [Data Model](#data-model)
11. [File Manifest](#file-manifest)
12. [Compatibility / What This Does Not Touch](#compatibility--what-this-does-not-touch)
13. [Known Scope Cuts](#known-scope-cuts--before-you-ship-this)
14. [Troubleshooting](#troubleshooting)

---

## What this adds

The base game is one city, one Incumbent, one Opposition. The Campaign
layer wraps **3 to 5 of those cities together** under the same two players,
and gives them tools that only make sense once you're playing more than one
board at a time:

| # | Mechanic | One-line pitch |
|---|----------|-----------------|
| 1 | **Black Money Pipeline** | Skim funds from a project you govern, launder them through a Private Offshore Account, and spend that account funding riots/strikes in a city where you're the Opposition. |
| 2 | **Staggered Election Phases** | Cities vote in waves (Domino Effect), and winning an early phase grants a Momentum Buff in the next one — like real Indian general elections. |
| 3 | **Command Center UI** | A "war room" sidebar: every city colour-coded by your role, warning icons, one-click context switching, and Split-Screen mode. |
| 4 | **Asymmetric Retaliation** | Both players hold power somewhere, so both can abuse it — "Arrest Opposition Leaders" docks your rival's Influence Points campaign-wide. |

---

## Quick Start

The Campaign layer needs nothing extra beyond what the base game already
requires (Python 3.11+, FastAPI, Node 18+, Next.js) — no new services, no
new environment variables, no database migration.

```bash
# 1. Backend (same as the base game)
cd backend
pip install -r requirements.txt --break-system-packages   # or use a venv
uvicorn app.main:app --reload --port 8000

# 2. Frontend (same as the base game)
cd frontend
npm install
npm run dev
```

Then open **`http://localhost:3000/campaign`** — this is a new, standalone
route, separate from the base game's `/` dashboard. It doesn't require
logging in (see [Known Scope Cuts](#known-scope-cuts--before-you-ship-this)
for why, and how to fix that before shipping to real users).

1. Enter a name, click **🗺️ Start New Campaign** — this creates a 4-city
   campaign (Bengaluru → Mumbai + Chennai → Delhi) and gives you a 6-character
   join code.
2. Open a second browser tab (or send the code to a friend), go to
   `/campaign` again, and **Join** with that code.
3. The Command Center loads automatically once two players are seated.

---

## Core Concept: Opposite Roles Per City

This is the one idea the other three mechanics are built on top of.

When a campaign is created, cities are assigned roles by index: in
even-indexed cities, the host is **Incumbent**; in odd-indexed cities, the
host is **Opposition**. Once the second player joins, they take the
opposite seat in every city automatically:

```
Bengaluru (Phase 1):  You = Incumbent   |  Rival = Opposition
Mumbai    (Phase 2):  You = Opposition  |  Rival = Incumbent
Chennai   (Phase 2):  You = Incumbent   |  Rival = Opposition
Delhi     (Phase 3):  You = Opposition  |  Rival = Incumbent
```

So at any moment you are simultaneously **defending** a government somewhere
and **attacking** one somewhere else. That's what makes "steal from the city
you govern to fund an insurgency in the city you don't" a coherent piece of
gameplay rather than a random cross-account transfer.

Under the hood, each city is still a completely ordinary
`SovereignEngine` instance — the same class the base 1-city game uses. The
Campaign layer never modifies that class; it just orchestrates several
instances at once and layers new state (offshore accounts, phases,
debuffs) on top in `CampaignEngine`.

---

## Mechanic 1 — The Black Money Pipeline

**Backend:** `campaign_engine.py` → `siphon_construct`, `fund_opposition`, `expose_laundering`
**Frontend:** `CommandCenter.tsx` → "💰 Commission Project" / "🕵️ Fund Opposition from Offshore Account" / "🚨 Audit & Expose the Pipeline"

### Step 1 — Siphon into the Offshore Account

As Incumbent, commissioning a project works exactly like the base game's
Construction tab (same `ConstructionRequest`, same siphon-percent slider,
same corruption graph under the hood) — except the game no longer lets the
skimmed cut disappear into flavour text. It goes somewhere:

```
gross_siphon  = budget × siphon_percent%          (existing base-game math)
laundering_fee = 5% of gross_siphon                (new — see corruption_graph.py's
                                                      "remitted_amount" field)
net_to_offshore = gross_siphon − laundering_fee
```

That `net_to_offshore` amount lands in your **Private Offshore Account** —
a single balance that follows *you*, not any one city, tracked in
`CampaignPlayer.offshore_balance`.

### Step 2 — Fund your own Opposition campaign elsewhere

`fund_opposition(target_city_id, amount)` only works in a city where **you
are the Opposition**. It:

- Deducts `amount` from your offshore balance.
- Converts it into Influence Points in that city (`amount × 1/3500`,
  rounded, minimum 1) — the same currency Opposition already spends on
  Strikes and Crisis amplification in the base game.
- Adds a small "funded riots" cost to the *target* city: a worker-unrest
  bump and a public-trust drag, scaled to the amount spent.
- Appends a headline to both the target city's local feed and the
  campaign-wide Wire Desk ticker, e.g.:

  > 🕵️ Untraceable funds pour into Mumbai's opposition — riots, strikes and a
  > media blitz worth ₹1,00,000 land overnight (+29 Influence Points).

### Step 3 — Get exposed

`expose_laundering(source_city_id)` only works for whoever is **Opposition
in the source city** (i.e. your rival auditing you, not you auditing
yourself). On success:

- The source city takes a public-trust penalty (`22 + audit_level`).
- Your offshore account is marked `traced` and **frozen for 4 minutes**
  (`fund_opposition` will reject calls while frozen).
- Every *other* city where you're currently Opposition gets an immediate
  50% Influence Point haircut — the "funding dries up instantly" effect
  from the original spec — with its own headline explaining why.

This is intentionally asymmetric with Step 2: funding is instant and
untraceable *until* someone specifically goes looking for it in the
*source* city (not the city being funded), which is what makes the
audit a real detective mechanic rather than a guaranteed counter.

---

## Mechanic 2 — Staggered Election Phases (the "Domino Effect")

**Backend:** `campaign_engine.py` → `_phase_schedule`, `run_city_election`, `_apply_momentum`, `advance_phase`
**Frontend:** `CommandCenter.tsx` → sidebar "Phase N / total" badge, "📅 Advance to Next Phase", per-city "🗳️ Call Election"

### Schedule

Cities are split into phases automatically based on how many you start with:

| Cities | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|
| 3      | City 1  | City 2  | City 3  |
| 4      | City 1  | Cities 2, 3 | City 4 |
| 5      | City 1  | Cities 2, 3 | Cities 4, 5 |

City 1 always votes alone — a deliberate "Day 1" result that can cast a
shadow (or a shockwave) over everything that follows. A city's
`voting_open` flag only flips true once the campaign's `current_phase`
reaches that city's `phase` — calling an election earlier is rejected with
`400 "hasn't entered its election phase yet."`

### Running an election

`run_city_election(city_id)` is Incumbent-only for that city, and reuses
the base game's existing 24-round counting simulation
(`incumbency_engine.simulate_ten_rounds`, called through the base
`SovereignEngine.run_election`) — nothing about vote counting was
reinvented. The only campaign-specific step is mapping the winner's *name*
back to a `player_id`, since the underlying engine only knows usernames.

### The Momentum Buff (National Wave)

Immediately after a winner is determined, `_apply_momentum` scans every
city in the **next** phase. For each one where the winning player holds
*any* seat (Incumbent or Opposition), it adds:

```
buff = round(that_city's_current_public_trust × 10%)
```

directly to that city's `public_trust`, clamped to `[0, 100]` — a real,
persistent stat change, not just a UI badge (though the UI does also show
it, via `momentum_trust_buff` on `CampaignCityInfo`). This is designed to
create the "desperate abandonment" dynamic from the original pitch: a
player who loses Phase 1 badly may rationally decide to strip a
Phase-2 city for cash rather than try to defend it, since they're facing a
trust deficit before that city's polls even open.

### Advancing phases

`advance_phase()` is called by either seated player (no special
permission beyond being in the campaign) and simply increments
`current_phase`, flips `voting_open = true` for every city in the newly
current phase, and returns which cities just opened — the frontend uses
this to show a "📅 Phase 2 has begun" headline.

---

## Mechanic 3 — The Command Center UI

**Frontend:** `frontend/src/components/CommandCenter.tsx`

A three-part layout, built to *feel* like a trading terminal rather than a
city-builder:

```
┌───────────────┬──────────────────────────────────────────┐
│  GLOBAL MAP    │              CITY DASHBOARD               │
│  (sidebar)     │        (swaps instantly on click)         │
│                │                                            │
│ ● Bengaluru    │  Incumbent tools:                          │
│   Ph.1 · open  │   💰 Commission Project → skims to        │
│                │      Offshore Account                      │
│ ● Mumbai       │   🚔 Arrest Opposition Leaders (retaliate) │
│   Ph.2         │                                            │
│   ⚠️ Strike     │  Opposition tools:                         │
│                │   🕵️ Fund Opposition from Offshore Account │
│ ● Chennai      │   🚨 Audit & Expose the Pipeline           │
│   Ph.2         │                                            │
│                │  🗳️ Call Election (when phase is open)     │
│ ● Delhi        │                                            │
│   Ph.3         ├──────────────────────────────────────────┤
│                │           WIRE DESK (headline ticker)      │
│ [Split-Screen] │                                            │
│ [Advance Phase]│                                            │
└───────────────┴──────────────────────────────────────────┘
```

- **Global Map dots** — green if you're Incumbent there, red if you're
  Opposition, grey if you're not seated in that city at all (not possible
  in a 2-player campaign today, but the component supports N players for
  future expansion).
- **Warning icons** are derived live from each city's real
  `SovereignStateResponse` on every poll: an active Flash Crisis shows
  `⚠️ Strike`, any block with a live `frozen_until` shows
  `🚨 Audit in Progress`, and `emergency_powers=true` shows `🛑 Emergency`.
- **Context switching** is a single `useState` — clicking a sidebar row
  swaps which city's data the whole dashboard renders, no page navigation,
  no re-fetch (the already-polled `CampaignState` has every city's data).
- **Split-Screen Mode** renders a second, more compact `CityDashboard`
  side-by-side. Double-click (or the "open in split pane" link) sends a
  city into the second pane while the first pane keeps whatever you had
  selected — so you can, e.g., watch Mumbai's election counter while still
  acting in Bengaluru.
- **Polling, not WebSockets** — the Command Center refreshes campaign state
  every 5 seconds (`pollMs` prop) via `GET /api/campaign/{id}/state`. The
  base game's 1-city matches use a WebSocket tick loop
  (`routers/match.py`); the Campaign layer intentionally does not, to keep
  this feature slice small. See [Known Scope Cuts](#known-scope-cuts--before-you-ship-this).

---

## Mechanic 4 — Asymmetric Retaliation

**Backend:** `campaign_engine.py` → `retaliate`
**Frontend:** `CommandCenter.tsx` → "🚔 Arrest Opposition Leaders" (Incumbent panel)

Played from any city where you're currently Incumbent
(`retaliate(source_city_id)`), this is the campaign's answer to "misusing
state machinery":

- Your rival's `ip_debuff_multiplier` is set to **0.4** for **300 seconds**
  (`RETALIATION_IP_MULTIPLIER`, `RETALIATION_DEBUFF_SECONDS` in
  `schemas/campaign.py`).
- **Every** city where your rival holds a seat (Incumbent or Opposition)
  has its `influence_points` immediately cut to 40% of its current value —
  not just capped going forward, but actively slashed right now.
- While the debuff is active, any `fund_opposition` your rival attempts
  also grants 40% of the Influence Points it normally would (the
  multiplier is applied at grant-time via `player.ip_multiplier()`).
- A headline explaining the crackdown is appended both to the source
  city's local feed and to the target city/cities' feeds.

Because roles are always opposite, this genuinely is **mutually assured
destruction**: any Incumbent seat you hold is also a seat your rival could
theoretically use to retaliate against *you*, the moment they're
Incumbent there. There's no "safe" side to play — only a judgment call
about whether the trust cost (from associated headlines/optics) is worth
crippling your opponent's Opposition economy for five minutes.

---

## In-App Tutorial

**File:** `frontend/src/components/CampaignTutorialModal.tsx`

A 5-step walkthrough modal, structurally identical to the base game's
existing `TutorialModal.tsx` (same header/footer chrome, same progress
dots, same `localStorage`-gated "show once" behaviour) but written
entirely for the Campaign layer:

1. **One Campaign, Many Cities** — explains the opposite-roles-per-city rule.
2. **The Black Money Pipeline** — siphon → offshore → fund → expose, in plain language.
3. **Staggered Election Phases** — phases, voting windows, the Momentum Buff.
4. **The Command Center** — Global Map colours/icons, context switching, Split-Screen.
5. **Asymmetric Retaliation** — what "Arrest Opposition Leaders" does and why it's mutual.

**Where it shows up:**

- **Automatically**, the first time a player's browser hits `/campaign`
  (tracked via `localStorage["prajatantra.campaign_tutorial_seen.v1"]`,
  deliberately a different key from the base game's
  `prajatantra.tutorial_seen.v1` so the two tutorials are independent —
  a returning base-game player still sees the Campaign tutorial once).
- **On demand**, via the **📖 How This Works** link that appears in:
  - the pre-campaign lobby screen (`frontend/src/app/campaign/page.tsx`), and
  - the Command Center sidebar header, once a campaign is underway.

Both entry points pass the same `onClose` handler, so re-opening it never
re-marks it "seen" until the player explicitly finishes or dismisses it
again — matching the base tutorial's behaviour exactly.

---

## Full API Reference

Base URL: `/api/campaign` (mounted in `backend/app/main.py` alongside the
existing `/api/prajatantra` and `/api/match` routers — see
`routers/campaign.py`).

All mutating endpoints return the *fresh* relevant state object so the
frontend never needs a follow-up GET after an action (though
`CommandCenter` still polls `/state` periodically as a safety net).

| Method | Path | Auth model | Purpose |
|--------|------|-----------|---------|
| `POST` | `/create?host_player_id=...` | body: `{host_username, city_names[]}` | Creates a campaign, 3–5 cities, host seated by role parity. Returns `CampaignStateResponse`. |
| `POST` | `/join?player_id=...` | body: `{join_code, username}` | Seats the second player; fills in the complementary role in every city. Returns `CampaignStateResponse`. |
| `GET`  | `/{campaign_id}/state` | — | Full campaign snapshot: every city, every offshore account, recent headlines. |
| `POST` | `/{campaign_id}/siphon-construct` | body: `{player_id, city_id, construction: ConstructionRequest}` | Incumbent-only. Builds a project and routes the siphoned cut into the player's offshore account. |
| `POST` | `/{campaign_id}/fund-opposition` | body: `{player_id, target_city_id, amount}` | Opposition-only (in `target_city_id`). Spends offshore balance for Influence Points + unrest/trust pressure there. |
| `POST` | `/{campaign_id}/expose-laundering` | body: `{exposer_player_id, source_city_id, audit_level}` | Opposition-only (in `source_city_id`). Trust penalty + freezes the Incumbent's offshore account + dries up their funding elsewhere. |
| `POST` | `/{campaign_id}/elections/run` | body: `{player_id, city_id}` | Incumbent-only, city's phase must be open and not already decided. Runs the 24-round simulation and applies the Momentum Buff to next-phase cities. |
| `POST` | `/{campaign_id}/phase/advance` | body: `{requesting_player_id}` | Either seated player. Opens the next phase's cities for voting. |
| `POST` | `/{campaign_id}/retaliate` | body: `{actor_player_id, source_city_id}` | Incumbent-only (in `source_city_id`). Slashes the rival's Influence Points campaign-wide for 5 minutes. |

Every mutating route returns `403` (`PermissionError`) if the caller
doesn't hold the required role, or `400` (`ValueError`) for invalid state
transitions (e.g. funding from a frozen account, voting in a city whose
phase hasn't opened, advancing past the final phase) — same convention the
base game's `/api/prajatantra` and `/api/match` routers already use.

### Example: full curl walkthrough

```bash
BASE=http://localhost:8000

# 1. Create as host
curl -s -X POST "$BASE/api/campaign/create?host_player_id=p1" \
  -H 'Content-Type: application/json' \
  -d '{"host_username":"Nikhil","city_names":["Bengaluru","Mumbai","Chennai","Delhi"]}' \
  | tee /tmp/create.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['campaign_id'], d['join_code'])"

CAMPAIGN_ID=$(python3 -c "import json; print(json.load(open('/tmp/create.json'))['campaign_id'])")
JOIN_CODE=$(python3 -c "import json; print(json.load(open('/tmp/create.json'))['join_code'])")

# 2. Join as the rival
curl -s -X POST "$BASE/api/campaign/join?player_id=p2" \
  -H 'Content-Type: application/json' \
  -d "{\"join_code\":\"$JOIN_CODE\",\"username\":\"Asha\"}"

# 3. Inspect state to find which city p1 is Incumbent in
curl -s "$BASE/api/campaign/$CAMPAIGN_ID/state" | python3 -m json.tool

# 4. Siphon-construct in that city (replace CITY_ID)
curl -s -X POST "$BASE/api/campaign/$CAMPAIGN_ID/siphon-construct" \
  -H 'Content-Type: application/json' \
  -d '{
        "player_id": "p1",
        "city_id": "CITY_ID",
        "construction": {
          "role": "Incumbent", "player_username": "Nikhil",
          "block_type": "Industrial", "name": "Grand Highway",
          "budget": 1000000, "siphon_percent": 40
        }
      }'
```

---

## Data Model

```
Campaign
├── id, join_code, status ("waiting" | "active" | "finished")
├── player_a, player_b : CampaignPlayer
│     ├── player_id, username
│     ├── offshore_balance                 ← the Private Offshore Account
│     ├── account_frozen_until, account_traced
│     └── ip_debuff_multiplier, ip_debuff_until   ← Retaliation state
├── phase_order : [[city_id, ...], ...]     ← e.g. [["A"],["B","C"],["D"]]
├── current_phase : int
└── cities : { city_id → CampaignCity }
      ├── city_id, name, phase
      ├── sovereign : SovereignEngine       ← the UNCHANGED base-game engine
      ├── incumbent_player_id, opposition_player_id
      ├── voting_open, election_completed, winner_player_id
      └── momentum_trust_buff
```

`CampaignEngine` (the module-level singleton `campaign_engine`, mirroring
the base game's `match_registry` singleton pattern) owns an in-memory
`dict[str, Campaign]`, exactly like `MatchRegistry` owns `dict[str, Match]`.
Same swap-in path applies if you outgrow memory: replace the dict with
Postgres/Redis-backed storage and keep every method signature the same
(see the docstring at the top of `match_registry.py`, which this module
was deliberately written to be a sibling of).

---

## File Manifest

Everything below is **new**, except the one bugfix noted:

```
backend/app/schemas/campaign.py         New — all Campaign request/response models
backend/app/services/campaign_engine.py New — CampaignEngine orchestrator (the 4 mechanics)
backend/app/routers/campaign.py         New — /api/campaign/* FastAPI routes
backend/app/main.py                     Modified — registers campaign.router
backend/app/schemas/prajatantra.py      Bugfix — TenRoundSimulationResponse was missing
                                         seat/emergency fields that incumbency_engine.py
                                         already set and sovereign_engine.run_election
                                         already read, so every election (base game
                                         included) crashed with AttributeError. Fixed
                                         with additive, default-valued fields — no
                                         existing behaviour changes.

frontend/src/lib/campaignApi.ts              New — typed fetch client for /api/campaign
frontend/src/components/CommandCenter.tsx     New — the Command Center UI
frontend/src/components/CampaignTutorialModal.tsx  New — the in-app tutorial
frontend/src/app/campaign/page.tsx            New — lobby (create/join) + mounts CommandCenter
```

---

## Compatibility / What This Does Not Touch

- `SovereignEngine`, `SovereignMemory`, `tactical_cards.py`,
  `cooldown_store.py`, `corruption_graph.py`, `incumbency_engine.py`'s
  simulation logic — **unmodified**. Each campaign city is a normal
  instance of the exact same engine the 1-city game uses.
- `match_registry.py` / `routers/match.py` (the 2-seat, single-city,
  WebSocket-driven multiplayer mode) — **unmodified and unaffected**. A
  Campaign and a Match are two independent registries; creating one never
  touches the other.
- The single bugfix (`TenRoundSimulationResponse` field additions) is
  additive-only: every new field has a default value, so any existing code
  or stored JSON that doesn't set them behaves exactly as before. This was
  necessary because it silently broke election calls campaign-wide *and*
  in the base game — see the File Manifest above.

---

## Known Scope Cuts — before you ship this

This was built as a working feature slice, not a production hardening
pass. Before exposing it to real users, close these gaps:

1. **Auth.** Campaign endpoints take `player_id` directly in the request
   body/query string, unlike `routers/match.py`, which resolves the
   caller's identity from a bearer token via `_resolve_player(token)`.
   Right now nothing stops a client from passing someone else's
   `player_id`. Swap in the same token-resolution pattern before shipping.
2. **Persistence.** `CampaignEngine._campaigns` is an in-memory dict — a
   backend restart loses every in-progress campaign, same tradeoff the
   base `MatchRegistry` makes today. The docstring in `campaign_engine.py`
   spells out the swap-in path (Postgres/Redis-backed dict) if you need
   durability.
3. **Real-time updates.** The Command Center polls every 5 seconds instead
   of using the base game's WebSocket tick loop
   (`connection_manager.py` + `routers/match.py`'s `_match_tick_loop`).
   Good enough for turn-paced play; wire up a campaign-scoped WebSocket
   broadcast if you want sub-second updates (e.g. for the election
   countdown or Flash Crisis timers to feel snappy).
4. **Only 2 players.** The data model (`Campaign.player_a` /
   `Campaign.player_b`) and the "opposite role in every city" assignment
   only support exactly two players. Scaling to more would mean rethinking
   role assignment (which the CommandCenter's grey-dot fallback was
   written anticipating, but the backend doesn't implement).

---

## Troubleshooting

**"Unknown city_id in this campaign."** — `city_id`s are generated per
campaign (`C1_XXXX` style random suffixes), not the same across different
campaigns. Always read them from a `state()`/`create()`/`join()` response,
never hardcode one.

**"You must be Incumbent in this city to commission a project here." /
similar 403s** — check `GET /{campaign_id}/state` and compare your
`player_id` against that city's `incumbent_player_id` /
`opposition_player_id`. Remember roles are opposite in different cities —
being Incumbent in City A does not make you Incumbent anywhere else.

**"hasn't entered its election phase yet."** — call
`POST /{campaign_id}/phase/advance` until `current_phase` reaches that
city's `phase` (visible in `CampaignCityInfo.phase`), or check
`voting_open` directly.

**Election call throws `AttributeError: 'TenRoundSimulationResponse'
object has no attribute 'incumbent_seats'`** — you're running an older
`schemas/prajatantra.py` without the bugfix described in
[File Manifest](#file-manifest). Pull the latest version of that file.
