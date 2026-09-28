from uuid import UUID

from sqlmodel import col, delete, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.domain.entities.matching_result import MatchingResult
from app.infrastructure.repositories.matching_result_model import MatchingResultModel


class MatchingResultRepository(IMatchingResultRepository):
    """Implementación de IMatchingResultRepository utilizando SQLModel para persistencia en base de datos relacional."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: MatchingResultModel) -> MatchingResult:
        """Convierte un modelo de base de datos a una entidad de dominio."""
        return MatchingResult(
            id=model.id,
            supplier_id=model.supplier_id,
            tender_id=model.tender_id,
            similarity_score=model.similarity_score,
            reranker_score=model.reranker_score,
            final_score=model.final_score,
            model_version=model.model_version,
            # Las filas anteriores a la columna quedaron en NULL y son del ranking.
            source="on_demand" if model.source == "on_demand" else "ranking",
            calculated_at=model.calculated_at,
        )

    def _to_model(self, entity: MatchingResult) -> MatchingResultModel:
        """Convierte una entidad de dominio a un modelo de base de datos."""
        return MatchingResultModel(
            id=entity.id,
            supplier_id=entity.supplier_id,
            tender_id=entity.tender_id,
            similarity_score=entity.similarity_score,
            reranker_score=entity.reranker_score,
            final_score=entity.final_score,
            model_version=entity.model_version,
            source=entity.source,
            calculated_at=entity.calculated_at,
        )

    async def save_bulk(self, results: list[MatchingResult]) -> None:
        """Persiste una lista de resultados de matching en la base de datos."""
        models = [self._to_model(r) for r in results]
        for m in models:
            self.session.add(m)
        await self.session.commit()

    async def save_on_demand(self, result: MatchingResult) -> MatchingResult:
        """Reemplaza el cálculo previo de ese par (proveedor, licitación), si lo hay."""
        await self.delete_by_supplier_and_tender_ids(
            result.supplier_id, [result.tender_id]
        )
        self.session.add(self._to_model(result))
        await self.session.commit()
        return result

    async def get_by_supplier_id(self, supplier_id: UUID) -> list[MatchingResult]:
        """Obtiene todos los resultados de matching asociados a un proveedor."""
        result = await self.session.exec(
            select(MatchingResultModel).where(
                MatchingResultModel.supplier_id == supplier_id
            )
        )
        models = result.all()
        return [self._to_entity(m) for m in models]

    async def get_ranking_by_supplier_id(
        self, supplier_id: UUID
    ) -> list[MatchingResult]:
        """Obtiene las recomendaciones del proveedor, sin los cálculos a pedido."""
        result = await self.session.exec(
            select(MatchingResultModel).where(
                MatchingResultModel.supplier_id == supplier_id,
                self._es_del_ranking(),
            )
        )
        models = result.all()
        return [self._to_entity(m) for m in models]

    async def delete_by_supplier_id(self, supplier_id: UUID) -> None:
        """Elimina físicamente todas las recomendaciones de un proveedor."""
        await self.session.exec(
            delete(MatchingResultModel).where(
                col(MatchingResultModel.supplier_id) == supplier_id
            )
        )
        await self.session.commit()

    async def delete_ranking_by_supplier_id(self, supplier_id: UUID) -> None:
        """Borra el top-N cacheado y deja intactos los cálculos a pedido."""
        await self.session.exec(
            delete(MatchingResultModel).where(
                col(MatchingResultModel.supplier_id) == supplier_id,
                self._es_del_ranking(),
            )
        )
        await self.session.commit()

    async def delete_by_supplier_and_tender_ids(
        self, supplier_id: UUID, tender_ids: list[UUID]
    ) -> None:
        """Borra las filas de ese proveedor para esas licitaciones, de cualquier origen."""
        if not tender_ids:
            return
        await self.session.exec(
            delete(MatchingResultModel).where(
                col(MatchingResultModel.supplier_id) == supplier_id,
                col(MatchingResultModel.tender_id).in_(tender_ids),
            )
        )
        await self.session.commit()

    @staticmethod
    def _es_del_ranking():
        """Condición de 'fila del ranking', contando el NULL de las filas antiguas."""
        return or_(
            col(MatchingResultModel.source).is_(None),
            col(MatchingResultModel.source) != "on_demand",
        )

    async def get_by_proveedor_and_licitacion(
        self, proveedor_id: UUID, licitacion_id: UUID
    ) -> MatchingResult | None:
        """Obtiene un resultado de matching específico por ID de proveedor y licitación."""
        result = await self.session.exec(
            select(MatchingResultModel).where(
                MatchingResultModel.supplier_id == proveedor_id,
                MatchingResultModel.tender_id == licitacion_id,
            )
        )
        model = result.first()
        return self._to_entity(model) if model else None
