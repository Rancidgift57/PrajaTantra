"""
Auth + leaderboard routes for PrajaTantra.

Mounted separately from the main `prajatantra` router so the existing
simulation endpoints are never touched.
"""
from fastapi import APIRouter, HTTPException, Query

from app.schemas.auth import (
    AuthResponse,
    LeaderboardResponse,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    RenameCityRequest,
    RenameCityResponse,
)
from app.services.auth_engine import auth_engine

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest) -> AuthResponse:
    try:
        return await auth_engine.register(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    try:
        return await auth_engine.login(payload)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/me", response_model=MeResponse)
async def me(token: str = Query(..., description="Bearer token issued at login/register")) -> MeResponse:
    try:
        return MeResponse(player=await auth_engine.me(token))
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/city/rename", response_model=RenameCityResponse)
async def rename_city(payload: RenameCityRequest) -> RenameCityResponse:
    try:
        return await auth_engine.rename_city(payload)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def leaderboard(
    token: str | None = Query(default=None, description="Optional viewer token to surface 'your rank'"),
    limit: int = Query(default=5, ge=1, le=50),
) -> LeaderboardResponse:
    return await auth_engine.leaderboard(viewer_token=token, limit=limit)