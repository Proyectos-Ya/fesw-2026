"""El doble en memoria debe respetar la semántica del contrato real.

Otros tests se apoyan en `InMemoryTenderItemVectorRepository` en lugar de Qdrant;
si el doble se desviara del contrato (por ejemplo, conservando vectores viejos tras
un reemplazo), esos tests pasarían por razones equivocadas.
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.application.schemas.tender_schema import TenderFilterCriteria
from app.shared.datetime_utils import to_utc_epoch
from tests.unit.application.fakes import InMemoryTenderItemVectorRepository


@pytest.mark.anyio
async def test_upsert_reemplaza_todos_los_vectores_de_la_licitacion() -> None:
    repo = InMemoryTenderItemVectorRepository()
    tender_id = uuid4()

    await repo.upsert(tender_id, [[1.0, 0.0], [0.0, 1.0]])
    await repo.upsert(tender_id, [[0.5, 0.5]])

    assert await repo.get_many([tender_id]) == {tender_id: [[0.5, 0.5]]}


@pytest.mark.anyio
async def test_upsert_con_lista_vacia_borra_la_licitacion() -> None:
    repo = InMemoryTenderItemVectorRepository()
    tender_id = uuid4()
    await repo.upsert(tender_id, [[1.0, 0.0]])

    await repo.upsert(tender_id, [])

    assert await repo.get_many([tender_id]) == {}


@pytest.mark.anyio
async def test_get_many_solo_devuelve_las_licitaciones_con_vectores() -> None:
    repo = InMemoryTenderItemVectorRepository()
    presente, ausente = uuid4(), uuid4()
    await repo.upsert(presente, [[1.0, 0.0]])

    result = await repo.get_many([presente, ausente])

    assert result == {presente: [[1.0, 0.0]]}


@pytest.mark.anyio
async def test_delete_elimina_y_es_idempotente() -> None:
    repo = InMemoryTenderItemVectorRepository()
    tender_id = uuid4()
    await repo.upsert(tender_id, [[1.0, 0.0]])

    await repo.delete(tender_id)
    await repo.delete(tender_id)

    assert await repo.get_many([tender_id]) == {}


# ---------------------------------------------------------------------------
# Payload y búsqueda por keywords (segundo canal de recuperación)
# ---------------------------------------------------------------------------

_PUBLICADA_RM = {"status_code": "publicada", "region_id": 13}


@pytest.mark.anyio
async def test_upsert_guarda_el_payload() -> None:
    repo = InMemoryTenderItemVectorRepository()
    tender_id = uuid4()

    await repo.upsert(tender_id, [[1.0, 0.0]], _PUBLICADA_RM)

    assert repo.payloads[tender_id] == _PUBLICADA_RM


@pytest.mark.anyio
async def test_upsert_reemplaza_el_punto_entero_payload_incluido() -> None:
    """Igual que Qdrant: el upsert sobrescribe el punto, no fusiona el payload."""
    repo = InMemoryTenderItemVectorRepository()
    tender_id = uuid4()
    await repo.upsert(tender_id, [[1.0, 0.0]], {"status_code": "publicada", "region_id": 13})

    await repo.upsert(tender_id, [[1.0, 0.0]], {"status_code": "cerrada"})

    assert repo.payloads[tender_id] == {"status_code": "cerrada"}


@pytest.mark.anyio
async def test_delete_y_upsert_vacio_eliminan_tambien_el_payload() -> None:
    repo = InMemoryTenderItemVectorRepository()
    a, b = uuid4(), uuid4()
    await repo.upsert(a, [[1.0, 0.0]], _PUBLICADA_RM)
    await repo.upsert(b, [[1.0, 0.0]], _PUBLICADA_RM)

    await repo.delete(a)
    await repo.upsert(b, [])

    assert repo.payloads == {}


@pytest.mark.anyio
async def test_set_payload_fusiona_las_claves_entregadas() -> None:
    repo = InMemoryTenderItemVectorRepository()
    tender_id = uuid4()
    await repo.upsert(tender_id, [[1.0, 0.0]], _PUBLICADA_RM)

    await repo.set_payload(tender_id, {"status_code": "cerrada"})

    assert repo.payloads[tender_id] == {"status_code": "cerrada", "region_id": 13}


@pytest.mark.anyio
async def test_set_payload_de_un_punto_inexistente_no_hace_nada() -> None:
    repo = InMemoryTenderItemVectorRepository()
    tender_id = uuid4()

    await repo.set_payload(tender_id, {"status_code": "cerrada"})

    assert repo.payloads == {}
    assert repo.vectors == {}


@pytest.mark.anyio
async def test_search_by_keywords_calcula_maxsim_con_coseno() -> None:
    """Σ sobre las keywords del mejor coseno entre esa keyword y las partidas."""
    repo = InMemoryTenderItemVectorRepository()
    cemento, mixta, nada = uuid4(), uuid4(), uuid4()
    await repo.upsert(cemento, [[1.0, 0.0, 0.0]])
    await repo.upsert(mixta, [[1.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    await repo.upsert(nada, [[0.0, 0.0, 1.0]])

    resultados = await repo.search_by_keywords([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], limit=10)

    puntajes = dict(resultados)
    assert puntajes[cemento] == pytest.approx(1.0 + 0.0)
    assert puntajes[mixta] == pytest.approx(2 * 0.5**0.5)  # coseno 45° con cada keyword
    assert puntajes[nada] == pytest.approx(0.0)


@pytest.mark.anyio
async def test_search_by_keywords_toma_la_mejor_partida_de_cada_keyword() -> None:
    repo = InMemoryTenderItemVectorRepository()
    tender_id = uuid4()
    await repo.upsert(tender_id, [[0.0, 1.0], [1.0, 0.0], [1.0, 1.0]])

    [(_, puntaje)] = await repo.search_by_keywords([[1.0, 0.0]], limit=10)

    assert puntaje == pytest.approx(1.0)  # la partida [1, 0], no el promedio


@pytest.mark.anyio
async def test_search_by_keywords_ordena_por_puntaje_descendente_y_recorta() -> None:
    repo = InMemoryTenderItemVectorRepository()
    bajo, alto, medio = uuid4(), uuid4(), uuid4()
    await repo.upsert(bajo, [[0.0, 1.0]])
    await repo.upsert(alto, [[1.0, 0.0]])
    await repo.upsert(medio, [[1.0, 1.0]])

    todos = await repo.search_by_keywords([[1.0, 0.0]], limit=10)
    recortado = await repo.search_by_keywords([[1.0, 0.0]], limit=2)

    assert [tid for tid, _ in todos] == [alto, medio, bajo]
    assert [tid for tid, _ in recortado] == [alto, medio]


@pytest.mark.anyio
async def test_search_by_keywords_sin_keywords_devuelve_vacio() -> None:
    repo = InMemoryTenderItemVectorRepository()
    await repo.upsert(uuid4(), [[1.0, 0.0]])

    assert await repo.search_by_keywords([], limit=10) == []


@pytest.mark.anyio
async def test_search_by_keywords_no_revienta_con_vectores_nulos() -> None:
    repo = InMemoryTenderItemVectorRepository()
    tender_id = uuid4()
    await repo.upsert(tender_id, [[0.0, 0.0]])

    [(_, puntaje)] = await repo.search_by_keywords([[1.0, 0.0]], limit=10)

    assert puntaje == 0.0


@pytest.mark.anyio
async def test_search_by_keywords_filtra_por_estado_y_region_antes_del_corte() -> None:
    """El filtro se aplica al conjunto elegible y el límite después: con el filtro
    activo el top-K se llena solo con licitaciones que califican."""
    repo = InMemoryTenderItemVectorRepository()
    mejor_pero_cerrada, publicada_rm, publicada_otra_region = uuid4(), uuid4(), uuid4()
    await repo.upsert(mejor_pero_cerrada, [[1.0, 0.0]], {"status_code": "cerrada", "region_id": 13})
    await repo.upsert(publicada_rm, [[1.0, 1.0]], {"status_code": "publicada", "region_id": 13})
    await repo.upsert(
        publicada_otra_region, [[1.0, 0.0]], {"status_code": "publicada", "region_id": 5}
    )

    resultados = await repo.search_by_keywords(
        [[1.0, 0.0]],
        limit=1,
        criteria=TenderFilterCriteria(status_codes=["publicada"], region_ids=[13]),
    )

    assert [tid for tid, _ in resultados] == [publicada_rm]


@pytest.mark.anyio
async def test_search_by_keywords_con_criterio_excluye_puntos_sin_payload() -> None:
    """Como Qdrant: una condición no calza contra un campo ausente."""
    repo = InMemoryTenderItemVectorRepository()
    sin_payload, con_payload = uuid4(), uuid4()
    await repo.upsert(sin_payload, [[1.0, 0.0]])
    await repo.upsert(con_payload, [[1.0, 0.0]], _PUBLICADA_RM)

    con_criterio = await repo.search_by_keywords(
        [[1.0, 0.0]], limit=10, criteria=TenderFilterCriteria(status_codes=["publicada"])
    )
    sin_criterio = await repo.search_by_keywords([[1.0, 0.0]], limit=10)

    assert [tid for tid, _ in con_criterio] == [con_payload]
    assert {tid for tid, _ in sin_criterio} == {sin_payload, con_payload}


@pytest.mark.anyio
async def test_search_by_keywords_interpreta_el_resto_de_los_criterios_como_tenders() -> None:
    repo = InMemoryTenderItemVectorRepository()
    dentro, fuera = uuid4(), uuid4()
    dentro_payload = {
        "status_code": "publicada",
        "region_id": 13,
        "provincia_id": 51,
        "comuna_id": 295,
        "available_amount_clp": 1_000_000.0,
        "closing_at": to_utc_epoch(datetime(2026, 8, 15)),
        "published_at": to_utc_epoch(datetime(2026, 7, 1)),
    }
    await repo.upsert(dentro, [[1.0, 0.0]], dentro_payload)
    await repo.upsert(fuera, [[1.0, 0.0]], {**dentro_payload, "comuna_id": 300})

    async def buscar(**criterios) -> list[UUID]:
        resultados = await repo.search_by_keywords(
            [[1.0, 0.0]], limit=10, criteria=TenderFilterCriteria(**criterios)
        )
        return [tid for tid, _ in resultados]

    assert await buscar(commune_id=295) == [dentro]
    assert await buscar(province_id=51) == [dentro, fuera]
    assert await buscar(min_amount=1_000_000.0, max_amount=1_000_000.0) == [dentro, fuera]
    assert await buscar(min_amount=1_000_001.0) == []
    assert await buscar(closing_from=datetime(2026, 8, 1), closing_to=datetime(2026, 8, 31)) == [
        dentro,
        fuera,
    ]
    assert await buscar(closing_from=datetime(2026, 9, 1)) == []
    assert await buscar(published_to=datetime(2026, 6, 30)) == []
