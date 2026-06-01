from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.proveedor_repository import IProveedorRepository
from app.application.useCases.obtener_proveedor import ObtenerProveedorUseCase
from app.domain.entities.proveedor import Proveedor
from app.domain.errors.proveedor_errors import ProveedorNoEncontrado
from app.infrastructure.db import get_session
from app.infrastructure.repositories.proveedor_repository import ProveedorRepository
from app.application.useCases.crear_proveedor import CrearProveedorUseCase
from app.domain.errors.proveedor_errors import ProveedorYaExiste
from app.domain.models.proveedor_schema import CrearProveedorSchema

router = APIRouter(prefix="/proveedores", tags=["proveedores"])


def get_proveedor_repo(
    session: AsyncSession = Depends(get_session),
) -> IProveedorRepository:
    return ProveedorRepository(session)

@router.post("/", response_model=Proveedor, status_code=status.HTTP_201_CREATED)
async def crear_proveedor(
    data: CrearProveedorSchema,
    repo: IProveedorRepository = Depends(get_proveedor_repo),
):
    try:
        return await CrearProveedorUseCase(repo).execute(data)
    except ProveedorYaExiste as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))



@router.get("/{rut}", response_model=Proveedor)
async def obtener_proveedor(
    rut: str,
    repo: IProveedorRepository = Depends(get_proveedor_repo),
):
    try:
        return await ObtenerProveedorUseCase(repo).execute(rut)
    except ProveedorNoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e))