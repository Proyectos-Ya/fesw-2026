from app.application.repositories.supplier_repository import ISupplierRepository
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import SupplierAlreadyExists, SupplierValidationError
from app.application.schemas.supplier_schema import CreateSupplierSchema
from pydantic import ValidationError

class CreateSupplierUseCase:

    def __init__(self, repo: ISupplierRepository):
        self.repo = repo

    async def execute(self, data: CreateSupplierSchema) -> Supplier:
    # Primero valida el formato — si es inválido no tocas la BD
        try:
            proveedor = Supplier(**data.model_dump())
        except ValidationError as e:
            raise SupplierValidationError(str(e.errors()[0]["msg"])) 
    # Luego consulta la BD solo si el RUT es válido
        existing = await self.repo.get_by_rut(data.rut)
        if existing:
            raise SupplierAlreadyExists(data.rut)

        return await self.repo.save(proveedor)