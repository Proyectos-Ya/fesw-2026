from pydantic import ValidationError

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.schemas.supplier_schema import CreateSupplierSchema
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import (
    SupplierAlreadyExists,
    SupplierValidationError,
)


class CreateSupplierUseCase:
    def __init__(
        self,
        repo: ISupplierRepository,
        vector_repo: ISupplierVectorRepository,
    ):
        self.repo = repo
        self.vector_repo = vector_repo

    async def execute(self, data: CreateSupplierSchema) -> Supplier:
        # Primero valida el formato — si es inválido no tocas la BD
        try:
            supplier = Supplier(**data.model_dump())
        except ValidationError as e:
            raise SupplierValidationError(str(e.errors()[0]["msg"]))

        # Luego consulta la BD solo si el RUT es válido
        existing = await self.repo.get_by_rut(data.rut)
        if existing:
            raise SupplierAlreadyExists(data.rut)

        # Guarda el proveedor en PostgreSQL
        saved_supplier = await self.repo.save(supplier)

        # TODO: generar embedding con EmbeddingService e indexar en Qdrant
        # Embedding hardcodeado para pruebas — reemplazar con EmbeddingService
        embedding = [0.1] * 1024
        self.vector_repo.upsert(saved_supplier.id, embedding)

        return saved_supplier
