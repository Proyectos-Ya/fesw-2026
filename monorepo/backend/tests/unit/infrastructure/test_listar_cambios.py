"""El servicio lista los cambios recientes y los traduce, sin tocar la base.

Tres cosas que el cron de estados necesita del listado:

- ventana de **cambios** (`ttl_cambio_ms`), no de publicación;
- **sin filtro de estado**, o las desiertas y canceladas no llegarían nunca;
- saber si el listado vino completo, que decide el código de salida.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

from app.infrastructure.services.tenders.mercado_publico_client import (
    ListadoLicitaciones,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)

FIXTURE = Path(__file__).parents[2] / "fixtures" / "mp_listado_cambios.json"


class ClienteFalso:
    def __init__(self, items: list[dict[str, Any]], completo: bool = True) -> None:
        self.items = items
        self.completo = completo
        self.llamadas: list[dict[str, Any]] = []

    async def get_tenders(
        self,
        from_date: datetime,
        to_date: datetime,
        quantity: int,
        *,
        por_publicacion: bool = False,
        estado: str | None = None,
    ) -> ListadoLicitaciones:
        self.llamadas.append(
            {
                "ventana": to_date - from_date,
                "quantity": quantity,
                "por_publicacion": por_publicacion,
                "estado": estado,
            }
        )
        return ListadoLicitaciones(items=self.items, completo=self.completo)


def _items() -> list[dict[str, Any]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["payload"]["items"]


def _servicio(cliente: ClienteFalso) -> TenderIngestionService:
    return TenderIngestionService(
        engine=cast(Any, None),
        client=cast(Any, cliente),
        embedding_service=cast(Any, None),
    )


class TestListarCambios:
    async def test_pide_la_ventana_de_cambios_sin_filtro_de_estado(self):
        cliente = ClienteFalso(_items())

        await _servicio(cliente).listar_cambios(timedelta(hours=6), limite=9000)

        assert cliente.llamadas == [
            {
                "ventana": timedelta(hours=6),
                "quantity": 9000,
                "por_publicacion": False,
                "estado": None,
            }
        ]

    async def test_traduce_todos_los_estados(self):
        listado = await _servicio(ClienteFalso(_items())).listar_cambios(
            timedelta(hours=6), limite=9000
        )

        assert listado.listadas == 4
        assert listado.completo is True
        assert sorted(c.status_code for c in listado.cambios) == [
            "cancelada",
            "cerrada",
            "desierta",
            "publicada",
        ]

    async def test_los_items_ilegibles_se_cuentan_pero_no_se_devuelven(self):
        items = [*_items(), {"codigo": "ROTO"}]

        listado = await _servicio(ClienteFalso(items)).listar_cambios(
            timedelta(hours=6), limite=9000
        )

        assert listado.listadas == 5
        assert len(listado.cambios) == 4
        assert listado.ilegibles == 1

    async def test_propaga_el_listado_incompleto(self):
        listado = await _servicio(
            ClienteFalso(_items(), completo=False)
        ).listar_cambios(timedelta(hours=6), limite=9000)

        assert listado.completo is False
