from datetime import datetime
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
            color=model.color,
            created_at=model.created_at,
        )

    def _to_model(self, entity: KanbanColumn) -> KanbanColumnModel:
        return KanbanColumnModel(
            id=entity.id,
            user_id=entity.user_id,
            name=entity.name,
            position=entity.position,
            color=entity.color,
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
        model.color = column.color
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
        # Las archivadas no aparecen en el tablero activo, así que tampoco
        # cuentan para el contador de la columna (HdU 10, CA4).
        result = await self.session.exec(
            select(KanbanCardModel).where(
                KanbanCardModel.column_id == column_id,
                KanbanCardModel.archived_at.is_(None),  # type: ignore[union-attr]
            )
        )
        return len(result.all())

    async def reorder(
        self, user_id: UUID, ordered_ids: list[UUID]
    ) -> list[KanbanColumn]:
        result = await self.session.exec(
            select(KanbanColumnModel).where(KanbanColumnModel.user_id == user_id)
        )
        models = {m.id: m for m in result.all()}
        for idx, col_id in enumerate(ordered_ids):
            model = models.get(col_id)
            if model is None:
                continue
            model.position = idx
            self.session.add(model)
        await self.session.commit()
        reordered = [models[cid] for cid in ordered_ids if cid in models]
        return [self._to_entity(m) for m in reordered]


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
            board_entered_at=model.board_entered_at,
            archived_at=model.archived_at,
            archived_reason=model.archived_reason,
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
            board_entered_at=entity.board_entered_at,
            archived_at=entity.archived_at,
            archived_reason=entity.archived_reason,
        )

    async def get_by_user_id(self, user_id: UUID) -> list[KanbanCard]:
        # Oculta las archivadas: el tablero activo nunca las muestra (CA4).
        result = await self.session.exec(
            select(KanbanCardModel).where(
                KanbanCardModel.user_id == user_id,
                KanbanCardModel.archived_at.is_(None),  # type: ignore[union-attr]
            )
        )
        return [self._to_entity(m) for m in result.all()]

    async def get(self, user_id: UUID, tender_id: UUID) -> KanbanCard | None:
        # Devuelve solo la tarjeta activa. Si la licitación está archivada,
        # el flujo de "agregar al tablero" la trata como ausente y crea una
        # nueva (el índice único parcial lo permite).
        result = await self.session.exec(
            select(KanbanCardModel).where(
                KanbanCardModel.user_id == user_id,
                KanbanCardModel.tender_id == tender_id,
                KanbanCardModel.archived_at.is_(None),  # type: ignore[union-attr]
            )
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def get_by_id(self, card_id: UUID, user_id: UUID) -> KanbanCard | None:
        result = await self.session.exec(
            select(KanbanCardModel).where(
                KanbanCardModel.id == card_id,
                KanbanCardModel.user_id == user_id,
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
        # El soft-delete y la restauración viajan por `update`: lo que mueve
        # entre tablero activo e historial es `archived_at`/`archived_reason`.
        # `board_entered_at` también se actualiza: solo cambia al restaurar,
        # para que el reloj de 90 días empiece de nuevo (regla de negocio
        # discutida en el plan).
        model.board_entered_at = card.board_entered_at
        model.archived_at = card.archived_at
        model.archived_reason = card.archived_reason
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def delete(self, user_id: UUID, tender_id: UUID) -> bool:
        # Borra la fila activa (si existe). Con soft-delete, los flujos de
        # usuario llegan a archive/restore; este método sigue acá para quitar
        # la fila sin dejar historial, por si lo pide otro flujo.
        result = await self.session.exec(
            select(KanbanCardModel).where(
                KanbanCardModel.user_id == user_id,
                KanbanCardModel.tender_id == tender_id,
                KanbanCardModel.archived_at.is_(None),  # type: ignore[union-attr]
            )
        )
        model = result.first()
        if model is None:
            return False
        await self.session.delete(model)
        await self.session.commit()
        return True

    async def list_archived(self, user_id: UUID) -> list[KanbanCard]:
        result = await self.session.exec(
            select(KanbanCardModel)
            .where(
                KanbanCardModel.user_id == user_id,
                KanbanCardModel.archived_at.is_not(None),  # type: ignore[union-attr]
            )
            .order_by(KanbanCardModel.archived_at.desc())  # type: ignore[union-attr]
        )
        return [self._to_entity(m) for m in result.all()]

    async def list_archived_with_context(
        self, user_id: UUID
    ) -> list[tuple[KanbanCard, str, str, str]]:
        # Importes locales para no forzar cargas cruzadas entre repositorios.
        from app.infrastructure.repositories.tender_model import TenderModel

        result = await self.session.exec(
            select(KanbanCardModel, KanbanColumnModel, TenderModel)
            .join(
                KanbanColumnModel,
                KanbanColumnModel.id == KanbanCardModel.column_id,
            )
            .join(TenderModel, TenderModel.id == KanbanCardModel.tender_id)
            .where(
                KanbanCardModel.user_id == user_id,
                KanbanCardModel.archived_at.is_not(None),  # type: ignore[union-attr]
            )
            .order_by(KanbanCardModel.archived_at.desc())  # type: ignore[union-attr]
        )
        rows = result.all()
        return [
            (self._to_entity(card), column.name, tender.code, tender.name)
            for (card, column, tender) in rows
        ]

    async def list_candidates_for_auto_archive(
        self, cutoff: datetime
    ) -> list[KanbanCard]:
        result = await self.session.exec(
            select(KanbanCardModel).where(
                KanbanCardModel.archived_at.is_(None),  # type: ignore[union-attr]
                KanbanCardModel.board_entered_at < cutoff,
            )
        )
        return [self._to_entity(m) for m in result.all()]