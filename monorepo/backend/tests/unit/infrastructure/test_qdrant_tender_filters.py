"""La traducción criterio -> filtro de Qdrant y los índices de payload son compartidos.

Las colecciones "tenders" y "tender_items" guardan el MISMO payload y se filtran con
los MISMOS criterios; si cada repositorio tuviera su propia traducción, una
divergencia haría que la misma búsqueda devolviera cosas distintas según el canal
de recuperación. Estos tests fijan el contrato del módulo compartido.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.schemas.tender_schema import TenderFilterCriteria
from app.infrastructure.repositories.qdrant_tender_filters import (
    PAYLOAD_INDEXES,
    build_filter,
    ensure_payload_indexes,
)
from app.infrastructure.repositories.qdrant_tender_item_vector_repository import (
    QdrantTenderItemVectorRepository,
)
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.shared.datetime_utils import to_utc_epoch


def _por_clave(filtro) -> dict:
    assert filtro is not None, "se esperaba un filtro, llegó None"
    return {c.key: c for c in filtro.must}


# ---------------------------------------------------------------------------
# build_filter
# ---------------------------------------------------------------------------


def test_sin_criterio_no_hay_filtro() -> None:
    assert build_filter(None) is None


def test_un_criterio_vacio_no_hay_filtro() -> None:
    """`Filter(must=[])` no equivale a "sin filtro" en Qdrant: hay que devolver None."""
    assert build_filter(TenderFilterCriteria()) is None


def test_las_listas_se_traducen_a_match_any() -> None:
    filtro = build_filter(
        TenderFilterCriteria(status_codes=["publicada", "cerrada"], region_ids=[13, 5])
    )

    condiciones = _por_clave(filtro)
    assert condiciones["status_code"].match.any == ["publicada", "cerrada"]
    assert condiciones["region_id"].match.any == [13, 5]


def test_provincia_y_comuna_se_traducen_a_match_value() -> None:
    filtro = build_filter(TenderFilterCriteria(province_id=22, commune_id=333))

    condiciones = _por_clave(filtro)
    assert condiciones["provincia_id"].match.value == 22
    assert condiciones["comuna_id"].match.value == 333


def test_el_rango_de_monto_es_inclusivo_y_admite_un_solo_extremo() -> None:
    ambos = _por_clave(
        build_filter(TenderFilterCriteria(min_amount=100.0, max_amount=500.0))
    )["available_amount_clp"].range
    solo_minimo = _por_clave(build_filter(TenderFilterCriteria(min_amount=100.0)))[
        "available_amount_clp"
    ].range

    assert (ambos.gte, ambos.lte) == (100.0, 500.0)
    assert ambos.gt is None and ambos.lt is None
    assert solo_minimo.gte == 100.0 and solo_minimo.lte is None


def test_las_fechas_pasan_a_epoch() -> None:
    desde = datetime(2026, 8, 1)
    hasta = datetime(2026, 8, 31, 23, 59)

    condiciones = _por_clave(
        build_filter(
            TenderFilterCriteria(
                closing_from=desde, closing_to=hasta, published_from=desde
            )
        )
    )

    assert condiciones["closing_at"].range.gte == to_utc_epoch(desde)
    assert condiciones["closing_at"].range.lte == to_utc_epoch(hasta)
    assert condiciones["published_at"].range.gte == to_utc_epoch(desde)
    assert condiciones["published_at"].range.lte is None


def test_todas_las_condiciones_van_en_un_must() -> None:
    filtro = build_filter(
        TenderFilterCriteria(
            status_codes=["publicada"],
            region_ids=[13],
            province_id=22,
            commune_id=333,
            closing_from=datetime(2026, 8, 1),
            published_to=datetime(2026, 9, 1),
            min_amount=1000.0,
        )
    )

    assert set(_por_clave(filtro)) == {
        "status_code",
        "region_id",
        "provincia_id",
        "comuna_id",
        "closing_at",
        "published_at",
        "available_amount_clp",
    }


# ---------------------------------------------------------------------------
# Índices de payload
# ---------------------------------------------------------------------------


def test_los_indices_cubren_los_campos_que_filtra_build_filter() -> None:
    """Todo campo por el que `build_filter` puede filtrar tiene su índice."""
    filtro = build_filter(
        TenderFilterCriteria(
            status_codes=["publicada"],
            region_ids=[13],
            province_id=22,
            commune_id=333,
            closing_from=datetime(2026, 8, 1),
            published_from=datetime(2026, 8, 1),
            min_amount=1.0,
        )
    )

    assert set(_por_clave(filtro)) == set(PAYLOAD_INDEXES)


def test_cada_indice_declara_su_tipo() -> None:
    """Un rango sobre un campo indexado como `keyword` no compara como número."""
    assert PAYLOAD_INDEXES == {
        "status_code": "keyword",
        "region_id": "integer",
        "provincia_id": "integer",
        "comuna_id": "integer",
        "available_amount_clp": "float",
        "closing_at": "integer",
        "published_at": "integer",
    }


@pytest.mark.anyio
async def test_ensure_payload_indexes_crea_un_indice_por_campo_en_la_coleccion() -> None:
    client = AsyncMock()

    await ensure_payload_indexes(client, "una_coleccion")

    llamadas = {
        c.kwargs["field_name"]: c.kwargs for c in client.create_payload_index.call_args_list
    }
    assert set(llamadas) == set(PAYLOAD_INDEXES)
    assert all(k["collection_name"] == "una_coleccion" for k in llamadas.values())
    assert {n: k["field_schema"] for n, k in llamadas.items()} == PAYLOAD_INDEXES


@pytest.mark.anyio
async def test_las_dos_colecciones_indexan_exactamente_lo_mismo() -> None:
    """"tenders" y "tender_items" comparten payload: sus índices no pueden divergir."""
    client_tenders, client_partidas = AsyncMock(), AsyncMock()
    existentes = MagicMock()
    existentes.collections = []
    client_tenders.get_collections.return_value = existentes
    client_partidas.get_collections.return_value = existentes

    await QdrantTenderRepository(client_tenders, vector_size=4).ensure_collection()
    await QdrantTenderItemVectorRepository(
        client_partidas, vector_size=4
    ).ensure_collection()

    def indices(client) -> dict:
        return {
            c.kwargs["field_name"]: c.kwargs["field_schema"]
            for c in client.create_payload_index.call_args_list
        }

    assert indices(client_tenders) == indices(client_partidas) == PAYLOAD_INDEXES
