# PrajaTantra — Election Seat Map, 24-Round Counting & Emergency Powers

## What's new

### 1. Hemicycle seat map (matches your reference screenshot)
- New `SeatMap.tsx` component: a semicircle of coloured dots grouped by
  party (Incumbent / Independents / Opposition), a big seat-count in the
  centre, legend, and a "By party / By alliance" toggle — same chrome as
  the screenshot you sent.
- Backend now converts the popular vote into seats via the **largest
  remainder method** (`allocate_seats()` in `incumbency_engine.py`),
  reserving a small ~3% independents/fringe bloc so the chart never shows
  a 100% wipeout. Default: **101 total seats** (configurable via
  `total_seats` in the request).

### 2. Election schedule: every 3 days, 2-hour counting, 24 rounds
- `TenRoundSimulationResponse` now runs **24 counting rounds** instead of
  10 (`COUNTING_ROUNDS = 24` in `incumbency_engine.py`).
- New flavour fields echoed back for the UI: `election_cycle_days: 3`,
  `counting_duration_hours: 2`, `total_rounds: 24`.
- The counting chart (`TenRoundChart`) and its x-axis now scale to 24
  rounds automatically (labels every 3rd round to avoid crowding).

### 3. Manifesto judged by AI (HuggingFace, with offline fallback)
- New `backend/app/services/manifesto_ai.py`: sends the manifesto to a
  HuggingFace zero-shot classification model (`facebook/bart-large-mnli`
  by default) with labels *credible funded plan* / *vague populist
  promise* / *corrupt or unfunded promise*, and folds the result into
  the practicality score.
- **No API token or no network?** It automatically falls back to a
  deterministic keyword heuristic — nothing breaks, it just won't be
  "real AI" until you set a token.
- To enable live AI judging, set one of these env vars on the backend:
  ```
  HUGGINGFACE_API_TOKEN=hf_xxx...
  # optional override:
  HF_MANIFESTO_MODEL=facebook/bart-large-mnli
  ```
- The election breakdown now includes `manifesto_ai_score` and
  `manifesto_ai_source` ("huggingface" or "heuristic-fallback"), shown
  in the Election Panel UI.

### 4. Seats driven by manifesto + anti-incumbency + development
- `manifesto_trust_score` (the `trust_score` from `/elections/grade` —
  which itself blends manifesto AI-judging + rhetoric + city
  performance/development delivery) now nudges the incumbency wave
  before seats are allocated. The frontend runs grading **before** the
  counting simulation and passes the trust score through, so a strong,
  well-funded manifesto and real development actually swing seats, not
  just the popular vote.

### 5. Emergency powers at >80% seats (dictatorship mechanic)
- If the Incumbent's seat share clears **80%** (`EMERGENCY_THRESHOLD_PCT`
  in `incumbency_engine.py`), the simulation response sets
  `emergency_eligible: true` and the Election Panel shows a red
  "Supermajority Cleared" banner with a **Declare Emergency** button
  (Incumbent-only).
- New endpoints:
  - `POST /api/prajatantra/emergency/declare` (single-player)
  - `POST /api/match/{match_id}/emergency/declare` (multiplayer,
    broadcasts the new state to both seats over WebSocket)
- Declaring Emergency sets `emergency_powers: true` on `SovereignState`
  and drops public trust slightly (authoritarian overreach has a cost).
- **Gameplay effect:** on the City Map, Industrial-only buildings
  (Factory, Port, Waste Plant) can now be placed directly on
  **Residential** zones, bypassing normal zoning — literally overriding
  city planning like a dictatorship. A red banner appears on the map
  while Emergency is active.

## Files touched
```
backend/app/schemas/prajatantra.py       # SeatResult, Emergency*, scheduling fields
backend/app/services/incumbency_engine.py # 24 rounds, allocate_seats(), emergency check
backend/app/services/manifesto_ai.py      # NEW — HuggingFace judge + heuristic fallback
backend/app/services/election_engine.py   # wires manifesto_ai into practicality score
backend/app/services/sovereign_engine.py  # emergency_powers flag + declare_emergency()
backend/app/routers/prajatantra.py        # POST /emergency/declare
backend/app/routers/match.py              # POST /{match_id}/emergency/declare
frontend/src/lib/api.ts                   # SeatResult, Emergency*, updated sim types
frontend/src/components/SeatMap.tsx        # NEW — hemicycle chart component
frontend/src/components/CityMap.tsx       # emergency zoning bypass + banner
frontend/src/app/page.tsx                 # wiring: seat map, emergency banner/button, 24-round chart
```

## Setup reminder
This zip excludes `node_modules` and the Python `.venv` to keep it small.
Before running:
```bash
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
```
