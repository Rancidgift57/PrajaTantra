# 🇮🇳 Prajatantra — प्रजातंत्र

**A 2-player political-economic simulation.** One player governs a city as the
**Incumbent** — building infrastructure, running government schemes, spending
budgets. The other plays the **Opposition** — digging through a live
corruption graph, launching strikes, leaking audit findings to the press.
Every three in-game days, both sides face a 24-round election, scored by an
AI-judged manifesto, a live vote-counting simulation, and a hemicycle seat
map. Win big enough, and the Incumbent can declare **Emergency** — sweeping
authoritarian construction powers that override the city's own zoning laws.

It's part SimCity, part corruption-investigation game, part election
simulator — played head-to-head in real time over WebSockets.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture](#architecture)
3. [Manual Setup](#manual-setup)
4. [Deployment](#deployment-render--vercel--supabase)
5. [Environment Variables](#environment-variables)
6. [How to Play](#how-to-play)
   - [1. Create your account](#1-create-your-account)
   - [2. Start or join a match](#2-start-or-join-a-match)
   - [3. The City Map & zoning](#3-the-city-map--zoning)
   - [4. Building Catalog](#4-building-catalog)
   - [5. Government Schemes](#5-government-schemes)
   - [6. Playing the Incumbent](#6-playing-the-incumbent)
   - [7. Playing the Opposition](#7-playing-the-opposition)
   - [8. The ED/CBI Corruption Graph](#8-the-edcbi-corruption-graph)
   - [9. Federal Grants & Trade Duels](#9-federal-grants--trade-duels)
   - [10. Elections — manifesto, AI judging, 24-round counting](#10-elections--manifesto-ai-judging-24-round-counting)
   - [11. The Seat Map](#11-the-seat-map)
   - [12. Emergency Powers (the dictatorship mechanic)](#12-emergency-powers-the-dictatorship-mechanic)
   - [13. Leaderboard](#13-leaderboard)
   - [Glossary of city stats](#glossary-of-city-stats)
7. [API Reference](#api-reference)
8. [Project Structure](#project-structure)
9. [Troubleshooting](#troubleshooting)

---

## Quick Start

Fastest path, fully local, zero external services required:

```bash
docker compose up --build
```

Then open:

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend health check | http://localhost:8000/health |
| Neo4j browser (optional) | http://localhost:7474 |

Default Docker credentials:

- Neo4j user / password: `neo4j` / `password`
- PostgreSQL user / password / db: `prajatantra`

Without Neo4j or Postgres configured, the backend transparently falls back to
in-memory stores for both the corruption graph and player accounts — the
whole game is playable with **zero database setup**. This is the easiest way
to try it solo (open two browser tabs and play both seats yourself).

---

## Architecture

```
┌─────────────────┐        REST (JSON)         ┌──────────────────────┐
│  Next.js 16      │ ─────────────────────────▶ │  FastAPI backend      │
│  (App Router)    │ ◀───────────────────────── │  (Python 3.11+)       │
│  frontend/src/    │                            │  backend/app/         │
└────────┬─────────┘        WebSocket            └──────────┬───────────┘
         │            (live match sync)                      │
         └──────────────────────────────────────────────────┘│
                                                               │
                                     ┌─────────────────────────┼─────────────────────┐
                                     │                         │                     │
                              ┌──────▼──────┐         ┌────────▼────────┐   ┌────────▼────────┐
                              │  Supabase/   │         │  Neo4j (or       │   │  HuggingFace     │
                              │  Postgres    │         │  in-memory       │   │  Inference API    │
                              │  (accounts,  │         │  fallback)       │   │  (manifesto AI    │
                              │  leaderboard)│         │  corruption      │   │  judging, with     │
                              │              │         │  graph           │   │  offline fallback) │
                              └──────────────┘         └─────────────────┘   └───────────────────┘
```

**Backend** (`backend/app/`) — FastAPI, fully async:
- `services/` — the actual simulation engines (see below), each independently
  testable and each with a documented in-memory fallback so nothing hard-crashes
  if an external service (Postgres, Neo4j, HuggingFace) isn't configured.
- `routers/` — thin HTTP/WebSocket layers over the services. `match.py` wraps
  the single-player engines in a 2-seat, isolated multiplayer room.
- `schemas/` — every request/response is a typed Pydantic model.

| Engine | File | Responsibility |
|---|---|---|
| `SovereignEngine` | `sovereign_engine.py` | Core city state: treasury, GDP, trust, pollution, unrest, prestige, infrastructure blocks, headlines, Emergency powers. |
| `DevelopmentEngine` | `development_engine.py` | Building catalog + Government Schemes layered on top of `SovereignEngine`. |
| `CorruptionGraph` | `corruption_graph.py` | Generates a layered fund-siphoning graph (Mayor → Shell Company → Vendor → ...) per construction project. Neo4j-backed with an in-memory fallback. |
| `ElectionEngine` | `election_engine.py` | Grades manifesto (AI-judged) + speech rhetoric + city performance into a trust score. |
| `IncumbencyEngine` | `incumbency_engine.py` | Pro-/anti-incumbency wave math, the 24-round vote-counting simulation, and seat allocation. |
| `ManifestoAI` | `manifesto_ai.py` | HuggingFace zero-shot judging of manifesto credibility, with a deterministic offline heuristic fallback. |
| `AuthEngine` | `auth_engine.py` | Register/login/session, dual-mode: Supabase/Postgres if `DATABASE_URL` is set, else in-memory. |
| `MatchRegistry` / `ConnectionManager` | `match_registry.py`, `connection_manager.py` | 2-seat match rooms + WebSocket broadcast so both players see the same live state. |
| `MatchmakingEngine` | `matchmaking.py` | Ideology-contrast + MMR-based opponent scoring (used by the queue-based matchmaking endpoint). |

**Frontend** (`frontend/src/`) — Next.js App Router, React 19, Tailwind:
- `app/page.tsx` — the entire game dashboard (auth gate → lobby → match).
- `components/CityMap.tsx` — the zoned 8×8 city grid you build on.
- `components/SeatMap.tsx` — the hemicycle election seat-map chart.
- `components/CityDevelopment.tsx` — Building Catalog + Schemes UI.
- `lib/api.ts`, `lib/matchApi.ts` — typed REST/WS clients.
- `lib/useMatchSocket.ts` — the live WebSocket hook that keeps both seats in sync.

---

## Manual Setup

### Backend

```bash
cd backend
cp .env.example .env          # Windows: copy .env.example .env
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
cp .env.example .env.local    # Windows: copy .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000. Without any `.env` values set, both the
corruption graph and player accounts run entirely in memory — good enough to
play a full match solo across two browser tabs.

---

## Deployment (Render + Vercel + Supabase)

This is the stack the project is actively deployed on:

### 1. Database — Supabase
1. Create a project at [supabase.com](https://supabase.com).
2. **SQL Editor** → run, in order:
   - `database/postgres/001_core_schema.sql`
   - `database/postgres/002_auth_columns.sql`
   - `database/postgres/003_player_identity.sql`
3. **Project Settings → Database → Connection string → Transaction pooler**
   (port `6543`) — copy it for the backend's `DATABASE_URL`.

### 2. Backend — Render
1. New **Web Service**, root directory `backend/`, build with the included
   `Dockerfile` (or `pip install -r requirements.txt` + `uvicorn app.main:app --host 0.0.0.0 --port $PORT` if not using Docker).
2. Set environment variables (see [table below](#environment-variables)):
   `DATABASE_URL`, `FRONTEND_ORIGIN` (or `FRONTEND_ORIGINS`), `PRAJATANTRA_TOKEN_SECRET`.
3. Deploy. Check `https://<your-service>.onrender.com/health` — it should
   report `"database_connected": true`.

### 3. Frontend — Vercel
1. Import the repo, root directory `frontend/`.
2. Set `NEXT_PUBLIC_API_BASE=https://<your-backend>.onrender.com`.
3. Deploy. `*.vercel.app` preview URLs are auto-allowed by the backend's CORS
   regex — no need to add every preview deploy manually.

### Self-hosting everything in one place
```bash
docker compose up -d --build
```
Uses the bundled Postgres + Neo4j containers instead of Supabase/Neo4j Aura.

---

## Environment Variables

**Backend** (`backend/.env`):

| Variable | Required? | Purpose |
|---|---|---|
| `DATABASE_URL` | No (falls back to in-memory) | Supabase/Postgres connection string. Without it, accounts don't survive a backend restart. |
| `FRONTEND_ORIGIN` | No | Single allowed CORS origin. Defaults to `http://localhost:3000`. |
| `FRONTEND_ORIGINS` | No | Comma-separated list if you need more than one origin. `localhost`/`127.0.0.1` (any port) and any `*.vercel.app` subdomain are always allowed automatically. |
| `PRAJATANTRA_TOKEN_SECRET` | Recommended in production | HMAC secret signing session tokens. Changing it invalidates every existing session — set it once, don't rotate casually. |
| `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` / `NEO4J_DATABASE` | No (falls back to in-memory graph) | Enables a real, persistent corruption graph instead of the per-process in-memory one. |
| `HUGGINGFACE_API_TOKEN` (or `HF_API_TOKEN`) | No (falls back to a heuristic) | Enables live AI manifesto judging via HuggingFace's zero-shot Inference API. |
| `HF_MANIFESTO_MODEL` | No | Overrides the default model (`facebook/bart-large-mnli`). |

**Frontend** (`frontend/.env.local`):

| Variable | Required? | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | No | Backend base URL. Defaults to `http://localhost:8000`. **Must** point at your deployed backend in production — this is inlined at build time, so changing it requires a redeploy. |

---

## How to Play

### 1. Create your account

Open the app → **New Account**. You'll need:

- **Username** (letters/numbers/underscore, 3–24 chars)
- **Email**
- **Password** (6+ characters)
- **Name of your city** — this is your city's display name throughout the game
- **Political Ideology** — one of `Industrialist`, `Green`, `Socialist`,
  `Nationalist`, `Technocrat`. This is currently used for matchmaking flavor
  (an ideology-contrast score factors into opponent-matching) and shows up on
  your profile — it doesn't apply direct stat modifiers to your city yet.

Already have an account? Use **Login** with your username *or* email.

### 2. Start or join a match

A **match** is a private 2-seat room:

- **Create a match** → you become the **Incumbent** and get a short
  **join code**. Share it with your opponent.
- **Join a match** → enter your opponent's join code, and you become the
  **Opposition**.

Once both seats are filled, the match goes live over a WebSocket — every
action either player takes (building, striking, leaking, launching a scheme)
broadcasts instantly to both screens. No polling, no refreshing.

> Matches live in server memory only, scoped independently — two matches
> never see each other's city. If the backend restarts (e.g. a redeploy), old
> matches are gone; the app detects this and drops you back to the lobby
> automatically instead of hanging on a dead connection.

### 3. The City Map & zoning

The Incumbent's city is an 8×8 grid of **zones** — `RESIDENTIAL`,
`COMMERCIAL`, `INDUSTRIAL`, `STRATEGIC`, plus fixed `ROAD`, `GREEN`, `WATER`,
and `GOVERNMENT` tiles that can't be built on. Every zone only accepts
certain building types:

| Zone | Allowed buildings |
|---|---|
| Residential | Hospital Chain, School Network, Mall |
| Commercial | Mall, Tech Park |
| Industrial | Port, Factory, Waste Plant |
| Strategic | Tech Park, Power Grid |
| Government | Waste Plant, School Network, Power Grid |
| Water | Port only |

Pick a building from the catalog, then click an eligible tile. The game
tells you exactly which buildings are legal on a tile if you try the wrong
one. (This zoning wall is exactly what **Emergency Powers** — see
[§12](#12-emergency-powers-the-dictatorship-mechanic) — lets you bypass.)

### 4. Building Catalog

Every building is a genuine tradeoff — there's no strictly-best option:

| Building | Portfolio | Cost | Gold/tick | Pollution | Unrest | Trust | Prestige | Jobs |
|---|---|---|---|---|---|---|---|---|
| **Container Port** 🏗️ | Industrial | ₹6,00,000 | +1,40,000 | +16 | +10 | −4 | +6 | +18 |
| **Commercial Mall** 🏬 | Industrial | ₹3,20,000 | +68,000 | +3 | −1 | +2 | +2 | +10 |
| **Manufacturing Factory** 🏭 | Industrial | ₹4,80,000 | +1,04,000 | +12 | +6 | −2 | +3 | +22 |
| **Waste Management Plant** ♻️ | Social | ₹2,60,000 | +8,000 | **−18** | −4 | +10 | +1 | +6 |
| **Tech Park** 💻 | Strategic | ₹4,20,000 | +58,000 | +1 | 0 | +3 | +10 | +14 |
| **Renewable Power Grid** ⚡ | Strategic | ₹5,40,000 | +22,000 | −8 | −2 | +6 | **+14** | +8 |
| **Public School Network** 🏫 | Social | ₹3,00,000 | +4,000 | −1 | −6 | +14 | +3 | +9 |
| **Public Hospital Chain** 🏥 | Social | ₹3,80,000 | +6,000 | −2 | −5 | **+18** | +2 | +11 |

Rule of thumb: **Industrial** buildings pay the bills but cost you trust and
raise pollution/unrest. **Social** buildings do the opposite — they drain
the treasury every tick but are your best tools for winning back trust
before an election. **Strategic** buildings are the balanced middle ground,
with the best prestige and least pollution.

### 5. Government Schemes

Separate from physical construction — schemes are time-limited *policy*
choices with an upfront cost, a recurring per-cycle cost, and a fixed
duration:

| Scheme | Upfront | Per-tick | Duration | Trust | Unrest | Jobs | Pollution | GDP |
|---|---|---|---|---|---|---|---|---|
| **MSME Subsidy** | ₹1,80,000 | ₹12,000 | 6 cycles | +6 | −3 | +12 | +2 | +8% |
| **Universal Free Healthcare** | ₹2,60,000 | ₹22,000 | 10 cycles | **+16** | −8 | +4 | 0 | −2% |
| **Swachh Shehar Abhiyan** (Clean City) | ₹90,000 | ₹8,000 | 5 cycles | +8 | 0 | +3 | **−14** | 0% |
| **National Skill Mission** | ₹1,40,000 | ₹10,000 | 8 cycles | +5 | −5 | **+16** | 0 | +4% |
| **Green Energy Subsidy** | ₹2,00,000 | ₹14,000 | 7 cycles | +7 | −2 | +6 | −10 | +3% |
| **Farmer Loan Waiver** | see catalog | — | — | — | — | — | — | — |

Schemes stack with buildings: e.g. Green Energy Subsidy + Power Grid, or
Skill Mission + a Factory/Port, compound their effects.

### 6. Playing the Incumbent

Your job: keep the treasury healthy, keep trust high enough to survive the
next election, and keep the Opposition from finding (and leaking) anything
too damaging.

Your toolkit:
- **Construct infrastructure** — pick a portfolio type, name your project,
  set a **budget** and a **siphon %**. Yes — you can skim public funds off
  your own project. Every construction call quietly generates a real,
  explorable **corruption graph** behind the scenes (Mayor → Shell Company →
  Vendor chain), whether you siphon 0% or 80%. Higher siphon = more money in
  your pocket, but a fatter, easier-to-detect trail.
- **Build from the catalog** / **Launch a Scheme** — the strategic layer
  described above.
- **Request a Federal Grant** — ask the (simulated) Prime Minister for funds;
  approval odds depend on your alignment (`ally`/`rival`/`swing`) with the
  ruling party.
- **Enter a Trade Duel** — a head-to-head export/tariff/supply-chain contest
  against a rival country for a temporary GDP buff.
- **Campaign** — write your manifesto and speech before each election (see
  §10).
- **Declare Emergency** — if you clear an 80%+ seat supermajority (§12).

### 7. Playing the Opposition

Your job: expose corruption before the next election, damage the Incumbent's
trust score, and try to flip the seat map.

Your toolkit:
- **Run a CAG Audit** — pick an audit depth (1–8). Deeper audits are more
  likely to trace the full money trail back to the Mayor, but cost more
  Influence Points. A successful deep audit returns a **smoking gun** and one
  or more suspicious paths through the graph.
- **Leak the audit to the press** — turns your audit findings into a public
  headline, directly damaging the Incumbent's public trust. This is
  irreversible and burns the finding (use it when it'll actually swing the
  election, not the moment you find it).
- **Call a Strike** — spend Influence Points to shut down one of the
  Incumbent's infrastructure blocks, costing them revenue and raising
  unrest.
- **Watch the ED/CBI Corruption Graph panel** — this is your investigation
  board; every construction project's graph shows up here once you've
  targeted it with an audit.

### 8. The ED/CBI Corruption Graph

Every construction project generates a layered graph of the money's actual
path:

```
Mayor ──funds──▶ Shell Company ──routes──▶ Vendor ──delivers──▶ Project
           ╲                                              ╱
            ╲── kickback ──▶ Offshore Account ──back to── ╱
```

- **`layer_depth`** (1–6) controls how many hops of laundering separate the
  Mayor from the money — deeper layers are harder for an audit to fully
  trace.
- **Audits** walk this graph up to `audit_level` hops deep and return a
  **suspicion score** per path; crossing the right depth threshold reveals
  the **smoking gun** — direct proof connecting the Mayor to the siphon.
- Runs against a real Neo4j graph database if `NEO4J_URI` is configured;
  otherwise an in-memory graph store with identical query semantics keeps
  everything playable with zero setup.
- **The graph panel only populates after you've run a construction project
  with siphon% > 0 and then targeted it with an audit** — it's empty by
  design until then, not a bug.

### 9. Federal Grants & Trade Duels

- **Federal Grant**: request funds from the national government. Approval
  and amount scale with your declared `alignment` to the ruling coalition —
  an `ally` city gets easier money than a `rival` one.
- **Trade Duel**: pick your country's net-exports / tariff-rate /
  supply-chain-resilience profile and duel a rival country's profile. The
  winner's city gets a temporary GDP multiplier buff.

### 10. Elections — manifesto, AI judging, 24-round counting

Elections are held **every 3 in-game days**. Vote counting is a live
**2-hour window split into 24 rounds** — rounds 1–6 are postal/rural
ballots, 7–18 are urban centres, 19–24 are the most volatile swing zones.

**Step 1 — Campaign.** Write a **manifesto** and a **campaign speech**.
- The manifesto is scored for *practicality*: does it address the crises the
  game generated, does it name a real funding mechanism (tax, bond, PPP,
  audit), is it appropriately detailed (not too thin, not padded)?
- **The manifesto is also judged by an AI model** (HuggingFace zero-shot
  classification, labels: *credible funded plan* / *vague populist promise*
  / *corrupt or unfunded promise*). Populist buzzwords ("free", "universal",
  "guaranteed", "mega") without a funding mechanism get penalized hard —
  especially if the promised cost would exceed your treasury. No
  HuggingFace token configured? It falls back to an offline keyword
  heuristic automatically — the mechanic works the same either way, you just
  won't see `"manifesto_ai_source": "huggingface"` in the breakdown.
- The speech is scored for rhetoric (structure, engagement, specificity).
- Your city's actual live performance (trust, treasury, pollution, GDP) is
  scored too — you can't manifesto your way out of a genuinely mismanaged
  city.

**Step 2 — Incumbency wave.** Consecutive terms in power, scams already
exposed, and current public trust combine into an *incumbency factor* that
swings the vote either pro- or anti-incumbent — remember, voters get
tired of the same face after enough terms. The manifesto's trust score
nudges this wave further, so campaign quality and real development delivery
genuinely move the outcome, not just raw popularity.

**Step 3 — Count.** 24 rounds of jittered ballot packets are tallied live,
each round nudging the running total for both sides — watch the chart move
round by round.

**Step 4 — Seats.** The final popular vote is converted into seats via the
**largest-remainder method**.

### 11. The Seat Map

Once counting finishes, results render as a hemicycle **seat map** — a
semicircle of colored dots, exactly like a real parliamentary results chart:

- **Saffron** = Incumbent seats
- **Red** = Opposition seats
- **Grey** = a small reserved Independents/fringe bloc (~3% of seats,
  minimum 1) — the chart never shows a 100% wipeout, mirroring how real
  results always leave a sliver for minor parties.
- Total seats defaults to **101**, matching the classic parliamentary
  hemicycle diagram — configurable per match.
- A "By party / By alliance" toggle switches the fill coloring.

### 12. Emergency Powers (the dictatorship mechanic)

If the Incumbent's seat share clears an **80% supermajority**, a red
**"Supermajority Cleared"** banner appears with a **Declare Emergency**
button (Incumbent-only).

Declaring Emergency:
- Sets `emergency_powers = true` on the match state (broadcast to both
  seats instantly).
- **Unlocks bypassing city zoning** — Industrial-only buildings (Port,
  Factory, Waste Plant) can now be placed directly on **Residential**
  zones, overriding the normal zoning rules entirely — literally
  overriding city planning like an authoritarian regime.
- Costs a small hit to public trust (authoritarian overreach isn't free).
- Is visible to both players via a persistent red banner on the City Map.

This is a deliberate strategic swing-for-the-fences mechanic: a landslide
election win converts directly into raw construction power the Opposition
can no longer contest through zoning.

### 13. Leaderboard

Ranked by **`owned_percent`** (share of simulated world GDP/influence),
alongside `gold` (treasury) and `max_troops` (a derived strength stat from
influence + infrastructure). Your own rank is always shown even if you're
outside the top 5. Four permanent AI "rival" nations (Brazil, Russia,
Siberia, Australia) seed the board so it's never empty on a fresh deploy.

### Glossary of city stats

| Stat | Meaning |
|---|---|
| **GDP** | Simulated city economic output. |
| **Treasury** | Available public funds — every construction, scheme, and grant draws from this. |
| **Public Trust** | Your most important election-adjacent stat — most Social buildings and schemes raise it, most Industrial buildings and any leaked scandal lower it. |
| **Unemployment** | Falls as buildings/schemes add `employment_delta`. |
| **Corruption Leaks** | Count of scandals the Opposition has successfully leaked. |
| **Pollution** | Rises with Industrial buildings, falls with Waste Plants / Power Grid / green schemes. |
| **Worker Unrest** | Rises with heavy-labor Industrial buildings, falls with Social spending. |
| **National Prestige** | Long-game stat, boosted most by Strategic buildings (Tech Park, Power Grid). |
| **Influence Points** | The Opposition's currency for Strikes and Audits. |
| **Audit Level** | How deep the Opposition can currently trace the corruption graph. |

---

## API Reference

Full interactive docs are auto-generated by FastAPI at `/docs` (Swagger UI)
and `/redoc` on your running backend. Endpoint groups:

| Prefix | Purpose |
|---|---|
| `/api/auth/*` | register, login, me, city rename, leaderboard |
| `/api/prajatantra/*` | single-player/sandbox versions of every core engine call (construction, strike, leak, grant, trade duel, scams, audits, elections, media, matchmaking, incumbency wave, emergency) |
| `/api/development/*` | building & scheme catalogs, build/launch, active schemes |
| `/api/match/*` | multiplayer: create, join, per-match REST actions (mirrors `/api/prajatantra/*` but scoped + broadcast), and `GET/WS /api/match/{match_id}` |
| `/health` | liveness + `database_connected` / `neo4j_connected` flags |

---

## Project Structure

```
PrajaTantra/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, CORS, lifespan (db connect + seed rivals)
│   │   ├── config.py               # env-driven settings
│   │   ├── db.py                   # asyncpg/Supabase pool wrapper
│   │   ├── routers/                # auth.py, prajatantra.py, development.py, match.py
│   │   ├── schemas/                # auth.py, prajatantra.py, development.py, match.py
│   │   └── services/                # every engine listed in Architecture above
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/page.tsx             # the entire game dashboard
│   │   ├── components/               # CityMap, SeatMap, CityDevelopment, AuthGate, MatchLobby, ...
│   │   └── lib/                      # api.ts, matchApi.ts, useMatchSocket.ts
│   ├── package.json
│   └── .env.example
├── database/postgres/                # 001/002/003 SQL migrations for Supabase/Postgres
└── docker-compose.yml
```

---

## Troubleshooting

- **"Failed to fetch" on register/login** → the backend didn't start. Check
  its logs for an import error (most common cause historically: `app/db.py`
  missing or misplaced) — `/health` should return `200` before the frontend
  can do anything.
- **CORS error in the browser console** → the frontend's origin isn't in the
  backend's allow-list. Set `FRONTEND_ORIGIN`/`FRONTEND_ORIGINS` on the
  backend to your exact deployed frontend URL and redeploy.
- **401/403 right after a successful login** → almost always a stale/invalid
  session token being checked against the wrong player id. Confirm the
  backend you're hitting is running the latest deployed commit.
- **WebSocket handshake fails with 403** → most commonly a stale `match_id`
  cached in the browser from before a backend restart (matches live in
  server memory only). Refreshing the page clears it automatically; the
  frontend also self-heals this on boot by validating the cached match
  against the server before reconnecting.
- **ED/CBI graph panel is empty** → expected until you've built a project
  with siphon% > 0 and then run an audit against it — it's not populated
  automatically.
- **`removeChild` React crash in the console** → known React 19 dev-mode
  issue triggered by browser extensions (Grammarly, translators, etc.)
  injecting DOM nodes outside React's control. Try an incognito window with
  extensions disabled.

## Contact
- Email: nnair7598@gmail.com
- LinkedIn: https://www.linkedin.com/in/nikhil-nair-809248286

## Thank You 
