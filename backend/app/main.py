from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.config import settings
from app.routers import auth, development, match, prajatantra
from app.services.auth_engine import auth_engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.connect()
    if db.is_configured():
        await auth_engine.seed_rivals()
    yield
    await db.disconnect()


app = FastAPI(
    title=settings.api_title,
    version="0.1.0",
    description=(
        "Simulation APIs for governance, graph audits, elections, media, "
        "matchmaking, auth, leaderboards, and city development."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(prajatantra.router)
app.include_router(auth.router)
app.include_router(development.router)
app.include_router(match.router)


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": "prajatantra",
        "database_connected": db.is_configured(),
        "neo4j_connected": settings.neo4j_enabled,
    }
