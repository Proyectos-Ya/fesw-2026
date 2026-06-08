from fastapi import Depends, FastAPI, Request
from sqlmodel.ext.asyncio.session import AsyncSession

# Único lugar donde se importa la implementación concreta del repositorio
from app.infrastructure.db import get_session
from app.infrastructure.repositories.supplier_repository import SupplierRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import SupplierVectorRepository
from app.infrastructure.repositories.qdrant_supplier_repository import QdrantSupplierRepository

from app.application.repositories.tender_repository import ITenderRepository
from app.infrastructure.repositories.tender_repository import TenderRepository

from app.infrastructure.routers.router import create_router


def get_supplier_repo(
    session: AsyncSession = Depends(get_session),
) -> ISupplierRepository:
    # Crea el repositorio concreto con la sesión de BD por petición
    return SupplierRepository(session)

def get_supplier_vector_repo(request: Request) -> SupplierVectorRepository:
    # Reutiliza el cliente Qdrant inicializado en el lifespan
    return QdrantSupplierRepository(request.app.state.qdrant_client)

def get_tender_repo(
    session: AsyncSession = Depends(get_session),
) -> ITenderRepository:
    # Crea el repositorio concreto de licitaciones con la sesión de BD
    return TenderRepository(session)


def bootstrap(app: FastAPI) -> None:
    router = create_router(
        get_supplier_repo=get_supplier_repo,
        get_supplier_vector_repo=get_supplier_vector_repo, 
    )
    app.include_router(router)