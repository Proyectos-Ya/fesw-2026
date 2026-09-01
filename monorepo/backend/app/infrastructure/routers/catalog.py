from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.schemas.catalog_schema import (
    CommuneOption,
    LocationCatalogResponse,
    ProvinceOption,
)
from app.domain.entities.user import User
from app.shared.comunas import CHILE_COMUNAS, CHILE_PROVINCIAS


def build_location_catalog() -> LocationCatalogResponse:
    """Arma el catálogo completo de provincias/comunas, sin tocar la base.

    `CHILE_PROVINCIAS`/`CHILE_COMUNAS` (`app/shared/comunas.py`) ya son la
    fuente de verdad usada para sembrar `provincia`/`comuna`: acá solo se
    envuelven con su id para que el frontend pueda mandarlo de vuelta como
    `province_id`/`commune_id` en `/tenders/search`, en vez de filtrar por
    nombre como región (56 provincias y 346 comunas no dan para hardcodear del
    lado del frontend como sí se hace con las 16 regiones).
    """
    return LocationCatalogResponse(
        provinces=[
            ProvinceOption(id=pid, name=name, region_name=region_name)
            for pid, (name, region_name) in CHILE_PROVINCIAS.items()
        ],
        communes=[
            CommuneOption(id=cid, name=name, province_name=province_name)
            for cid, (name, province_name) in CHILE_COMUNAS.items()
        ],
    )


def create_catalog_router(get_current_user: Callable) -> APIRouter:
    """Fábrica del router de catálogos. Requiere sesión iniciada, igual que el resto."""
    router = APIRouter(
        prefix="/catalogs",
        tags=["Catalogs"],
        dependencies=[Depends(get_current_user)],
    )

    @router.get("/locations", response_model=LocationCatalogResponse)
    async def get_location_catalog(
        _current_user: Annotated[User, Depends(get_current_user)],
    ) -> LocationCatalogResponse:
        """Provincias y comunas de Chile, con sus ids, para poblar selects."""
        return build_location_catalog()

    return router
