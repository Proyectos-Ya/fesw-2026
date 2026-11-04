"""El listado de licitaciones nuevas también deja la lista oficial de anexos.

`fetch_tenders_metadata` ya recorre los ítems del listado para encolar los
códigos; juntar de paso sus `documentos` no cuesta ninguna petición. La lista se
devuelve en `ResultadoListado.documentos` y la aplica el cron al final de la
corrida, cuando las nuevas ya existen en `tender` (hay clave foránea).
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from app.infrastructure.services.tenders import tender_ingestion_service as modulo
from app.infrastructure.services.tenders.mercado_publico_client import (
    ListadoLicitaciones,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)

FIXTURE = Path(__file__).parents[2] / "fixtures" / "mp_listado_cambios.json"


class _SesionFalsa:
    """Reemplaza a `AsyncSession(engine)`: la consulta real no es lo que se prueba."""

    def __init__(self, *_: Any, **__: Any) -> None:
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self) -> "_SesionFalsa":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


class _ClienteFalso:
    def __init__(self, items: list[dict[str, Any]], completo: bool = True) -> None:
        self.items = items
        self.completo = completo

    async def get_tenders(self, *_: Any, **__: Any) -> ListadoLicitaciones:
        return ListadoLicitaciones(items=self.items, completo=self.completo)


def _items() -> list[dict[str, Any]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["payload"]["items"]


@pytest.fixture
def servicio_con(monkeypatch):
    def _armar(items: list[dict[str, Any]]) -> TenderIngestionService:
        monkeypatch.setattr(modulo, "AsyncSession", _SesionFalsa)
        servicio = TenderIngestionService(
            engine=MagicMock(),
            client=cast(Any, _ClienteFalso(items)),
            embedding_service=cast(Any, None),
        )
        monkeypatch.setattr(servicio, "_insertar_metadata", AsyncMock(return_value=0))
        return servicio

    return _armar


async def test_devuelve_la_lista_oficial_de_todos_los_items_listados(servicio_con):
    servicio = servicio_con(_items())

    resultado = await servicio.fetch_tenders_metadata(
        desde=datetime(2026, 9, 28, tzinfo=UTC), hasta=datetime(2026, 9, 29, tzinfo=UTC)
    )

    # Las cuatro, también las cerradas, desiertas y canceladas que no se encolan:
    # si ya las tenemos, igual conviene refrescar su lista.
    assert set(resultado.documentos) == {
        "5052-431-COT26",
        "5684-369-COT26",
        "1058078-836-COT26",
        "5153-1851-COT26",
    }
    assert resultado.documentos["5052-431-COT26"][0] == DocumentoOficialDTO(
        mp_document_id=1931002, nombre="Anexo 3 Composición personalidad juridica.xlsx"
    )
    assert resultado.documentos["5153-1851-COT26"] == []


async def test_un_item_con_documentos_ilegibles_no_deja_lista(servicio_con):
    items = [{**_items()[0], "documentos": [{"id": None}]}]
    servicio = servicio_con(items)

    resultado = await servicio.fetch_tenders_metadata(
        desde=datetime(2026, 9, 28, tzinfo=UTC), hasta=datetime(2026, 9, 29, tzinfo=UTC)
    )

    assert resultado.documentos == {}


async def test_si_el_listado_falla_no_hay_documentos(monkeypatch):
    class _ClienteRoto:
        async def get_tenders(self, *_: Any, **__: Any):
            raise RuntimeError("API caída")

    monkeypatch.setattr(modulo, "AsyncSession", _SesionFalsa)
    servicio = TenderIngestionService(
        engine=MagicMock(),
        client=cast(Any, _ClienteRoto()),
        embedding_service=cast(Any, None),
    )

    resultado = await servicio.fetch_tenders_metadata(dias=1)

    assert resultado.completo is False
    assert resultado.documentos == {}
