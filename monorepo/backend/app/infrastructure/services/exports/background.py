"""Terminar exportaciones después de responder, con tareas de asyncio (HdU 19).

Asume **una sola instancia** de la API, como los bucles de alertas: la tarea
vive en la memoria del proceso. Si la API se reinicia a mitad de camino, el
arranque marca el trabajo como fallido (`ReconcileExportJobsUseCase`).
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from app.domain.entities.export_job import ExportJob

logger = logging.getLogger(__name__)


class _Completar(Protocol):
    async def execute(
        self, job: ExportJob, render: "asyncio.Task[bytes]", recipient: str, tender_name: str
    ) -> object: ...


class AsyncioExportBackground:
    def __init__(self, open_completion: Callable[[], AbstractAsyncContextManager[_Completar]]):
        # Abre una sesión de base de datos por trabajo: la de la petición ya se
        # cerró cuando la tarea termina.
        self._open_completion = open_completion
        # Sin una referencia fuerte, el recolector de basura puede llevarse la
        # tarea a mitad de camino (lo advierte la documentación de asyncio).
        self._tareas: set[asyncio.Task[None]] = set()

    @property
    def pending(self) -> int:
        return len(self._tareas)

    def schedule(
        self, job: ExportJob, render: "asyncio.Task[bytes]", recipient: str, tender_name: str
    ) -> None:
        tarea = asyncio.create_task(self._completar(job, render, recipient, tender_name))
        self._tareas.add(tarea)
        tarea.add_done_callback(self._tareas.discard)

    async def _completar(
        self, job: ExportJob, render: "asyncio.Task[bytes]", recipient: str, tender_name: str
    ) -> None:
        try:
            async with self._open_completion() as completar:
                await completar.execute(job, render, recipient, tender_name)
        except asyncio.CancelledError:
            render.cancel()
            raise
        except Exception:
            logger.exception("No se pudo completar la exportación %s", job.id)

    async def wait_idle(self) -> None:
        """Espera a que terminen los trabajos en curso (para los tests)."""
        if self._tareas:
            await asyncio.gather(*self._tareas, return_exceptions=True)

    async def shutdown(self) -> None:
        for tarea in list(self._tareas):
            tarea.cancel()
        await self.wait_idle()
