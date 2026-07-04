"""
City Development routes for PrajaTantra.

Mounted separately from the main `prajatantra` and `auth` routers so
existing endpoints are never touched.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.development import (
    ActiveScheme,
    BuildFromCatalogRequest,
    BuildFromCatalogResponse,
    BuildingCatalogResponse,
    LaunchSchemeRequest,
    LaunchSchemeResponse,
    SchemeCatalogResponse,
)
from app.services.development_engine import development_engine

router = APIRouter(prefix="/api/development", tags=["development"])


@router.get("/buildings/catalog", response_model=BuildingCatalogResponse)
async def building_catalog() -> BuildingCatalogResponse:
    return development_engine.building_catalog()


@router.post("/buildings/build", response_model=BuildFromCatalogResponse)
async def build_from_catalog(payload: BuildFromCatalogRequest) -> BuildFromCatalogResponse:
    try:
        return await development_engine.build_from_catalog(payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/schemes/catalog", response_model=SchemeCatalogResponse)
async def scheme_catalog() -> SchemeCatalogResponse:
    return development_engine.scheme_catalog()


@router.post("/schemes/launch", response_model=LaunchSchemeResponse)
async def launch_scheme(payload: LaunchSchemeRequest) -> LaunchSchemeResponse:
    try:
        return development_engine.launch_scheme(payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/schemes/active", response_model=list[ActiveScheme])
async def active_schemes() -> list[ActiveScheme]:
    return development_engine.active_schemes()