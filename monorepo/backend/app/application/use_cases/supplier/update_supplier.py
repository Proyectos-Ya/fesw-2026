import logging
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

logger = logging.getLogger(__name__)

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
            raise SupplierValidationError(str(e.errors()[0]["msg"])) from e

        # Igual que al crear: el embedding va antes de persistir. Si se guardara
        # primero, un fallo del proveedor externo dejaría el texto nuevo en SQL
        # apuntando al vector viejo, y el matching seguiría respondiendo con el
        # perfil anterior sin que nada lo delatara.
        vectors = None
        if matching_changed:
            text = _build_supplier_text(updated)
            vectors = await self.embedding_service.embed([text])

        if vectors is None:
            return await self.repo.update(updated)

        # Misma regla que al crear: la edición queda pendiente, se reescribe el
        # vector y solo entonces se confirma. Se guarda el vector anterior para
        # devolverlo a Qdrant si el commit falla: sin eso, Qdrant describiría un
        # perfil que en SQL nunca llegó a existir.
        saved = await self.repo.stage_update(updated)
        try:
            previous_vector = await self.vector_repo.get_vector(saved.id)
            await self.vector_repo.upsert(saved.id, vectors[0])
        except Exception:
            await self.repo.rollback()
            raise

        try:
            await self.repo.commit()
        except Exception:
            await self._restore_vector(saved.id, previous_vector)
            await self.repo.rollback()
            raise

        return saved

    async def _restore_vector(
        self, supplier_id: UUID, previous_vector: list[float] | None
    ) -> None:
        # Compensación de mejor esfuerzo: si también falla, se registra y se deja
        # subir el error original del commit.
        try:
            if previous_vector is None:
                await self.vector_repo.delete(supplier_id)
            else:
                await self.vector_repo.upsert(supplier_id, previous_vector)
        except Exception:
            logger.exception(
                "No se pudo restaurar el vector del proveedor %s tras un commit fallido.",
                supplier_id,
            )
