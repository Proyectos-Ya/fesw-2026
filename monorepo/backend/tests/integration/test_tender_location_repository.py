"""Cola y caché de geocodificación contra Postgres (HU-22, #314).

`db_session` y el esquema limpio los aporta tests/integration/conftest.py.
"""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.tender_map import CachedGeocode, GeoPoint, GeoPrecision
from app.infrastructure.repositories.sql_tender_location_repository import (
    SqlTenderLocationRepository,
)
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    ComunaModel,
    ProvinciaModel,
    RegionModel,
    TenderModel,
    TenderStatusModel,
)
from app.shared.constants import CERRADA_STATUS_ID, PUBLICADA_STATUS_ID
from app.shared.datetime_utils import utc_now_naive
from app.shared.regions import (
    CHILE_REGIONS,
    UNKNOWN_REGION_ID,
    UNKNOWN_REGION_NAME,
)

pytestmark = pytest.mark.integration

CON_COMUNA = "61.111.111-1"
SIN_COMUNA = "62.222.222-2"


async def _sembrar(session: AsyncSession) -> None:
    ahora = utc_now_naive()
    session.add(RegionModel(id=10, name=CHILE_REGIONS[10]))
    session.add(TenderStatusModel(id=PUBLICADA_STATUS_ID, code="publicada", name="P"))
    session.add(TenderStatusModel(id=CERRADA_STATUS_ID, code="cerrada", name="C"))
    session.add(ProvinciaModel(id=102, name="Chiloé", region_id=10))
    session.add(ComunaModel(id=10202, name="Ancud", provincia_id=102))
    session.add(
        BuyerInstitutionModel(
            rut=CON_COMUNA,
            name="Municipalidad de Ancud",
            region_id=10,
            comuna_id=10202,
            created_at=ahora,
            updated_at=ahora,
        )
    )
    session.add(
        BuyerInstitutionModel(
            rut=SIN_COMUNA,
            name="Servicio de Salud Chiloé",
            region_id=10,
            created_at=ahora,
            updated_at=ahora,
        )
    )
    await session.commit()


def _tender(
    *,
    cierra_en: timedelta = timedelta(days=5),
    estado: int = PUBLICADA_STATUS_ID,
    direccion: str | None = "Yerbas Buenas #915",
    comprador: str = CON_COMUNA,
    **extra,
) -> TenderModel:
    ahora = utc_now_naive()
    return TenderModel(
        id=uuid4(),
        code=f"{uuid4().hex[:8]}-COT26",
        name="Insumos",
        status_id=estado,
        published_at=ahora,
        closing_at=ahora + cierra_en,
        last_change_at=ahora,
        buyer_rut=comprador,
        buyer_unit="Unidad de Compras",
        delivery_address=direccion,
        created_at=ahora - timedelta(days=1),
        updated_at=ahora - timedelta(days=1),
        **extra,
    )


async def _guardar(session: AsyncSession, *tenders: TenderModel) -> list[UUID]:
    # Los ids se leen antes del commit: después los atributos expiran y leerlos
    # dispararía una carga síncrona fuera del loop.
    ids = [t.id for t in tenders]
    session.add_all(tenders)
    await session.commit()
    return ids


async def _organismo_sin_region(session: AsyncSession) -> str:
    """Un comprador cuya región Mercado Público no informó (`region_id` 0)."""
    rut = "64.444.444-4"
    ahora = utc_now_naive()
    session.add(RegionModel(id=UNKNOWN_REGION_ID, name=UNKNOWN_REGION_NAME))
    session.add(
        BuyerInstitutionModel(
            rut=rut,
            name="Servicio sin región informada",
            region_id=UNKNOWN_REGION_ID,
            created_at=ahora,
            updated_at=ahora,
        )
    )
    await session.commit()
    return rut


class TestCola:
    async def test_trae_solo_abiertas_con_direccion_y_sin_intento(
        self, db_session: AsyncSession
    ):
        await _sembrar(db_session)
        [pendiente] = await _guardar(db_session, _tender())
        await _guardar(
            db_session,
            _tender(direccion=None),
            _tender(estado=CERRADA_STATUS_ID),
            _tender(cierra_en=timedelta(hours=-1)),
            _tender(delivery_geocoded_at=utc_now_naive()),
        )

        cola = await SqlTenderLocationRepository(db_session).list_pending(limit=10)

        assert [p.tender_id for p in cola] == [pendiente]
        assert cola[0].delivery_address == "Yerbas Buenas #915"
        assert cola[0].commune == "Ancud"
        assert cola[0].region == CHILE_REGIONS[10]

    async def test_sin_comuna_la_trae_con_comuna_nula(self, db_session: AsyncSession):
        await _sembrar(db_session)
        await _guardar(db_session, _tender(comprador=SIN_COMUNA))

        [pendiente] = await SqlTenderLocationRepository(db_session).list_pending(10)

        assert pendiente.commune is None
        assert pendiente.region == CHILE_REGIONS[10]

    async def test_primero_las_que_cierran_antes_y_respeta_el_tope(
        self, db_session: AsyncSession
    ):
        await _sembrar(db_session)
        tarde, pronto, medio = await _guardar(
            db_session,
            _tender(cierra_en=timedelta(days=9)),
            _tender(cierra_en=timedelta(days=1)),
            _tender(cierra_en=timedelta(days=4)),
        )

        cola = await SqlTenderLocationRepository(db_session).list_pending(limit=2)

        assert [p.tender_id for p in cola] == [pronto, medio]
        assert tarde not in [p.tender_id for p in cola]


    async def test_no_encola_las_de_region_desconocida(
        self, db_session: AsyncSession
    ):
        """`region_id` 0 es "no informada", no una región.

        El mapa filtra por las 16 reales, así que estas licitaciones no pueden
        aparecer nunca: geocodificarlas gasta cuota de Nominatim en algo que no
        se va a mostrar, y manda la palabra "Desconocida" dentro de la consulta.
        """
        await _sembrar(db_session)
        sin_region = await _organismo_sin_region(db_session)
        await _guardar(db_session, _tender(comprador=sin_region))

        assert await SqlTenderLocationRepository(db_session).list_pending(10) == []


class TestGuardarUbicacion:
    async def test_guarda_el_punto_y_la_saca_de_la_cola_sin_mover_updated_at(
        self, db_session: AsyncSession
    ):
        await _sembrar(db_session)
        modelo = _tender()
        antes = modelo.updated_at
        [tender_id] = await _guardar(db_session, modelo)
        repo = SqlTenderLocationRepository(db_session)

        await repo.save_location(
            tender_id, GeoPoint(lat=-41.87, lng=-73.82), GeoPrecision.DIRECCION
        )

        db_session.expire_all()
        fila = (
            await db_session.exec(
                select(TenderModel).where(TenderModel.id == tender_id)
            )
        ).one()
        assert (fila.delivery_lat, fila.delivery_lng) == (-41.87, -73.82)
        assert fila.delivery_geo_precision == "direccion"
        assert fila.delivery_geocoded_at is not None
        assert fila.updated_at == antes
        assert await repo.list_pending(10) == []

    async def test_no_encontrada_queda_sin_coordenadas(self, db_session: AsyncSession):
        await _sembrar(db_session)
        [tender_id] = await _guardar(db_session, _tender())
        repo = SqlTenderLocationRepository(db_session)

        await repo.save_location(tender_id, None, GeoPrecision.NO_ENCONTRADA)

        db_session.expire_all()
        fila = (
            await db_session.exec(
                select(TenderModel).where(TenderModel.id == tender_id)
            )
        ).one()
        assert fila.delivery_lat is None and fila.delivery_lng is None
        assert fila.delivery_geo_precision == "no_encontrada"
        assert await repo.list_pending(10) == []


class TestCache:
    async def test_una_consulta_nueva_no_esta(self, db_session: AsyncSession):
        repo = SqlTenderLocationRepository(db_session)

        assert await repo.get_cached("Yerbas Buenas #915, Chile") is None

    async def test_guarda_el_punto_y_tambien_el_no_encontrado(
        self, db_session: AsyncSession
    ):
        repo = SqlTenderLocationRepository(db_session)
        punto = GeoPoint(lat=-41.87, lng=-73.82)

        await repo.cache("Ancud, Chile", punto)
        await repo.cache("Calle falsa 123, Chile", None)

        assert await repo.get_cached("Ancud, Chile") == CachedGeocode(point=punto)
        assert await repo.get_cached("Calle falsa 123, Chile") == CachedGeocode(
            point=None
        )

    async def test_guardar_dos_veces_la_misma_consulta_la_reemplaza(
        self, db_session: AsyncSession
    ):
        repo = SqlTenderLocationRepository(db_session)

        await repo.cache("Ancud, Chile", None)
        await repo.cache("Ancud, Chile", GeoPoint(lat=-41.87, lng=-73.82))

        guardada = await repo.get_cached("Ancud, Chile")
        assert guardada is not None and guardada.point is not None


def _ubicada(**extra) -> TenderModel:
    return _tender(
        delivery_lat=-41.87,
        delivery_lng=-73.82,
        delivery_geo_precision="direccion",
        delivery_geocoded_at=utc_now_naive(),
        **extra,
    )


async def _otra_region(session: AsyncSession) -> str:
    rut = "63.333.333-3"
    ahora = utc_now_naive()
    session.add(RegionModel(id=13, name=CHILE_REGIONS[13]))
    session.add(
        BuyerInstitutionModel(
            rut=rut,
            name="Municipalidad de Santiago",
            region_id=13,
            created_at=ahora,
            updated_at=ahora,
        )
    )
    await session.commit()
    return rut


class TestMapa:
    async def test_trae_abiertas_ubicadas_de_la_region(self, db_session: AsyncSession):
        await _sembrar(db_session)
        santiago = await _otra_region(db_session)
        [visible] = await _guardar(db_session, _ubicada())
        await _guardar(
            db_session,
            _tender(),  # pendiente, sin punto
            _tender(
                delivery_geo_precision="no_encontrada",
                delivery_geocoded_at=utc_now_naive(),
            ),
            _ubicada(estado=CERRADA_STATUS_ID),
            _ubicada(cierra_en=timedelta(hours=-1)),
            _ubicada(comprador=santiago),
        )

        puntos, total = await SqlTenderLocationRepository(
            db_session
        ).list_open_with_location(region_id=10, limit=50)

        assert [p.id for p in puntos] == [visible]
        assert total == 1
        punto = puntos[0]
        assert (punto.lat, punto.lng) == (-41.87, -73.82)
        assert punto.precision == GeoPrecision.DIRECCION
        assert punto.delivery_address == "Yerbas Buenas #915"
        assert punto.buyer_name == "Municipalidad de Ancud"
        assert punto.name == "Insumos"

    async def test_el_total_cuenta_lo_que_el_tope_deja_fuera(
        self, db_session: AsyncSession
    ):
        await _sembrar(db_session)
        pronto, medio, _tarde = await _guardar(
            db_session,
            _ubicada(cierra_en=timedelta(days=1)),
            _ubicada(cierra_en=timedelta(days=2)),
            _ubicada(cierra_en=timedelta(days=3)),
        )

        puntos, total = await SqlTenderLocationRepository(
            db_session
        ).list_open_with_location(region_id=10, limit=2)

        assert [p.id for p in puntos] == [pronto, medio]
        assert total == 3
