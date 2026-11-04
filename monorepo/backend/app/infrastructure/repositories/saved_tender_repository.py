from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.saved_tender_repository import (
    ISavedTenderRepository,
)
from app.domain.entities.saved_tender import SavedTender
from app.infrastructure.repositories.saved_tender_model import SavedTenderModel


class SavedTenderRepository(ISavedTenderRepository):
    """Implementación de ISavedTenderRepository con SQLModel sobre Postgres.

    HU-18: scoping por workspace (`supplier_id`); `save` es idempotente a
    nivel de DB vía `INSERT ... ON CONFLICT DO NOTHING` sobre
    `(supplier_id, tender_id)`.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: SavedTenderModel) -> SavedTender:
        return SavedTender(
            id=model.id,
            supplier_id=model.supplier_id,
            user_id=model.user_id,
            tender_id=model.tender_id,
            saved_at=model.saved_at,
        )

    async def get_by_supplier_id(self, supplier_id: UUID) -> list[SavedTender]:
        result = await self.session.exec(
            select(SavedTenderModel).where(
                SavedTenderModel.supplier_id == supplier_id
            )
        )
        return [self._to_entity(m) for m in result.all()]

    async def _get_model(
        self, supplier_id: UUID, tender_id: UUID
    ) -> SavedTenderModel | None:
        result = await self.session.exec(
            select(SavedTenderModel).where(
                SavedTenderModel.supplier_id == supplier_id,
                SavedTenderModel.tender_id == tender_id,
            )
        )
        return result.first()

    async def get(
        self, supplier_id: UUID, tender_id: UUID
    ) -> SavedTender | None:
        model = await self._get_model(supplier_id, tender_id)
        return self._to_entity(model) if model else None

    async def save(self, saved_tender: SavedTender) -> SavedTender:
        # Idempotencia a nivel de workspace: si (supplier_id, tender_id) ya
        # existe, no insertamos nada y devolvemos la fila existente. Resuelve
        # el caso de dos miembros que piden guardar la misma licitación casi
        # simultáneamente sin ejecutar dos escrituras.
        stmt = (
            pg_insert(SavedTenderModel.__table__)
            .values(
                id=saved_tender.id,
                supplier_id=saved_tender.supplier_id,
                user_id=saved_tender.user_id,
                tender_id=saved_tender.tender_id,
                saved_at=saved_tender.saved_at,
            )
            .on_conflict_do_nothing(
                index_elements=["supplier_id", "tender_id"]
            )
        )
        await self.session.exec(stmt)  # type: ignore[call-overload]
        await self.session.commit()

        existing = await self._get_model(
            saved_tender.supplier_id, saved_tender.tender_id
        )
        # existing no debería ser None tras el insert+commit; si lo es, dejamos
        # explotar la excepción porque es una incoherencia que debe loguearse.
        assert existing is not None
        return self._to_entity(existing)

    async def delete(self, supplier_id: UUID, tender_id: UUID) -> bool:
        model = await self._get_model(supplier_id, tender_id)
        if model is None:
            return False
        await self.session.delete(model)
        await self.session.commit()
        return True
