"""Lo que el cron de estados le pide a Postgres, contra una base real.

`overwrite_statuses` es un UPDATE en lote con `IS DISTINCT FROM`: tiene que
escribir estado y cierre, pero no mover `updated_at` de una fila que no cambió,
porque `updated_at` dispara la regeneración del análisis de Gemini.
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.models.cambio_estado import CambioDeEstado
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    RegionModel,
    TenderModel,
    TenderStatusModel,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.shared.regions import CHILE_REGIONS

pytestmark = pytest.mark.asyncio

PUBLICADA, DESIERTA = 2, 6
ANTES = datetime(2026, 9, 1, 12, 0)
CIERRE = datetime(2026, 10, 5, 16, 0)


async def _base(session: AsyncSession) -> None:
    session.add(RegionModel(id=13, name=CHILE_REGIONS[13]))
    session.add(TenderStatusModel(id=PUBLICADA, code="publicada", name="Publicada"))
    session.add(TenderStatusModel(id=DESIERTA, code="desierta", name="Desierta"))
    session.add(
        BuyerInstitutionModel(
            rut="61.000.000-0",
            name="Municipalidad",
            region_id=13,
            created_at=ANTES,
            updated_at=ANTES,
        )
    )
    await session.commit()


async def _tender(session: AsyncSession, code: str, status_id: int = PUBLICADA) -> UUID:
    tender_id = uuid4()
    session.add(
        TenderModel(
            id=tender_id,
            code=code,
            name=f"Licitación {code}",
            description=None,
            status_id=status_id,
            published_at=ANTES,
            closing_at=CIERRE,
            last_change_at=ANTES,
            buyer_rut="61.000.000-0",
            buyer_unit="Abastecimiento",
            available_amount_clp=100.0,
            created_at=ANTES,
            updated_at=ANTES,
        )
    )
    await session.commit()
    return tender_id


def _cambio(
    code: str, status_id: int, status_code: str, closing_at: datetime = CIERRE
) -> CambioDeEstado:
    return CambioDeEstado(
        code=code, status_id=status_id, status_code=status_code, closing_at=closing_at
    )


async def _fila(session: AsyncSession, tender_id: UUID) -> TenderModel:
    session.expire_all()
    fila = await session.get(TenderModel, tender_id)
    assert fila is not None
    return fila


class TestGetKnownByCodes:
    async def test_devuelve_solo_las_que_existen(self, db_session: AsyncSession):
        await _base(db_session)
        tender_id = await _tender(db_session, "A")
        repo = TenderRepository(db_session)

        conocidas = await repo.get_known_by_codes(["A", "NO-EXISTE"])

        assert set(conocidas) == {"A"}
        assert conocidas["A"].id == tender_id
        assert conocidas["A"].status_id == PUBLICADA
        assert conocidas["A"].last_change_at == ANTES

    async def test_sin_codigos_no_consulta(self, db_session: AsyncSession):
        assert await TenderRepository(db_session).get_known_by_codes([]) == {}


class TestOverwriteStatuses:
    async def test_escribe_estado_y_cierre(self, db_session: AsyncSession):
        await _base(db_session)
        tender_id = await _tender(db_session, "A")
        nuevo_cierre = CIERRE + timedelta(days=2)

        cambiadas = await TenderRepository(db_session).overwrite_statuses(
            [_cambio("A", DESIERTA, "desierta", closing_at=nuevo_cierre)]
        )

        fila = await _fila(db_session, tender_id)
        assert cambiadas == 1
        assert fila.status_id == DESIERTA
        assert fila.closing_at == nuevo_cierre
        assert fila.updated_at > ANTES

    async def test_solo_el_cierre_distinto_tambien_cuenta(
        self, db_session: AsyncSession
    ):
        """El plazo ampliado: mismo estado, otra fecha."""
        await _base(db_session)
        tender_id = await _tender(db_session, "A")
        nuevo_cierre = CIERRE + timedelta(days=2)

        cambiadas = await TenderRepository(db_session).overwrite_statuses(
            [_cambio("A", PUBLICADA, "publicada", closing_at=nuevo_cierre)]
        )

        assert cambiadas == 1
        assert (await _fila(db_session, tender_id)).closing_at == nuevo_cierre

    async def test_una_fila_sin_cambios_no_mueve_updated_at(
        self, db_session: AsyncSession
    ):
        await _base(db_session)
        tender_id = await _tender(db_session, "A")

        cambiadas = await TenderRepository(db_session).overwrite_statuses(
            [_cambio("A", PUBLICADA, "publicada")]
        )

        assert cambiadas == 0
        assert (await _fila(db_session, tender_id)).updated_at == ANTES

    async def test_no_toca_last_change_at(self, db_session: AsyncSession):
        """Es cuándo el ingest bajó el detalle; el reencolado depende de eso."""
        await _base(db_session)
        tender_id = await _tender(db_session, "A")

        await TenderRepository(db_session).overwrite_statuses(
            [_cambio("A", DESIERTA, "desierta")]
        )

        assert (await _fila(db_session, tender_id)).last_change_at == ANTES

    async def test_en_lote_y_sin_tocar_codigos_ajenos(self, db_session: AsyncSession):
        await _base(db_session)
        a = await _tender(db_session, "A")
        b = await _tender(db_session, "B")
        otra = await _tender(db_session, "OTRA")

        cambiadas = await TenderRepository(db_session).overwrite_statuses(
            [_cambio("A", DESIERTA, "desierta"), _cambio("B", DESIERTA, "desierta")]
        )

        assert cambiadas == 2
        assert (await _fila(db_session, a)).status_id == DESIERTA
        assert (await _fila(db_session, b)).status_id == DESIERTA
        assert (await _fila(db_session, otra)).status_id == PUBLICADA

    async def test_lista_vacia(self, db_session: AsyncSession):
        assert await TenderRepository(db_session).overwrite_statuses([]) == 0
