"""`ranking_id` en /tenders/recommended y POST /tenders/{id}/interactions (plan 233, decisión 8)."""

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.application.use_cases.ranking_telemetry.record_tender_interaction import (
    RecordTenderInteractionUseCase,
)
from app.bootstrap import (
    get_rank_tenders_use_case,
    get_record_tender_interaction_use_case,
)
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.ranking_telemetry import RankingImpression
from app.main import app
from tests.support.api_auth import autenticar
from tests.unit.application.fakes import InMemoryRankingTelemetryRepository


@pytest.fixture(autouse=True)
def limpiar_overrides():
    yield
    app.dependency_overrides.clear()


def _servir(n: int = 3) -> list[MatchingResult]:
    supplier_id = uuid4()
    return [
        MatchingResult(
            supplier_id=supplier_id,
            tender_id=uuid4(),
            final_score=0.9 - indice / 10,
            model_version="m+v",
        )
        for indice in range(n)
    ]


def _usar_ranking(resultados: list[MatchingResult]) -> AsyncMock:
    caso = AsyncMock()
    caso.execute.return_value = resultados
    app.dependency_overrides[get_rank_tenders_use_case] = lambda: caso
    return caso


# ---------------------------------------------------------------------------
# GET /tenders/recommended
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recommended_lleva_ranking_id_y_las_posiciones_servidas(
    api: AsyncClient,
) -> None:
    resultados = _servir(3)
    _usar_ranking(resultados)
    user_id = await autenticar(api)

    respuesta = await api.get("/tenders/recommended")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert [r["tender_id"] for r in cuerpo] == [str(r.tender_id) for r in resultados]
    assert [r["ranking_position"] for r in cuerpo] == [1, 2, 3]
    ranking_ids = {r["ranking_id"] for r in cuerpo}
    assert len(ranking_ids) == 1
    assert None not in ranking_ids

    (llamada,) = api.rankings_registrados.llamadas
    ranking_id, usuario, servidos, _ = llamada
    assert str(ranking_id) == ranking_ids.pop()
    assert usuario == user_id
    assert [r.tender_id for r in servidos] == [r.tender_id for r in resultados]


@pytest.mark.asyncio
async def test_dos_pedidos_con_la_misma_lista_reusan_el_ranking_y_registran_una_vez(
    api: AsyncClient,
) -> None:
    _usar_ranking(_servir(3))
    await autenticar(api)

    primero = (await api.get("/tenders/recommended")).json()
    segundo = (await api.get("/tenders/recommended")).json()

    assert primero[0]["ranking_id"] == segundo[0]["ranking_id"]
    assert len(api.rankings_registrados.llamadas) == 1


@pytest.mark.asyncio
async def test_track_false_no_registra(api: AsyncClient) -> None:
    _usar_ranking(_servir(3))
    await autenticar(api)

    respuesta = await api.get("/tenders/recommended?track=false")

    assert respuesta.status_code == 200
    assert [r["ranking_id"] for r in respuesta.json()] == [None, None, None]
    assert api.rankings_registrados.llamadas == []


@pytest.mark.asyncio
async def test_lista_vacia_no_registra(api: AsyncClient) -> None:
    _usar_ranking([])
    await autenticar(api)

    respuesta = await api.get("/tenders/recommended")

    assert respuesta.status_code == 200
    assert respuesta.json() == []
    assert api.rankings_registrados.llamadas == []


# ---------------------------------------------------------------------------
# POST /tenders/{id}/interactions
# ---------------------------------------------------------------------------


class Escenario:
    def __init__(self, user_id: UUID) -> None:
        self.repo = InMemoryRankingTelemetryRepository()
        self.ranking = uuid4()
        self.tender = uuid4()
        self.repo.impressions.append(
            RankingImpression(
                ranking_id=self.ranking,
                supplier_id=uuid4(),
                user_id=user_id,
                tender_id=self.tender,
                position=2,
                model_version="m1",
            )
        )
        app.dependency_overrides[get_record_tender_interaction_use_case] = (
            lambda: RecordTenderInteractionUseCase(repo=self.repo)
        )


@pytest.mark.asyncio
async def test_una_interaccion_atribuida_responde_202_y_guarda_la_posicion_mostrada(
    api: AsyncClient,
) -> None:
    e = Escenario(await autenticar(api))

    respuesta = await api.post(
        f"/tenders/{e.tender}/interactions",
        json={
            "kind": "detalle",
            "ranking_id": str(e.ranking),
            "position": 1,
            "source": "matches",
        },
    )

    assert respuesta.status_code == 202
    assert respuesta.json() == {"recorded": True, "attributed": True}
    (guardada,) = e.repo.interactions
    assert guardada.position == 1
    assert guardada.ranking_id == e.ranking


@pytest.mark.asyncio
async def test_un_ranking_de_otro_usuario_no_se_atribuye(api: AsyncClient) -> None:
    await autenticar(api)
    e = Escenario(uuid4())

    respuesta = await api.post(
        f"/tenders/{e.tender}/interactions",
        json={
            "kind": "detalle",
            "ranking_id": str(e.ranking),
            "position": 1,
            "source": "matches",
        },
    )

    assert respuesta.status_code == 202
    assert respuesta.json() == {"recorded": True, "attributed": False}
    assert e.repo.interactions[0].ranking_id is None


@pytest.mark.asyncio
async def test_dos_impresiones_iguales_registran_solo_la_primera(
    api: AsyncClient,
) -> None:
    e = Escenario(await autenticar(api))
    cuerpo = {
        "kind": "impresion",
        "ranking_id": str(e.ranking),
        "position": 1,
        "source": "inicio",
    }

    primera = await api.post(f"/tenders/{e.tender}/interactions", json=cuerpo)
    segunda = await api.post(f"/tenders/{e.tender}/interactions", json=cuerpo)

    assert primera.json()["recorded"] is True
    assert segunda.json()["recorded"] is False
    assert len(e.repo.interactions) == 1


@pytest.mark.asyncio
async def test_un_tipo_desconocido_responde_422(api: AsyncClient) -> None:
    e = Escenario(await autenticar(api))

    respuesta = await api.post(
        f"/tenders/{e.tender}/interactions",
        json={"kind": "compartir", "source": "matches"},
    )

    assert respuesta.status_code == 422


@pytest.mark.asyncio
async def test_una_licitacion_inexistente_responde_404(api: AsyncClient) -> None:
    e = Escenario(await autenticar(api))
    e.repo.missing_tenders.add(e.tender)

    respuesta = await api.post(
        f"/tenders/{e.tender}/interactions",
        json={"kind": "detalle", "source": "detalle"},
    )

    assert respuesta.status_code == 404


@pytest.mark.asyncio
async def test_sin_token_responde_401(api: AsyncClient) -> None:
    e = Escenario(uuid4())

    respuesta = await api.post(
        f"/tenders/{e.tender}/interactions",
        json={"kind": "detalle", "source": "detalle"},
    )

    assert respuesta.status_code == 401
