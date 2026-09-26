"""Refresco de una licitación puntual para detectar cambios de fecha (HU-16)."""

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.application.services.tender_refresher import OfficialTenderDates
from app.infrastructure.services.milestone_refresh_scheduler import (
    MilestoneRefreshScheduler,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)
from app.infrastructure.services.tenders.tender_refresher import (
    MercadoPublicoTenderRefresher,
)

DETALLE: dict[str, Any] = {
    "codigo": "COT-1",
    "nombre": "Reparación de techumbre",
    "estado": {"id_estado": 2, "codigo": "publicada"},
    # Mercado Público entrega hora de Chile sin zona: 15:00 en octubre = 18:00 UTC.
    "fechas": {"fecha_publicacion": "2026-10-01T10:00:00", "fecha_cierre": "2026-10-27T15:00:00"},
    "institucion": {"rut": "1-9", "organismo_comprador": "Municipalidad", "unidad_compra": "Ops", "region": 13},
    "presupuesto": {"monto_disponible_clp": 1000},
    "productos_solicitados": [],
}


class ClienteFalso:
    def __init__(self, detalle: dict[str, Any]) -> None:
        self.detalle = detalle

    async def get_tender_detail(self, code: str) -> dict[str, Any]:
        return self.detalle


def _servicio(detalle: dict[str, Any]) -> tuple[TenderIngestionService, AsyncMock]:
    servicio = TenderIngestionService(
        engine=create_async_engine("sqlite+aiosqlite://"),
        client=ClienteFalso(detalle),  # type: ignore[arg-type]
        embedding_service=AsyncMock(),
        tender_vector_repo=AsyncMock(),
    )
    use_case = AsyncMock()
    servicio._construir_use_case = lambda session: use_case  # type: ignore[method-assign]
    return servicio, use_case


class TestRefrescoEnLaIngesta:
    async def test_actualiza_la_licitacion_con_la_ingesta_de_siempre(self):
        servicio, use_case = _servicio(DETALLE)

        dto = await servicio.refresh_tender("COT-1")

        assert dto is not None
        use_case.execute.assert_awaited_once_with(dto)
        assert dto.closing_at == datetime(2026, 10, 27, 18, 0)

    async def test_sin_detalle_no_actualiza_nada(self):
        servicio, use_case = _servicio({})

        assert await servicio.refresh_tender("COT-1") is None
        use_case.execute.assert_not_awaited()

    @pytest.mark.parametrize("falta", ["fecha_publicacion", "fecha_cierre"])
    async def test_sin_fechas_oficiales_no_actualiza(self, falta):
        # El parser las reemplazaría por "ahora", lo que parecería un cambio de fecha.
        detalle = {**DETALLE, "fechas": {k: v for k, v in DETALLE["fechas"].items() if k != falta}}
        servicio, use_case = _servicio(detalle)

        assert await servicio.refresh_tender("COT-1") is None
        use_case.execute.assert_not_awaited()


class TestAdaptador:
    async def test_devuelve_las_fechas_oficiales(self):
        servicio, _ = _servicio(DETALLE)

        fechas = await MercadoPublicoTenderRefresher(servicio).refresh("COT-1")

        assert fechas == OfficialTenderDates(
            published_at=datetime(2026, 10, 1, 13, 0),
            closing_at=datetime(2026, 10, 27, 18, 0),
        )

    async def test_sin_detalle_devuelve_none(self):
        servicio, _ = _servicio({})

        assert await MercadoPublicoTenderRefresher(servicio).refresh("COT-1") is None


class TestScheduler:
    async def test_un_error_no_detiene_el_loop(self):
        llamadas = 0

        async def refrescar() -> int:
            nonlocal llamadas
            llamadas += 1
            if llamadas == 1:
                raise RuntimeError("Mercado Público caído")
            return 1

        tarea = asyncio.create_task(
            MilestoneRefreshScheduler(refrescar, interval_seconds=0).start_loop()
        )
        while llamadas < 3:
            await asyncio.sleep(0)
        tarea.cancel()

        assert llamadas >= 3
