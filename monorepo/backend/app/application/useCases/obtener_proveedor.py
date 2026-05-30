from app.application.repositories.proveedor_repository import IProveedorRepository
from app.domain.entities.proveedor import Proveedor
from app.domain.errors.proveedor_errors import ProveedorNoEncontrado


class ObtenerProveedorUseCase:

    def __init__(self, repo: IProveedorRepository):
        self.repo = repo

    async def execute(self, rut: str) -> Proveedor:
        proveedor = await self.repo.get_by_rut(rut)
        if not proveedor:
            raise ProveedorNoEncontrado(rut)
        return proveedor