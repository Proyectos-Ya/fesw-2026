from typing import Callable
from fastapi import APIRouter

from app.infrastructure.routers.health import create_health_router
from app.infrastructure.routers.supplier import create_supplier_router


def create_router(get_supplier_repo: Callable) -> APIRouter:
    """Ensambla todos los sub-routers con sus dependencias inyectadas."""
    root = APIRouter()

    root.include_router(create_health_router(), tags=["Health"])
    root.include_router(create_supplier_router(get_supplier_repo=get_supplier_repo), tags=["Suppliers"])

    return root