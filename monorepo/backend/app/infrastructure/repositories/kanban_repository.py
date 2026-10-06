from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.kanban_repository import (
    IKanbanColumnRepository,
    IKanbanCardRepository,
)
from app.domain.entities.kanban import KanbanCard, KanbanColumn
from app.infrastructure.repositories.kanban_model import KanbanCardModel, KanbanColumnModel

class KanbanColumnRepository(IKanbanColumnRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: KanbanColumnModel) -> KanbanColumn:
        return KanbanColumn(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            position=model.position,
            created_at=model.created_at,
        )

    def _to_model(self, entity: KanbanColumn) -> KanbanColumnModel:
        return KanbanColumnModel(
            id=entity.id,
            user_id=entity.user_id,
            name=entity.name,
            position=entity.position,
            created_at=entity.created_at,
        )

    async def get_by_user_id(self, user_id: UUID) -> list[KanbanColumn]:
        result = await self.session.exec(
            select(KanbanColumnModel).where(KanbanColumnModel.user_id == user_id)
        )
        return [self._to_entity(m) for m in result.all()]

    async def get(self, column_id: UUID, user_id: UUID) -> KanbanColumn | None:
        result = await self.session.exec(
            select(KanbanColumnModel).where(
                KanbanColumnModel.id == column_id,
                KanbanColumnModel.user_id == user_id,
            )
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def create(self, column: KanbanColumn) -> KanbanColumn:
        model = self._to_model(column)
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def update(self, column: KanbanColumn) -> KanbanColumn:
        result = await self.session.exec(
            select(KanbanColumnModel).where(KanbanColumnModel.id == column.id)
        )
        model = result.one()
        model.name = column.name
        model.position = column.position
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def delete(self, column_id: UUID, user_id: UUID) -> bool:
        result = await self.session.exec(
            select(KanbanColumnModel).where(
                KanbanColumnModel.id == column_id,
                KanbanColumnModel.user_id == user_id,
            )
        )
        model = result.first()
        if model is None:
            return False
        await self.session.delete(model)
        await self.session.commit()
        return True

    async def count_cards(self, column_id: UUID) -> int:
        result = await self.session.exec(
            select(KanbanCardModel).where(KanbanCardModel.column_id == column_id)
        )
        return len(result.all())


class KanbanCardRepository(IKanbanCardRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: KanbanCardModel) -> KanbanCard:
        return KanbanCard(
            id=model.id,
            user_id=model.user_id,
            tender_id=model.tender_id,
            column_id=model.column_id,
            position=model.position,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: KanbanCard) -> KanbanCardModel:
        return KanbanCardModel(
            id=entity.id,
            user_id=entity.user_id,
            tender_id=entity.tender_id,
            column_id=entity.column_id,
            position=entity.position,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def get_by_user_id(self, user_id: UUID) -> list[KanbanCard]:
        result = await self.session.exec(
            select(KanbanCardModel).where(KanbanCardModel.user_id == user_id)
        )
        return [self._to_entity(m) for m in result.all()]

    async def get(self, user_id: UUID, tender_id: UUID) -> KanbanCard | None:
        result = await self.session.exec(
            select(KanbanCardModel).where(
                KanbanCardModel.user_id == user_id,
                KanbanCardModel.tender_id == tender_id,
            )
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def create(self, card: KanbanCard) -> KanbanCard:
        model = self._to_model(card)
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def update(self, card: KanbanCard) -> KanbanCard:
        result = await self.session.exec(
            select(KanbanCardModel).where(KanbanCardModel.id == card.id)
        )
        model = result.one()
        model.column_id = card.column_id
        model.position = card.position
        model.updated_at = card.updated_at
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def delete(self, user_id: UUID, tender_id: UUID) -> bool:
        result = await self.session.exec(
            select(KanbanCardModel).where(
                KanbanCardModel.user_id == user_id,
                KanbanCardModel.tender_id == tender_id,
            )
        )
        model = result.first()
        if model is None:
            return False
        await self.session.delete(model)
        await self.session.commit()
        return True