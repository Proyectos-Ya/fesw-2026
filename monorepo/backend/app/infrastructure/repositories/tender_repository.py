import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.schemas.tender_schema import TenderFilterCriteria
from app.domain.entities.deep_analysis import VALID_RECOMMENDATIONS, DeepAnalysis
from app.domain.entities.tender import Tender, TenderItem, utc_now_naive
from app.infrastructure.repositories.deep_analysis_model import DeepAnalysisModel
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    RegionModel,
    TenderItemModel,
    TenderModel,
    TenderStatusModel,
)
from app.shared.constants import TENDER_STATUS_CODE_BY_ID


class TenderRepository(ITenderRepository):
    """Concrete repository implementing ITenderRepository with SQLModel."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: TenderModel) -> Tender:
        """Convert DB Model to Domain Entity."""
        return Tender(
            id=model.id,
            code=model.code,
            name=model.name,
            description=model.description,
            status_id=model.status_id,
            # Código semántico ('publicada', ...) derivado del status_id: la tabla
            # tender_status guarda códigos únicos por fila (ej. '2', 'publicada_2'),
            # pero el pipeline de matching filtra por el código semántico.
            status_code=TENDER_STATUS_CODE_BY_ID.get(
                model.status_id, model.status.code if model.status else None
            ),
            published_at=model.published_at,
            closing_at=model.closing_at,
            last_change_at=model.last_change_at,
            buyer_rut=model.buyer_rut,
            buyer_name=model.buyer.name if model.buyer else None,
            buyer_unit=model.buyer_unit,
            region=model.buyer.region.name
            if model.buyer and model.buyer.region
            else None,
            available_amount_clp=model.available_amount_clp,
            created_at=model.created_at,
            updated_at=model.updated_at,
            items=[
                TenderItem(
                    id=item.id,
                    tender_id=item.tender_id,
                    product_code=item.product_code,
                    name=item.name,
                    description=item.description,
                    quantity=item.quantity,
                    unit_of_measure=item.unit_of_measure,
                )
                for item in (model.items or [])
            ],
        )

    def _to_model(self, entity: Tender) -> TenderModel:
        """Convert Domain Entity to DB Model."""
        return TenderModel(
            id=entity.id,
            code=entity.code,
            name=entity.name,
            description=entity.description,
            status_id=entity.status_id,
            published_at=entity.published_at,
            closing_at=entity.closing_at,
            last_change_at=entity.last_change_at,
            buyer_rut=entity.buyer_rut,
            buyer_unit=entity.buyer_unit,
            available_amount_clp=entity.available_amount_clp,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def get_tenders(self, filters: TenderFilters) -> list[Tender]:
        """Retrieve tenders matching specified filters."""
        # SQLModel anota las relaciones con el tipo de la entidad, no con el
        # descriptor QueryableAttribute que SQLAlchemy instala en runtime, por lo
        # que selectinload no puede tiparse sin ignorar el argumento.
        query = select(TenderModel).options(
            selectinload(TenderModel.status),  # type: ignore[arg-type]
            selectinload(TenderModel.buyer).selectinload(  # type: ignore[arg-type]
                BuyerInstitutionModel.region  # type: ignore[arg-type]
            ),
            selectinload(TenderModel.items),  # type: ignore[arg-type]
        )

        # Apply join if region name filtering is requested
        if filters.regions:
            query = (
                query.join(
                    BuyerInstitutionModel,
                    col(TenderModel.buyer_rut) == col(BuyerInstitutionModel.rut),
                )
                .join(
                    RegionModel,
                    col(BuyerInstitutionModel.region_id) == col(RegionModel.id),
                )
                .where(col(RegionModel.name).in_(filters.regions))
            )

        if filters.ids:
            query = query.where(col(TenderModel.id).in_(filters.ids))

        result = await self.session.exec(query)
        models = result.all()

        return [self._to_entity(m) for m in models]

    def _search_conditions(self, criteria: TenderFilterCriteria) -> list:
        """Traduce el criterio de búsqueda a condiciones de SQLModel.

        Todo pasa por `col(...) == valor`, que genera parámetros ligados: los
        valores nunca se concatenan a la sentencia. Ahí está la defensa real
        contra inyección, no en sanitizar cadenas.
        """
        conditions = []

        if criteria.status_codes:
            # La tabla guarda `status_id`; el código semántico ('publicada') se
            # deriva de él. Varios ids comparten código —1, 2 y 6 son todos
            # 'publicada'— así que la traducción es de uno a muchos.
            status_ids = [
                status_id
                for status_id, code in TENDER_STATUS_CODE_BY_ID.items()
                if code in criteria.status_codes
            ]
            conditions.append(col(TenderModel.status_id).in_(status_ids))

        if criteria.closing_from is not None:
            conditions.append(col(TenderModel.closing_at) >= criteria.closing_from)
        if criteria.closing_to is not None:
            conditions.append(col(TenderModel.closing_at) <= criteria.closing_to)
        if criteria.published_from is not None:
            conditions.append(col(TenderModel.published_at) >= criteria.published_from)
        if criteria.published_to is not None:
            conditions.append(col(TenderModel.published_at) <= criteria.published_to)

        # Una licitación sin monto queda fuera cuando el filtro está activo: en
        # SQL la comparación contra NULL no es verdadera, que es la misma
        # semántica del payload de Qdrant y la del filtro del frontend.
        if criteria.min_amount is not None:
            conditions.append(
                col(TenderModel.available_amount_clp) >= criteria.min_amount
            )
        if criteria.max_amount is not None:
            conditions.append(
                col(TenderModel.available_amount_clp) <= criteria.max_amount
            )

        return conditions

    async def search_tenders(
        self,
        criteria: TenderFilterCriteria,
        limit: int,
        offset: int = 0,
    ) -> tuple[list[Tender], int]:
        """Respaldo del buscador cuando no hay vector con que ordenar.

        Ordena por fecha de cierre ascendente: sin relevancia que calcular, lo
        más útil es lo que vence primero.
        """
        conditions = self._search_conditions(criteria)

        # La región vive en la institución compradora, así que necesita join. Se
        # aplica a las dos consultas para que el total corresponda a los mismos
        # resultados que se devuelven.
        def _with_region(query):
            if not criteria.region_ids:
                return query.where(*conditions) if conditions else query
            query = query.join(
                BuyerInstitutionModel,
                col(TenderModel.buyer_rut) == col(BuyerInstitutionModel.rut),
            ).where(col(BuyerInstitutionModel.region_id).in_(criteria.region_ids))
            return query.where(*conditions) if conditions else query

        total_result = await self.session.exec(
            _with_region(select(func.count()).select_from(TenderModel))  # type: ignore[call-overload]
        )
        total = total_result.one()

        page_query = _with_region(
            select(TenderModel).options(
                selectinload(TenderModel.status),  # type: ignore[arg-type]
                selectinload(TenderModel.buyer).selectinload(  # type: ignore[arg-type]
                    BuyerInstitutionModel.region  # type: ignore[arg-type]
                ),
                selectinload(TenderModel.items),  # type: ignore[arg-type]
            )
        )
        page_query = (
            page_query.order_by(col(TenderModel.closing_at).asc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.exec(page_query)
        return [self._to_entity(m) for m in result.all()], total

    async def get_by_code(self, code: str) -> TenderModel | None:
        statement = select(TenderModel).where(TenderModel.code == code)
        result = await self.session.exec(statement)
        return result.first()

    async def get_or_create_buyer(self, rut: str, name: str, region_id: int) -> str:
        statement = select(BuyerInstitutionModel).where(
            BuyerInstitutionModel.rut == rut
        )
        result = await self.session.exec(statement)
        buyer = result.first()

        if not buyer:
            now = utc_now_naive()
            buyer = BuyerInstitutionModel(
                rut=rut, name=name, region_id=region_id, created_at=now, updated_at=now
            )
            self.session.add(buyer)
            await self.session.flush()
        return rut

    async def get_or_create_status(self, status_id: int) -> int:
        statement = select(TenderStatusModel).where(TenderStatusModel.id == status_id)
        result = await self.session.exec(statement)
        status = result.first()

        if not status:
            # Se deriva del mapeo medido en vez de repetirlo: eran tres copias
            # (esta, el seeder y constants) y llevaban valores distintos entre sí.
            ESTADOS_MAP = {
                id_: codigo.replace("_", " ").capitalize()
                for id_, codigo in TENDER_STATUS_CODE_BY_ID.items()
            }

            if status_id in ESTADOS_MAP:
                # code tiene índice único: se sufija con el id; el código
                # semántico se deriva en _to_entity vía TENDER_STATUS_CODE_BY_ID.
                name_str = ESTADOS_MAP[status_id]
                code_str = f"{name_str.lower().strip()}_{status_id}"
            else:
                name_str = f"Estado Desconocido ({status_id})"
                code_str = f"desconocido_{status_id}"

            status = TenderStatusModel(id=status_id, code=code_str, name=name_str)
            self.session.add(status)
            await self.session.flush()

        return status_id

    async def save_complex_tender(
        self, tender_model: TenderModel, items: list[TenderItemModel]
    ):
        self.session.add(tender_model)
        for item in items:
            self.session.add(item)
        await self.session.commit()

    async def rollback(self) -> None:
        # Limpia buffer
        await self.session.rollback()

    def _to_deep_analysis_entity(self, model: DeepAnalysisModel) -> DeepAnalysis:
        """Convert DeepAnalysisModel to DeepAnalysis domain entity."""
        # La columna es un str libre: validamos contra el dominio antes de
        # construir la entidad para no violar su contrato con datos corruptos.
        recommendation = model.recommendation
        if recommendation not in VALID_RECOMMENDATIONS:
            raise ValueError(
                f"Recomendación inválida en la base de datos para el análisis "
                f"{model.id}: '{recommendation}'. "
                f"Valores permitidos: {list(VALID_RECOMMENDATIONS)}"
            )

        return DeepAnalysis(
            id=model.id,
            tender_id=model.tender_id,
            supplier_id=model.supplier_id,
            compatibility_score=model.compatibility_score,
            recommendation=recommendation,
            justification=model.justification,
            prompt_instruction=model.prompt_instruction,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_deep_analysis_model(self, entity: DeepAnalysis) -> DeepAnalysisModel:
        """Convert DeepAnalysis domain entity to DeepAnalysisModel DB model."""
        return DeepAnalysisModel(
            id=entity.id,
            tender_id=entity.tender_id,
            supplier_id=entity.supplier_id,
            compatibility_score=entity.compatibility_score,
            recommendation=entity.recommendation,
            justification=entity.justification,
            prompt_instruction=entity.prompt_instruction,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def get_deep_analysis(
        self, tender_id: uuid.UUID, supplier_id: uuid.UUID
    ) -> DeepAnalysis | None:
        statement = select(DeepAnalysisModel).where(
            DeepAnalysisModel.tender_id == tender_id,
            DeepAnalysisModel.supplier_id == supplier_id,
        )
        result = await self.session.exec(statement)
        model = result.first()
        return self._to_deep_analysis_entity(model) if model else None

    async def save_deep_analysis(self, deep_analysis: DeepAnalysis) -> DeepAnalysis:
        statement = select(DeepAnalysisModel).where(
            DeepAnalysisModel.tender_id == deep_analysis.tender_id,
            DeepAnalysisModel.supplier_id == deep_analysis.supplier_id,
        )
        result = await self.session.exec(statement)
        model = result.first()

        if model:
            model.compatibility_score = deep_analysis.compatibility_score
            model.recommendation = deep_analysis.recommendation
            model.justification = deep_analysis.justification
            model.prompt_instruction = deep_analysis.prompt_instruction
            model.updated_at = deep_analysis.updated_at
        else:
            model = self._to_deep_analysis_model(deep_analysis)
            self.session.add(model)

        await self.session.commit()
        await self.session.refresh(model)
        return self._to_deep_analysis_entity(model)

    async def get_latest_tender_created_at(self) -> datetime | None:
        """Fecha de la licitación más reciente, para saber si la caché quedó atrás."""
        statement = (
            select(TenderModel.created_at)
            .order_by(col(TenderModel.created_at).desc())
            .limit(1)
        )
        result = await self.session.exec(statement)
        return result.first()
