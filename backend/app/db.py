"""
db.py
-----
Thin asyncpg connection-pool wrapper for Supabase/Postgres.

One pool is created at FastAPI startup (see main.py's lifespan) and shared
by every service that needs persistence (currently just AuthEngine). Reads
`DATABASE_URL` from the environment — get this from Supabase:
  Project Settings → Database → Connection string → "Transaction pooler"
  (port 6543) is recommended for serverless-style hosts like Render/Railway,
  since it doesn't hold long-lived idle connections the way the direct
  connection (port 5432) does.

Example:
  postgresql://postgres.xxxxxxxxxxxx:[email protected]:6543/postgres
"""
from __future__ import annotations

import os

import asyncpg

_pool: asyncpg.Pool | None = None


def is_configured() -> bool:
    return bool(os.getenv("DATABASE_URL"))


async def connect() -> None:
    global _pool
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # No DATABASE_URL set — services fall back to in-memory stores.
        # This keeps `docker compose up` / local dev working with zero DB
        # setup, exactly like before.
        return
    _pool = await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=10,
        # Supabase's pooler (pgbouncer, transaction mode) does not support
        # prepared statements across pooled connections — disable asyncpg's
        # statement cache to avoid "prepared statement already exists"
        # errors under load.
        statement_cache_size=0,
    )


async def disconnect() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError(
            "Postgres pool not initialized — either DATABASE_URL is unset "
            "(intentional: running in in-memory mode) or connect() wasn't "
            "awaited at startup. Callers should check db.is_configured() "
            "before calling db.pool()."
        )
    return _pool
