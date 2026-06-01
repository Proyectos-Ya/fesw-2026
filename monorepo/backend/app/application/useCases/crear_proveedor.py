from app.application.repositories.proveedor_repository import IProveedorRepository
from app.domain.entities.proveedor import Proveedor
from app.domain.errors.proveedor_errors import ProveedorYaExiste
from app.domain.models.proveedor_schema import CrearProveedorSchema


class CrearProveedorUseCase:

    def __init__(self, repo: IProveedorRepository):
        self.repo = repo

    async def execute(self, data: CrearProveedorSchema) -> Proveedor:
        existente = await self.repo.get_by_rut(data.rut)
        if existente:
            raise ProveedorYaExiste(data.rut)

        proveedor = Proveedor(**data.model_dump())
        return await self.repo.save(proveedor)