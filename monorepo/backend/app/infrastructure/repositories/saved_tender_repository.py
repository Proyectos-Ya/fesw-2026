from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.saved_tender_repository import ISavedTenderRepository
from app.domain.entities.saved_tender import SavedTender
from app.infrastructure.repositories.saved_tender_model import SavedTenderModel


class SavedTenderRepository(ISavedTenderRepository):
    """Implementación de ISavedTenderRepository con SQLModel sobre PostgreSQL."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: SavedTenderModel) -> SavedTender:
        """Convierte un modelo de base de datos a una entidad de dominio."""
        return SavedTender(
            id=model.id,
            user_id=model.user_id,
            tender_id=model.tender_id,
            saved_at=model.saved_at,
        )

    def _to_model(self, entity: SavedTender) -> SavedTenderModel:
        """Convierte una entidad de dominio a un modelo de base de datos."""
        return SavedTenderModel(
            id=entity.id,
            user_id=entity.user_id,
            tender_id=entity.tender_id,
            saved_at=entity.saved_at,
        )

    async def get_by_user_id(self, user_id: UUID) -> list[SavedTender]:
        """Obtiene todas las licitaciones que el usuario marcó como de interés."""
        result = await self.session.exec(
            select(SavedTenderModel).where(SavedTenderModel.user_id == user_id)
        )
        return [self._to_entity(m) for m in result.all()]

    async def _get_model(
        self, user_id: UUID, tender_id: UUID
    ) -> SavedTenderModel | None:
        result = await self.session.exec(
            select(SavedTenderModel).where(
                SavedTenderModel.user_id == user_id,
                SavedTenderModel.tender_id == tender_id,
            )
        )
        return result.first()

    async def get(self, user_id: UUID, tender_id: UUID) -> SavedTender | None:
        """Obtiene la marca de interés de un usuario sobre una licitación, si existe."""
        model = await self._get_model(user_id, tender_id)
        return self._to_entity(model) if model else None

    async def save(self, saved_tender: SavedTender) -> SavedTender:
        """Persiste una nueva marca de interés."""
        model = self._to_model(saved_tender)
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def delete(self, user_id: UUID, tender_id: UUID) -> bool:
        """Elimina la marca de interés. Retorna False si no existía."""
        model = await self._get_model(user_id, tender_id)
        if model is None:
            return False
        await self.session.delete(model)
        await self.session.commit()
        return True
