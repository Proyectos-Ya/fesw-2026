"""Caso de uso del mapa de licitaciones (HU-22, #314)."""

from datetime import datetime
from uuid import uuid4

import pytest

from app.application.repositories.tender_map_repository import ITenderMapRepository
from app.application.use_cases.tender.get_tenders_map import (
    MAP_RESULT_LIMIT,
    GetTendersMapUseCase,
)
from app.domain.entities.tender_map import GeoPrecision, TenderMapPoint
from app.domain.errors.tender_errors import InvalidSearchCriteria


def _punto() -> TenderMapPoint:
    return TenderMapPoint(
        id=uuid4(),
        name="Insumos",
        buyer_name="Municipalidad de Ancud",
        delivery_address="Yerbas Buenas #915",
        closing_at=datetime(2026, 11, 3, 15, 0),
        lat=-41.87,
        lng=-73.82,
        precision=GeoPrecision.DIRECCION,
    )


class FakeMapRepository(ITenderMapRepository):
    def __init__(self, puntos: list[TenderMapPoint], total: int | None = None):
        self.puntos = puntos
        self.total = len(puntos) if total is None else total
        self.pedidos: list[tuple[int, int]] = []

    async def list_open_with_location(
        self, region_id: int, limit: int
    ) -> tuple[list[TenderMapPoint], int]:
        self.pedidos.append((region_id, limit))
        return self.puntos[:limit], self.total


@pytest.mark.parametrize(
    "nombre",
    ["Los Lagos", "los lagos", "Región de Los Lagos"],
)
async def test_reconoce_la_region_como_la_nombre_el_frontend(nombre):
    repo = FakeMapRepository([_punto()])

    resultado = await GetTendersMapUseCase(repo).execute(nombre)

    assert repo.pedidos == [(10, MAP_RESULT_LIMIT)]
    assert resultado.region == "Los Lagos"
    assert len(resultado.items) == 1


async def test_el_nombre_del_wizard_tambien_vale():
    repo = FakeMapRepository([])

    resultado = await GetTendersMapUseCase(repo).execute("Metropolitana")

    assert repo.pedidos[0][0] == 13
    assert resultado.region == "Metropolitana de Santiago"


async def test_una_region_desconocida_es_un_criterio_invalido():
    with pytest.raises(InvalidSearchCriteria):
        await GetTendersMapUseCase(FakeMapRepository([])).execute("Narnia")


async def test_avisa_si_el_tope_dejo_marcadores_fuera():
    repo = FakeMapRepository([_punto()], total=900)

    resultado = await GetTendersMapUseCase(repo).execute("Los Lagos")

    assert resultado.total == 900
    assert resultado.is_truncated is True


async def test_sin_resultados_responde_vacio_sin_error():
    resultado = await GetTendersMapUseCase(FakeMapRepository([])).execute("Ñuble")

    assert resultado.items == []
    assert resultado.total == 0
    assert resultado.is_truncated is False
