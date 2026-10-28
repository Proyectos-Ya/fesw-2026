"""Dónde cae la entrega de cada licitación: la cola de geocodificación (#314)."""

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.tender_geocoding_repository import (
    ITenderGeocodingRepository,
)
from app.domain.entities.tender_map import (
    CachedGeocode,
    GeoPoint,
    GeoPrecision,
    PendingGeocoding,
)
from app.infrastructure.repositories.geocoding_cache_model import GeocodingCacheModel
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    ComunaModel,
    RegionModel,
    TenderModel,
)
from app.shared.constants import PUBLICADA_STATUS_ID
from app.shared.datetime_utils import utc_now_naive


class SqlTenderLocationRepository(ITenderGeocodingRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_pending(self, limit: int) -> list[PendingGeocoding]:
        # Las mismas condiciones del índice parcial `ix_tender_geocodificacion_pendiente`,
        # que además viene ordenado por cierre.
        query = (
            select(
                TenderModel.id,
                TenderModel.delivery_address,
                ComunaModel.name,
                RegionModel.name,
            )
            .join(
                BuyerInstitutionModel,
                col(TenderModel.buyer_rut) == col(BuyerInstitutionModel.rut),
            )
            .join(
                RegionModel, col(BuyerInstitutionModel.region_id) == col(RegionModel.id)
            )
            .outerjoin(
                ComunaModel, col(BuyerInstitutionModel.comuna_id) == col(ComunaModel.id)
            )
            .where(
                col(TenderModel.delivery_address).is_not(None),
                col(TenderModel.delivery_geocoded_at).is_(None),
                col(TenderModel.status_id) == PUBLICADA_STATUS_ID,
                col(TenderModel.closing_at) > utc_now_naive(),
            )
            .order_by(col(TenderModel.closing_at).asc())
            .limit(limit)
        )
        filas = (await self.session.exec(query)).all()
        return [
            PendingGeocoding(
                tender_id=tender_id,
                delivery_address=direccion,
                commune=comuna,
                region=region,
            )
            for tender_id, direccion, comuna, region in filas
        ]

    async def save_location(
        self, tender_id: UUID, point: GeoPoint | None, precision: GeoPrecision
    ) -> None:
        # `update` directo, sin cargar el modelo: `updated_at` dispara la
        # regeneración del análisis de Gemini y una ubicación no cambia lo que se pide.
        await self.session.exec(  # type: ignore[call-overload]
            update(TenderModel)
            .where(col(TenderModel.id) == tender_id)
            .values(
                delivery_lat=point.lat if point else None,
                delivery_lng=point.lng if point else None,
                delivery_geo_precision=precision.value,
                delivery_geocoded_at=utc_now_naive(),
            )
        )
        await self.session.commit()

    async def get_cached(self, query: str) -> CachedGeocode | None:
        fila = await self.session.get(GeocodingCacheModel, query)
        if fila is None:
            return None
        if fila.lat is None or fila.lng is None:
            return CachedGeocode(point=None)
        return CachedGeocode(point=GeoPoint(lat=fila.lat, lng=fila.lng))

    async def cache(self, query: str, point: GeoPoint | None) -> None:
        valores = {
            "lat": point.lat if point else None,
            "lng": point.lng if point else None,
            "geocoded_at": utc_now_naive(),
        }
        await self.session.exec(  # type: ignore[call-overload]
            pg_insert(GeocodingCacheModel)
            .values(query=query, **valores)
            .on_conflict_do_update(index_elements=["query"], set_=valores)
        )
        await self.session.commit()
