from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, delete, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.domain.entities.matching_result import MatchingResult
from app.domain.errors.matching_errors import RecommendationsSaveError
from app.infrastructure.repositories.matching_result_model import MatchingResultModel

# Restricción única del par (ver MatchingResultModel y las migraciones).
_PAR_UNICO = "uq_matching_result_supplier_tender"


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
        """Persiste el ranking de un proveedor; si el par ya existe, lo reemplaza.

        Idempotente por (proveedor, licitación): dos recálculos simultáneos del
        mismo proveedor —el dashboard pide `/tenders/recommended` dos veces al
        abrirse— escriben los mismos pares, y el borrado previo del caso de uso
        no alcanza a protegerlos porque ocurre antes de que el otro inserte. Con
        ON CONFLICT gana el último cálculo en vez de violar
        `uq_matching_result_supplier_tender`.

        Cualquier otro rechazo de la base (p. ej. una licitación borrada a mitad
        del cálculo) sale como `RecommendationsSaveError`, con la sesión ya
        revertida para que pueda seguir usándose.
        """
        if not results:
            return
        filas = [self._to_model(r).model_dump() for r in results]
        stmt = pg_insert(MatchingResultModel).values(filas)
        stmt = stmt.on_conflict_do_update(
            constraint=_PAR_UNICO,
            set_={
                columna: stmt.excluded[columna]
                for columna in (
                    "similarity_score",
                    "reranker_score",
                    "final_score",
                    "model_version",
                    "source",
                    "calculated_at",
                )
            },
        )
        try:
            await self.session.exec(stmt)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise RecommendationsSaveError() from exc

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
