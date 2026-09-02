"""Las licitaciones cuyo plazo venció tienen que dejar de competir por un cupo.

El payload de Qdrant se escribía una vez en la ingesta y no se tocaba más. Una
licitación que cerró conservaba `status_code: "publicada"`, así que seguía
pasando el pre-filtro de la etapa ① del embudo y **ocupaba uno de los 50 cupos
de candidatas**, para recién ser descartada en la etapa ② comparando `closing_at`
contra SQL. Con rotación alta pueden estar rerankeándose 20 vigentes en vez de 50:
cada cerrada le roba el lugar a una candidata real.

Se marcan, no se borran. Borrar el punto —lo que proponía la nota original—
libera el cupo igual, pero el buscador manual expone un filtro `status_codes`
que acepta `cerrada`, y esa búsqueda quedaría devolviendo cero para siempre.

No cuesta cuota: `closing_at` ya está en Postgres.
"""

import uuid
from datetime import timedelta

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.use_cases.mark_expired_tenders import MarkExpiredTendersUseCase
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    TenderModel,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.infrastructure.seeder import seed_database_metadata
from app.shared.constants import TENDER_STATUSES
from app.shared.datetime_utils import utc_now_naive

pytestmark = pytest.mark.asyncio

PUBLICADA_ID = 2
CERRADA_ID = 3


class VectorRepoFalso:
    def __init__(self):
        self.payloads: dict[uuid.UUID, dict] = {}
        self.borrados: list[uuid.UUID] = []

    async def ensure_collection(self) -> None: ...
    async def upsert(self, tender_id, embedding, payload) -> None: ...
    async def delete(self, tender_id) -> None:
        self.borrados.append(tender_id)

    async def set_payload(self, tender_id, payload) -> None:
        self.payloads[tender_id] = payload

    async def search_by_vector(self, *a, **kw):
        return []

    async def count(self, *a, **kw):
        return 0


BUYER_RUT = "60.000.000-0"


@pytest_asyncio.fixture
async def base(integration_engine):
    """Regiones, estados y un organismo comprador: los FK de `tender`."""
    async with AsyncSession(integration_engine) as s:
        await seed_database_metadata(s)
        ahora = utc_now_naive()
        s.add(
            BuyerInstitutionModel(
                rut=BUYER_RUT,
                name="Organismo de prueba",
                region_id=13,
                created_at=ahora,
                updated_at=ahora,
            )
        )
        await s.commit()
    return integration_engine


async def _crear(engine, code: str, *, cierra_en: timedelta, status_id: int) -> uuid.UUID:
    tender_id = uuid.uuid4()
    ahora = utc_now_naive()
    async with AsyncSession(engine) as s:
        s.add(
            TenderModel(
                id=tender_id,
                code=code,
                name=f"Licitación {code}",
                description="x",
                status_id=status_id,
                published_at=ahora - timedelta(days=10),
                closing_at=ahora + cierra_en,
                last_change_at=ahora,
                buyer_rut=BUYER_RUT,
                buyer_unit="u",
                available_amount_clp=1000,
                created_at=ahora,
                updated_at=ahora,
            )
        )
        await s.commit()
    return tender_id


async def _status_id(engine, tender_id: uuid.UUID) -> int:
    async with AsyncSession(engine) as s:
        fila = await s.get(TenderModel, tender_id)
        assert fila is not None
        return fila.status_id


def _caso_de_uso(session, vector_repo) -> MarkExpiredTendersUseCase:
    return MarkExpiredTendersUseCase(
        repository=TenderRepository(session),
        tender_vector_repo=vector_repo,  # type: ignore[arg-type]
    )


class TestMarcadoDeVencidas:
    async def test_una_vencida_pasa_a_cerrada_en_sql_y_en_qdrant(self, base):
        vencida = await _crear(
            base, "VENC-1", cierra_en=-timedelta(days=1), status_id=PUBLICADA_ID
        )
        repo = VectorRepoFalso()

        async with AsyncSession(base) as s:
            marcadas = await _caso_de_uso(s, repo).execute()

        assert marcadas == 1
        assert await _status_id(base, vencida) == CERRADA_ID
        assert repo.payloads[vencida] == {"status_code": TENDER_STATUSES["CLOSED"]}

    async def test_una_vigente_no_se_toca(self, base):
        vigente = await _crear(
            base, "VIG-1", cierra_en=timedelta(days=5), status_id=PUBLICADA_ID
        )
        repo = VectorRepoFalso()

        async with AsyncSession(base) as s:
            marcadas = await _caso_de_uso(s, repo).execute()

        assert marcadas == 0
        assert await _status_id(base, vigente) == PUBLICADA_ID
        assert repo.payloads == {}

    async def test_nunca_borra_el_punto(self, base):
        """Borrar dejaría el filtro `cerrada` del buscador devolviendo cero."""
        await _crear(
            base, "VENC-1", cierra_en=-timedelta(days=1), status_id=PUBLICADA_ID
        )
        repo = VectorRepoFalso()

        async with AsyncSession(base) as s:
            await _caso_de_uso(s, repo).execute()

        assert repo.borrados == []

    async def test_es_idempotente(self, base):
        """Correr dos veces no reescribe lo ya marcado: la segunda no hace nada."""
        await _crear(
            base, "VENC-1", cierra_en=-timedelta(days=1), status_id=PUBLICADA_ID
        )
        repo = VectorRepoFalso()

        async with AsyncSession(base) as s:
            primera = await _caso_de_uso(s, repo).execute()
        async with AsyncSession(base) as s:
            segunda = await _caso_de_uso(s, repo).execute()

        assert (primera, segunda) == (1, 0)

    async def test_no_reabre_una_cancelada_ni_una_desierta(self, base):
        """Solo se tocan las que siguen diciendo `publicada`."""
        cancelada = await _crear(
            base, "CANC-1", cierra_en=-timedelta(days=1), status_id=5
        )
        repo = VectorRepoFalso()

        async with AsyncSession(base) as s:
            marcadas = await _caso_de_uso(s, repo).execute()

        assert marcadas == 0
        assert await _status_id(base, cancelada) == 5

    async def test_marca_varias_de_una_pasada(self, base):
        for i in range(5):
            await _crear(
                base, f"VENC-{i}", cierra_en=-timedelta(days=1), status_id=PUBLICADA_ID
            )
        repo = VectorRepoFalso()

        async with AsyncSession(base) as s:
            marcadas = await _caso_de_uso(s, repo).execute()

        assert marcadas == 5
        assert len(repo.payloads) == 5
