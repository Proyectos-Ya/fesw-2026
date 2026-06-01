from fastapi import Depends, FastAPI
from sqlmodel.ext.asyncio.session import AsyncSession

# Único lugar donde se importa la implementación concreta del repositorio
from app.infrastructure.db import get_session
from app.infrastructure.repositories.supplier_repository import SupplierRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from monorepo.backend.app.infrastructure.routers.router import create_router


def get_supplier_repo(
    session: AsyncSession = Depends(get_session),
) -> ISupplierRepository:
    # Crea el repositorio concreto con la sesión de BD por petición
    return SupplierRepository(session)


def bootstrap(app: FastAPI) -> None:
    """Composition root: conecta implementaciones con interfaces."""
    router = create_router(
        get_supplier_repo=get_supplier_repo,
    )
    app.include_router(router)