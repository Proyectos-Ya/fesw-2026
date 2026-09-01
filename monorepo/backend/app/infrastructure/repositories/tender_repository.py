import uuid
from datetime import datetime

from sqlalchemy import delete, func, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
    ComunaModel,
    RegionModel,
    TenderItemModel,
    TenderModel,
    TenderStatusModel,
)
from app.shared.constants import (
    CERRADA_STATUS_ID,
    PUBLICADA_STATUS_ID,
    TENDER_STATUS_CODE_BY_ID,
)


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
            # El código semántico sale de la fila de tender_status, que guarda el
            # valor tal como lo entrega la API. Antes se derivaba del status_id
            # con un mapa heredado de la API de Licitaciones: esa traducción es
            # justo lo que hacía que una licitación desierta figurara como
            # publicada.
            status_code=model.status.code if model.status else None,
            published_at=model.published_at,
            closing_at=model.closing_at,
            last_change_at=model.last_change_at,
            buyer_rut=model.buyer_rut,
            buyer_name=model.buyer.name if model.buyer else None,
            buyer_unit=model.buyer_unit,
            region=model.buyer.region.name
            if model.buyer and model.buyer.region
            else None,
            province=model.buyer.comuna.provincia.name
            if model.buyer and model.buyer.comuna and model.buyer.comuna.provincia
            else None,
            commune=model.buyer.comuna.name
            if model.buyer and model.buyer.comuna
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
            selectinload(TenderModel.buyer)  # type: ignore[arg-type]
            .selectinload(BuyerInstitutionModel.comuna)  # type: ignore[arg-type]
            .selectinload(ComunaModel.provincia),  # type: ignore[arg-type]
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

        # Región, provincia y comuna viven en la institución compradora (la
        # provincia, un salto más, en la comuna), así que necesitan join. Se
        # aplica a las dos consultas para que el total corresponda a los mismos
        # resultados que se devuelven.
        def _with_location(query):
            needs_buyer_join = bool(
                criteria.region_ids or criteria.province_id or criteria.commune_id
            )
            if not needs_buyer_join:
                return query.where(*conditions) if conditions else query

            query = query.join(
                BuyerInstitutionModel,
                col(TenderModel.buyer_rut) == col(BuyerInstitutionModel.rut),
            )
            if criteria.region_ids:
                query = query.where(
                    col(BuyerInstitutionModel.region_id).in_(criteria.region_ids)
                )
            if criteria.commune_id:
                # Comuna es directa: `buyer_institution.comuna_id` ya es la FK.
                query = query.where(
                    col(BuyerInstitutionModel.comuna_id) == criteria.commune_id
                )
            elif criteria.province_id:
                # Provincia no tiene FK propia en `buyer_institution`: un salto
                # más a través de `comuna`. No hace falta si ya se filtró por
                # comuna (una comuna implica una única provincia).
                query = query.join(
                    ComunaModel,
                    col(BuyerInstitutionModel.comuna_id) == col(ComunaModel.id),
                ).where(col(ComunaModel.provincia_id) == criteria.province_id)
            return query.where(*conditions) if conditions else query

        total_result = await self.session.exec(
            _with_location(select(func.count()).select_from(TenderModel))  # type: ignore[call-overload]
        )
        total = total_result.one()

        page_query = _with_location(
            select(TenderModel).options(
                selectinload(TenderModel.status),  # type: ignore[arg-type]
                selectinload(TenderModel.buyer).selectinload(  # type: ignore[arg-type]
                    BuyerInstitutionModel.region  # type: ignore[arg-type]
                ),
                selectinload(TenderModel.buyer)  # type: ignore[arg-type]
                .selectinload(BuyerInstitutionModel.comuna)  # type: ignore[arg-type]
                .selectinload(ComunaModel.provincia),  # type: ignore[arg-type]
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

    async def get_items_by_tender_id(
        self, tender_id: uuid.UUID
    ) -> list[TenderItemModel]:
        statement = select(TenderItemModel).where(
            col(TenderItemModel.tender_id) == tender_id
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def replace_tender_items(
        self, tender_id: uuid.UUID, items: list[TenderItemModel]
    ) -> None:
        """Borra las partidas actuales y deja las nuevas, en una transacción.

        Reemplazo completo y no diff: nada tiene clave foránea hacia
        `tender_item` —verificado—, y las partidas de la API no traen un
        identificador estable con el que emparejarlas entre corridas.
        """
        await self.session.exec(  # type: ignore[call-overload]
            delete(TenderItemModel).where(col(TenderItemModel.tender_id) == tender_id)
        )
        for item in items:
            self.session.add(item)
        await self.session.commit()

    async def update_tender(self, tender: TenderModel) -> None:
        self.session.add(tender)
        await self.session.commit()

    async def get_expired_published_ids(self) -> list[uuid.UUID]:
        """Vencidas que aún figuran publicadas.

        El estado se compara contra el id numérico y no contra el código de
        texto porque es la columna que tiene `tender`; el join a `tender_status`
        sería un viaje de más para un valor que ya es una constante conocida.
        """
        statement = select(TenderModel.id).where(
            col(TenderModel.closing_at) < utc_now_naive(),
            col(TenderModel.status_id) == PUBLICADA_STATUS_ID,
        )
        result = await self.session.exec(statement)  # type: ignore[call-overload]
        return list(result.all())

    async def mark_as_closed(self, tender_ids: list[uuid.UUID]) -> None:
        """Una sola sentencia y no una fila por vez.

        Cada viaje a Supabase desde Chile son ~133 ms medidos: con un día de
        rotación normal esto son cientos de licitaciones, y de a una serían
        minutos de espera que no calculan nada.
        """
        if not tender_ids:
            return
        statement = (
            update(TenderModel)
            .where(col(TenderModel.id).in_(tender_ids))
            .values(status_id=CERRADA_STATUS_ID, updated_at=utc_now_naive())
        )
        await self.session.exec(statement)  # type: ignore[call-overload]
        await self.session.commit()

    async def get_or_create_buyer(
        self,
        rut: str,
        name: str,
        region_id: int,
        comuna_id: int | None = None,
        comuna_resolution_source: str | None = None,
    ) -> str:
        statement = select(BuyerInstitutionModel).where(
            BuyerInstitutionModel.rut == rut
        )
        result = await self.session.exec(statement)
        buyer = result.first()

        if buyer:
            return rut

        # ON CONFLICT y no `add` + `flush`: desde que la ingesta baja varios
        # detalles en paralelo, dos licitaciones del mismo organismo —el caso
        # normal, un municipio publica decenas— hacen el SELECT a la vez, las
        # dos lo ven vacío y la segunda revienta con UniqueViolationError sobre
        # buyer_institution_pkey. El SELECT de arriba se conserva porque resuelve
        # el caso frecuente sin escribir nada.
        now = utc_now_naive()
        stmt = (
            pg_insert(BuyerInstitutionModel)
            .values(
                rut=rut,
                name=name,
                region_id=region_id,
                comuna_id=comuna_id,
                comuna_resolution_source=comuna_resolution_source,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["rut"])
        )
        await self.session.exec(stmt)  # type: ignore[call-overload]
        return rut

    async def get_comuna_id_by_name(self, name: str) -> int | None:
        statement = select(ComunaModel).where(ComunaModel.name == name)
        result = await self.session.exec(statement)
        comuna = result.first()
        return comuna.id if comuna else None

    async def get_provincia_id_by_comuna_id(self, comuna_id: int) -> int | None:
        comuna = await self.session.get(ComunaModel, comuna_id)
        return comuna.provincia_id if comuna else None

    async def get_or_create_status(self, status_id: int, code: str) -> int:
        """Devuelve el id de la fila de estado, creándola o corrigiéndola.

        `code` es el `estado.codigo` de la API y es lo que después lee
        `_to_entity`. Antes esta función escribía `str(id)` o `publicada_2` y el
        código semántico se derivaba de un mapa aparte; guardarlo tal cual
        elimina esa traducción.

        Si la fila existe con otro código —el caso de las bases sembradas con la
        numeración heredada de la API de Licitaciones— se corrige en el sitio.
        Sin esto, una base ya poblada seguiría sirviendo el valor viejo para
        siempre.
        """
        statement = select(TenderStatusModel).where(TenderStatusModel.id == status_id)
        result = await self.session.exec(statement)
        status = result.first()

        nombre = code.replace("_", " ").capitalize()
        if not status:
            # Mismo motivo que en get_or_create_buyer: con la ingesta en
            # paralelo, varias licitaciones estrenan el mismo estado a la vez.
            # Sin `index_elements`: la tabla tiene único el id y también el
            # code, y cualquiera de los dos puede ser el que choque.
            stmt = (
                pg_insert(TenderStatusModel)
                .values(id=status_id, code=code, name=nombre)
                .on_conflict_do_nothing()
            )
            await self.session.exec(stmt)  # type: ignore[call-overload]
        elif status.code != code:
            status.code = code
            status.name = nombre
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
