# 🏛️ The Coalition Era — the 5-Player Expansion

> Companion doc to the main [`README.md`](./README.md). That file covers the
> core 1v1 game — **Incumbent vs Opposition**, one city, one election.
> **This document covers The Coalition Era**: five players, one 101-seat
> Assembly, nobody starts with a majority — so the only way to govern is to
> negotiate, share power, and eventually betray each other. Nothing here
> touches or breaks the base 2-player game — see
> [Compatibility](#-compatibility--what-this-does-not-touch).

```
                                  ┌──────────────────────────┐
                                  │      101-SEAT ASSEMBLY     │
                                  │   ░░░░░░░░░░░░░░░░░░░░░░░░  │
                                  │   ▓▓▓▓▓▓▓▓░░░░░░▒▒▒▒▒▒▒▒▒▒  │
                                  │        ↑ MAGIC NUMBER: 51   │
                                  └──────────────────────────┘
        30 seats        25 seats        20 seats        15 seats      11 seats
      ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐  ┌─────────┐
      │  Player A │   │  Player B │   │  Player C │   │  Player D │  │Player E │
      │Industrialist│   │   Green   │   │ Socialist │   │Nationalist│  │Technocrat│
      └───────────┘   └───────────┘   └───────────┘   └───────────┘  └─────────┘
            ↑ Nobody alone can govern. Everybody has to talk to somebody.
```

---

## Table of Contents

1. [What this adds](#-what-this-adds)
2. [Quick Start](#-quick-start)
3. [The Core Loop](#-the-core-loop)
4. [Mechanic 1 — No One Has a Majority](#mechanic-1--no-one-has-a-majority)
5. [Mechanic 2 — Power Sharing (Satta & Vipaksha)](#mechanic-2--power-sharing-सत्ता--विपक्ष)
6. [Mechanic 3 — Asymmetrical Corruption](#mechanic-3--asymmetrical-corruption)
7. [Mechanic 4 — The Floor Test](#mechanic-4--the-floor-test)
8. [Mechanic 5 — ED/CBI Blackmail](#mechanic-5--edcbi-weaponization)
9. [Mechanic 6 — The 2029 Election (Round-by-Round Reveal)](#mechanic-6--the-2029-election)
10. [Quick Match — 5-Player Auto-Grouping](#-quick-match--5-player-auto-grouping)
11. [API Reference](#-api-reference)
12. [Data Model](#-data-model)
13. [File Manifest](#-file-manifest)
14. [Compatibility / What This Does Not Touch](#-compatibility--what-this-does-not-touch)
15. [Known Scope Cuts](#-known-scope-cuts--before-you-ship-this)
16. [Troubleshooting](#-troubleshooting)

---

## 🎭 What this adds

The base game is a clean binary: one Incumbent builds, one Opposition audits.
The Coalition Era throws that out and replaces it with **five players who all
want the same chair** — so the game becomes less about your own city and more
about *who you're willing to sit next to.*

| # | Mechanic | One-line pitch |
|---|----------|-----------------|
| 1 | **No One Has a Majority** | 101 seats, randomly split across 5 ideologies. 51 to govern. Nobody starts there. |
| 2 | **Power Sharing** | The CM leads the Ruling Coalition, but Deputy CM / Ministers must sign off on portfolios — and can be cut out of the black money. |
| 3 | **Asymmetrical Corruption** | The CM siphons the treasury, then chooses — partner by partner — how much of the loot to share. Stiff someone, and they remember. |
| 4 | **The Floor Test** | Any player can force a No-Confidence Motion once an hour. Lose it, and the government falls *mid-game.* |
| 5 | **ED/CBI Blackmail** | The Opposition can sit on a smoking gun and threaten a coalition partner privately instead of leaking it immediately. |
| 6 | **The 2029 Election** | War Chests buy vote-multipliers. Results are announced **live, round by round** — 24 rounds, 4 revealed every 10 real minutes (1 hour total), just like an actual election-night broadcast. |

---

## 🚀 Quick Start

Same backend, same frontend, zero new services, zero new environment
variables, zero database migrations. The Coalition Era is a purely additive
module bolted on next to the existing 2-player match system.

```bash
# 1. Backend (same as the base game)
cd backend
pip install -r requirements.txt --break-system-packages
uvicorn app.main:app --reload --port 8000

# 2. Frontend (same as the base game)
cd frontend
npm install
npm run dev
```

Then in the browser:

1. Log in (or register) same as always.
2. On the lobby screen you'll now see **two** buttons side by side:
   - ⚡ **Quick Match** — the original 1v1
   - 👥 **5-Player Coalition — Quick Match** — the new mode
3. Click the second one. Open 4 more tabs/incognito windows, log in as
   different accounts, and click the same button in each. The moment the
   5th player joins, the Assembly forms automatically.

> No 5 friends online right now? Open 5 browser tabs yourself and log in as
> 5 different test accounts — same trick the base game uses for solo
> testing.

---

## 🔁 The Core Loop

```
  ┌───────────────┐      5 players join       ┌────────────────┐
  │  QUICK MATCH   │ ─────────────────────────▶│  NEGOTIATING    │◀─────────────┐
  │  (queue of 5)  │      101 seats split       │  (5 min window) │               │
  └───────────────┘                            └───────┬────────┘               │
                                                          │ ≥51 seats agree        │
                                                          ▼                        │
                                                 ┌────────────────┐                │
                                       ┌────────▶│   GOVERNING     │                │
                                       │         │  (CM + Cabinet) │                │
                                       │         └───────┬────────┘                │
                          survives ────┘                 │                          │
                                                          │  ┌── Floor Test called    │
                                                          ▼  ▼                       │
                                                 ┌────────────────┐                 │
                                                 │  FLOOR TEST     │                 │
                                                 │ (confidence vs  │                 │
                                                 │  no-confidence) │                 │
                                                 └───────┬────────┘                 │
                                             loses / betrayal                       │
                                                          └─────────────────────────┘
                                                          (government collapses,
                                                           new negotiation opens)

                                                 CM calls it whenever ──▶ ┌────────────────┐
                                                                          │  2029 ELECTION  │
                                                                          │ 24 rounds / 1hr │
                                                                          └────────────────┘
```

---

## Mechanic 1 — No One Has a Majority

When the 5th player joins, `CoalitionEngine._start_negotiation()` runs a
constrained random split: 101 seats across 5 players, every party ≥1 seat,
and — critically — **re-rolled until no single party has ≥51 on its own**.
Each of the 5 ideologies (`Industrialist`, `Green`, `Socialist`,
`Nationalist`, `Technocrat`) is assigned to exactly one player.

A 5-minute real-time negotiation window (`NEGOTIATION_WINDOW_SECONDS = 300`)
opens immediately. Any player can propose a coalition with any subset of the
other four; once everyone in the proposal has accepted **and** the combined
seat count crosses 51, the government forms automatically. If the window
expires with nobody past 51, it just quietly reopens — the match never
soft-locks.

---

## Mechanic 2 — Power Sharing (सत्ता / विपक्ष)

Once a coalition crosses the Magic Number:

- The **largest party in the coalition** becomes **Chief Minister (CM)** —
  controls the treasury siphon and calls Floor Tests / the final election.
- The next-largest becomes **Deputy CM**; everyone else in the coalition
  becomes a **Minister**.
- The CM (and only the CM) can hand out the three portfolios —
  **Infrastructure**, **Welfare**, **Finance** — to coalition partners via
  `POST /api/coalition/{match_id}/ministry`.
- Everyone left outside the government is the **Opposition Bloc**: the
  largest of them is **Leader of Opposition (LoP)**; anyone with ≤12 seats
  is flavor-tagged as a **Fringe** party.

---

## Mechanic 3 — Asymmetrical Corruption

The CM can siphon treasury funds at any time via
`POST /api/coalition/{match_id}/siphon`, specifying an amount and — this is
the whole point — **a per-partner cut percentage**. Whatever isn't
explicitly cut to a partner stays in the CM's own War Chest.

```
POST /siphon  { amount: 1,000,000, cuts: { deputy_cm: 0.30 } }

                 ┌───────────────────────┐
   ₹1,000,000 ──▶│   CM decides the cut   │
                 └───────────┬───────────┘
                   ₹300,000 │            ₹700,000
                             ▼                     ▼
                   Deputy CM's War Chest      CM's own War Chest
```

Cut a partner out entirely, and the engine logs it publicly (⚠️ in the live
ticker) — everyone in the room sees the CM stiffed someone, even if they
don't yet know by how much. That partner now has a very good reason to
check the ⚔️ **Withdraw Support** button.

---

## Mechanic 4 — The Floor Test

Any seated player can call a No-Confidence Motion
(`POST /{match_id}/floor-test/trigger`), gated by a **1-hour real-time
cooldown** (`FLOOR_TEST_COOLDOWN_SECONDS = 3600`) so it can't be spammed.
Once called, every player has 90 seconds to cast `confidence` /
`no_confidence`; non-voters auto-default to backing their own bloc. If
confidence votes don't add up to 51+, the government **falls immediately** —
treasury freezes, all roles reset, and a fresh 5-minute negotiation window
opens.

A Deputy CM or Minister doesn't have to wait for someone else to call a
Floor Test, either — `POST /{match_id}/withdraw-support` lets them defect on
their own terms. If the coalition drops below 51 as a result, the collapse
is instant.

---

## Mechanic 5 — ED/CBI Weaponization

`POST /{match_id}/blackmail` lets any Opposition player privately message a
government partner: *"I have proof your CM is siphoning funds — withdraw
support, or I leak this to the press."* It's deliberately lightweight (a
public-image hit + a log entry) rather than a second corruption-evidence
system, since `corruption_graph.py` already owns the real audit trail for
the base game — this mechanic is about the *social* pressure, not a new
data model.

---

## Mechanic 6 — The 2029 Election

The CM can call the final election at any time from `governing` status
(`POST /{match_id}/election/start`). Final seats are computed from a blend
of each player's original party seats, their **Public Image Score**, and —
per the original design brief — how much of their **War Chest** they've
built up:

```
final_seats(player)  ∝  0.55 × original_party_seats
                       + 0.20 × (public_image_score share)
                       + 0.25 × (war_chest share)
```

The winner is whoever ends up with the most seats — **regardless of who was
CM the longest.**

### The "election night" reveal

This is the same `COUNTING_ROUNDS = 24` engine the base game's elections use
(see [`README.md` § 10](./README.md#10-elections--manifesto-ai-judging-24-round-counting)),
tuned so the whole count now takes **1 real-time hour**:

```
 24 total rounds ÷ 4 rounds-per-batch = 6 batches × 10 real minutes = 60 minutes
```

`ElectionRoundsAnnouncer.tsx` reveals 4 rounds at a time, every 10 real
minutes, ticking down to the next batch on-screen — so instead of the full
result dumping the instant the simulation resolves, it *looks and feels*
like a live election-night broadcast. This component is shared: it also now
powers the base 2-player game's election screen, since the base engine's
`COUNTING_DURATION_HOURS` was reduced from 2 → 1 to match.

---

## ⚡ Quick Match — 5-Player Auto-Grouping

`CoalitionQuickMatchQueue` is the 5-player sibling of the base game's
`QuickMatchQueue`. Since the base game's `MatchmakingEngine` compatibility
scoring is inherently pairwise, the 5-player queue keeps it simple and fast:
**FIFO grouping** — the moment 5 distinct players are waiting, the oldest 5
are popped and seated together. Stale queue entries auto-expire after 3
minutes so a player who closes their tab doesn't block a group forever.

---

## 📡 API Reference

All endpoints live under `/api/coalition` and are mounted in
`backend/app/main.py` alongside (not instead of) `/api/match`.

| Method | Path | What it does |
|---|---|---|
| `POST` | `/create` | Host a new 5-seat room, get a join code |
| `POST` | `/join` | Join a room by code |
| `GET` | `/{match_id}?token=` | Fetch current state |
| `POST` | `/quickmatch/join` | Join the 5-player auto-match queue |
| `GET` | `/quickmatch/status` | Poll queue status |
| `POST` | `/quickmatch/leave` | Leave the queue |
| `POST` | `/{match_id}/propose` | Propose a coalition to N other seats |
| `POST` | `/{match_id}/respond` | Accept/reject a pending proposal |
| `POST` | `/{match_id}/ministry` | CM assigns a portfolio to a partner |
| `POST` | `/{match_id}/siphon` | CM siphons funds with per-partner cuts |
| `POST` | `/{match_id}/blackmail` | Opposition privately threatens a partner |
| `POST` | `/{match_id}/withdraw-support` | A partner defects from the coalition |
| `POST` | `/{match_id}/floor-test/trigger` | Call a No-Confidence Motion |
| `POST` | `/{match_id}/floor-test/vote` | Cast a confidence/no-confidence vote |
| `POST` | `/{match_id}/election/start` | CM calls the final 2029 election |
| `WS` | `/ws/{match_id}?token=` | Live state broadcast to every seated player |

---

## 🗄️ Data Model

Everything lives in-memory inside `CoalitionRegistry` (mirrors the base
game's `MatchRegistry`) — no schema migrations, no new tables.

```python
CoalitionMatch
├── seats: dict[player_id, CoalitionSeat]
│     ├── ideology, party_seats, role, ministry
│     ├── war_chest            # black money kept + received
│     └── public_image_score   # dented by blackmail
├── government_ids / opposition_ids
├── cm_id / lop_id
├── treasury
├── pending_proposals: dict[proposal_id, CoalitionProposal]
├── floor_test: FloorTestState
├── negotiation_deadline / floor_test_cooldown_until
└── election_started_at / election_result / election_seats_by_player
```

---

## 📁 File Manifest

```
backend/app/
├── schemas/coalition.py          # Pydantic models for the 5-player mode
├── services/
│   ├── coalition_engine.py       # CoalitionMatch + CoalitionEngine (the rules)
│   ├── coalition_queue.py        # 5-player Quick Match FIFO grouping
│   └── incumbency_engine.py      # (edited) COUNTING_DURATION_HOURS 2 → 1
├── routers/coalition.py          # REST + WebSocket routes
└── main.py                       # (edited) mounts the coalition router

frontend/src/
├── lib/
│   ├── coalitionApi.ts           # typed REST client
│   └── useCoalitionSocket.ts     # live WebSocket hook
└── components/
    ├── CoalitionRoom.tsx         # the full 5-player game screen
    ├── ElectionRoundsAnnouncer.tsx  # shared live election-night reveal
    └── MatchLobby.tsx            # (edited) added the 5-Player Quick Match button
```

---

## ✅ Compatibility / What This Does Not Touch

- `services/match_registry.py`, `sovereign_engine.py`, `corruption_graph.py`
  — completely untouched. The 2-player game's data structures are never
  imported by anything in `coalition_engine.py`.
- `routers/match.py` — untouched; `routers/coalition.py` is a separate
  `APIRouter` mounted alongside it.
- The only genuinely shared edits are `incumbency_engine.py`'s election
  timing constants (now 1hr/24 rounds for *both* modes) and
  `MatchLobby.tsx` gaining a second button — everything else is additive.

---

## ⚠️ Known Scope Cuts — before you ship this

Being upfront about what's simplified relative to the full design brief, so
nothing surprises you in a demo:

- **Negotiation is proposal/accept, not free-form chat.** The design doc
  imagines a live voice/chat negotiation window; this ships the mechanical
  skeleton (propose → accept/reject → auto-form at 51) without an in-app
  chat UI. Bolt on a text channel per match if you want the "war room"
  feel from the base game's Campaign expansion.
- **Ministries are flavor + bookkeeping**, not yet wired into a shared City
  Map build-approval gate ("CM can't build a factory without Infrastructure
  Minister's sign-off") — there's no shared city map in this mode at all
  yet, since seat/treasury/coalition politics was the core ask.
- **The election formula is a deliberately simple weighted blend**
  (seats/image/war-chest), not a full ward-by-ward simulation — it's tuned
  to *feel* right and always sums to exactly 101 seats, not to model real
  electoral geography.
- **Corruption evidence is a flat public-image hit**, not hooked into the
  base game's Neo4j `corruption_graph.py` audit trail — intentional, to
  avoid coupling a brand-new mode to a stateful graph database mid-match.

---

## 🛠️ Troubleshooting

| Symptom | Fix |
|---|---|
| "5-Player Coalition" button does nothing | Check the backend logs for `/api/coalition/quickmatch/join` — confirm `coalition.router` is included in `main.py`. |
| Stuck at 4/5 in queue forever | Open a 5th tab — `CoalitionQuickMatchQueue` only forms a group once 5 *distinct* players are waiting; queue entries expire after 3 minutes. |
| Floor Test button greyed out | You're mid-cooldown (1 real hour between calls) — the button shows the countdown. |
| Election never reveals new rounds | `ElectionRoundsAnnouncer` paces purely off `election_started_at` vs wall-clock time — check your system clock isn't skewed from the server's. |
| Coalition WebSocket won't connect | Same auth token flow as the base game's match socket — confirm `NEXT_PUBLIC_API_BASE` is set and reachable, and that `token` is a valid, non-expired session token. |
