"""Lo que encola la red de seguridad nocturna queda etiquetado como `nueva`.

El 2026-10-14 la nocturna dejó 63 filas pendientes sin etiqueta: se procesaban
igual, pero detrás de las `nueva` y sin que la cola dijera por qué estaban.
"""

from datetime import datetime
from typing import Any

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.repositories.tender_model import TenderMetadataModel
from app.infrastructure.services.tenders.mercado_publico_client import (
    ListadoLicitaciones,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)

pytestmark = pytest.mark.asyncio


def _item(code: str) -> dict[str, Any]:
    return {
        "codigo": code,
        "estado": {"id_estado": 2, "codigo": "publicada"},
        "fechas": {"fecha_cierre": "2099-01-01 10:00"},
        "institucion": {"nombre_region": "Región Metropolitana de Santiago"},
    }


class ClienteFalso:
    async def get_tenders(self, *_args, **_kwargs) -> ListadoLicitaciones:
        return ListadoLicitaciones(items=[_item("NUEVA-1")], completo=True)


async def test_la_red_de_seguridad_encola_como_nueva(integration_engine):
    servicio = TenderIngestionService(
        engine=integration_engine,
        client=ClienteFalso(),  # type: ignore[arg-type]
        embedding_service=None,  # type: ignore[arg-type]
    )

    resultado = await servicio.fetch_tenders_metadata(
        desde=datetime(2026, 10, 13, 0, 0),
        hasta=datetime(2026, 10, 13, 6, 0),
        por_publicacion=True,
        estado="publicada",
    )

    async with AsyncSession(integration_engine) as s:
        fila = (
            await s.exec(
                select(TenderMetadataModel).where(
                    TenderMetadataModel.code == "NUEVA-1"
                )
            )
        ).one()
    assert resultado.nuevas == 1
    assert fila.pending_reason == "nueva"
