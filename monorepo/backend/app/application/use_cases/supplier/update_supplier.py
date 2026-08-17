from uuid import UUID

from pydantic import ValidationError

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.schemas.supplier_schema import UpdateSupplierSchema
from app.application.services.embedding_service import IEmbeddingService
from app.application.use_cases.supplier.create_supplier import _build_supplier_text
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import (
    SupplierNotFoundForUser,
    SupplierValidationError,
)
from app.shared.datetime_utils import utc_now_naive

# Campos que alimentan el texto del embedding: si cambian, hay que re-indexar
_MATCHING_FIELDS = {"legal_name", "trade_name", "description", "sectors", "keywords"}


class UpdateSupplierUseCase:
    """Edita la empresa del usuario autenticado (actualización parcial)."""

    def __init__(
        self,
        repo: ISupplierRepository,
        vector_repo: ISupplierVectorRepository,
        embedding_service: IEmbeddingService,
    ):
        self.repo = repo
        self.vector_repo = vector_repo
        self.embedding_service = embedding_service

    async def execute(self, user_id: UUID, data: UpdateSupplierSchema) -> Supplier:
        supplier = await self.repo.get_by_user_id(user_id)
        if supplier is None:
            raise SupplierNotFoundForUser(user_id)

        updates = data.model_dump(exclude_unset=True)
        # Descarta campos enviados con el mismo valor actual
        updates = {k: v for k, v in updates.items() if getattr(supplier, k) != v}
        if not updates:
            return supplier

        now = utc_now_naive()
        matching_changed = bool(_MATCHING_FIELDS & updates.keys())

        try:
            updated = Supplier(
                **{
                    **supplier.model_dump(),
                    **updates,
                    "updated_at": now,
                    "profile_changed_at": now
                    if matching_changed
                    else supplier.profile_changed_at,
                }
            )
        except ValidationError as e:
            raise SupplierValidationError(str(e.errors()[0]["msg"]))

        saved = await self.repo.update(updated)

        if matching_changed:
            text = _build_supplier_text(saved)
            vectors = await self.embedding_service.embed([text])
            self.vector_repo.upsert(saved.id, vectors[0])

        return saved
