# Prajatantra

Prajatantra is a web-based political-economic simulation where elected players govern through budgets, opponents investigate corruption through graph forensics, and elections are scored from city performance, manifestos, and speeches.

This repo contains a first playable vertical slice:

- FastAPI backend for governance, layered scam generation, depth-bound audits, election scoring, AI media headlines, and ideological matchmaking.
- Next.js dashboard UI for the Incumbent and Opposition loops.
- Neo4j-ready corruption graph service with an in-memory fallback for local play.

## Quick Start

Fastest path:

```bash
docker compose up --build
```

Then open:

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/health
- Neo4j browser: http://localhost:7474

Default docker credentials:

- Neo4j user: `neo4j`
- Neo4j password: `password`
- PostgreSQL user/password/db: `prajatantra`

## Manual Setup

Backend:

```bash
cd backend
copy .env.example .env
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

Without Neo4j, the backend still runs using the in-memory graph store so the audit loop remains playable.

## Deploy

Recommended production layout:

1. Deploy `frontend/` to Vercel or Netlify.
2. Deploy `backend/` as a container on Render, Railway, Fly.io, or a VM.
3. Use managed PostgreSQL, Neo4j Aura, and Redis, then set the backend environment variables to those hosted services.

If you want one-container self-hosting, use Docker Compose on a VM:

```bash
docker compose up -d --build
```

Production environment variables:

- `BACKEND`: `FRONTEND_ORIGIN`, `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
- `FRONTEND`: `NEXT_PUBLIC_API_BASE`

## Notes

- The backend has a working in-memory graph fallback for local play.
- The database schemas in `database/` are ready to run against PostgreSQL and Neo4j.
- `frontend/src/app/page.tsx` is the main playable dashboard.
