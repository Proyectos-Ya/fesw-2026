from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.licitacion_repository import ILicitacionRepository
from app.domain.entities.licitacion import ItemLicitacion, Licitacion
from app.infrastructure.repositories.licitacion_model import LicitacionModel


class LicitacionRepository(ILicitacionRepository):

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_entity(self, model: LicitacionModel) -> Licitacion:
        data = model.model_dump()
        data["items"] = [ItemLicitacion(**item) for item in (data.get("items") or [])]
        return Licitacion(**data)

    def _to_model(self, entity: Licitacion) -> LicitacionModel:
        data = entity.model_dump()
        return LicitacionModel(**data)

    async def get_by_id(self, licitacion_id: UUID) -> Licitacion | None:
        model = await self.session.get(LicitacionModel, licitacion_id)
        return self._to_entity(model) if model else None

    async def get_by_ids(self, ids: list[UUID]) -> list[Licitacion]:
        result = await self.session.exec(
            select(LicitacionModel).where(LicitacionModel.id.in_(ids))
        )
        return [self._to_entity(m) for m in result.all()]

    async def get_by_codigo_externo(self, codigo_externo: str) -> Licitacion | None:
        result = await self.session.exec(
            select(LicitacionModel).where(
                LicitacionModel.codigo_externo == codigo_externo
            )
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def save(self, licitacion: Licitacion) -> Licitacion:
        model = self._to_model(licitacion)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)
