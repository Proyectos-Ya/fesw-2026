"""Analizar los anexos en segundo plano, con tareas de asyncio (plan 233).

Mismo patrón que la extracción de hitos: asume **una sola instancia** de la API
y el estado vive en la memoria del proceso. Si la API se reinicia a mitad de
camino, el análisis se pierde y se rehace con la siguiente subida.
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from app.application.services.tender_analysis_background import TenderAnalysis

logger = logging.getLogger(__name__)

_Clave = tuple[UUID, UUID]


class AsyncioTenderAnalysisBackground:
    def __init__(
        self, open_analysis: Callable[[], AbstractAsyncContextManager[TenderAnalysis]]
    ) -> None:
        self._open_analysis = open_analysis
        # Sin una referencia fuerte, el recolector de basura puede llevarse la
        # tarea a mitad de camino (lo advierte la documentación de asyncio).
        self._tareas: dict[_Clave, asyncio.Task[None]] = {}
        self._repetir: set[_Clave] = set()

    def schedule(self, workspace_id: UUID, tender_id: UUID) -> None:
        clave = (workspace_id, tender_id)
        if clave in self._tareas:
            # Ya hay uno en curso: al terminar hace una pasada más, que ve también
            # lo recién subido. Varias subidas seguidas cuestan dos llamadas.
            self._repetir.add(clave)
            return
        self._tareas[clave] = asyncio.create_task(self._ciclo(clave))

    def is_running(self, workspace_id: UUID, tender_id: UUID) -> bool:
        return (workspace_id, tender_id) in self._tareas

    async def _ciclo(self, clave: _Clave) -> None:
        try:
            while True:
                self._repetir.discard(clave)
                await self._pasada(clave)
                if clave not in self._repetir:
                    return
        finally:
            self._tareas.pop(clave, None)

    async def _pasada(self, clave: _Clave) -> None:
        workspace_id, tender_id = clave
        try:
            async with self._open_analysis() as analizar:
                await analizar.execute(workspace_id, tender_id)
        except Exception:
            # La siguiente subida lo reintenta; el usuario tiene además el botón
            # de análisis de la ficha.
            logger.exception("Falló el análisis de anexos de la licitación %s", tender_id)

    async def wait_idle(self) -> None:
        """Espera a que terminen los análisis en curso (para los tests)."""
        if self._tareas:
            await asyncio.gather(*self._tareas.values(), return_exceptions=True)

    async def shutdown(self) -> None:
        for tarea in list(self._tareas.values()):
            tarea.cancel()
        await self.wait_idle()
        # Una tarea cancelada antes de empezar no corre su `finally`.
        self._tareas.clear()
        self._repetir.clear()
