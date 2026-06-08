from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.resultado_matching_repository import (
    IResultadoMatchingRepository,
)
from app.domain.entities.resultado_matching import ResultadoMatching
from app.infrastructure.repositories.resultado_matching_model import (
    ResultadoMatchingModel,
)


class ResultadoMatchingRepository(IResultadoMatchingRepository):

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_entity(self, model: ResultadoMatchingModel) -> ResultadoMatching:
        return ResultadoMatching(**model.model_dump())

    def _to_model(self, entity: ResultadoMatching) -> ResultadoMatchingModel:
        return ResultadoMatchingModel(**entity.model_dump())

    async def save_bulk(self, resultados: list[ResultadoMatching]) -> None:
        for resultado in resultados:
            self.session.add(self._to_model(resultado))
        await self.session.commit()

    async def get_by_proveedor_and_licitacion(
        self,
        proveedor_id: UUID,
        licitacion_id: UUID,
    ) -> ResultadoMatching | None:
        result = await self.session.exec(
            select(ResultadoMatchingModel).where(
                ResultadoMatchingModel.proveedor_id == proveedor_id,
                ResultadoMatchingModel.licitacion_id == licitacion_id,
            )
        )
        model = result.first()
        return self._to_entity(model) if model else None
