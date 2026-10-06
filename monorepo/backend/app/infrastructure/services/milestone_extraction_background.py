"""Extraer los hitos de las bases en segundo plano, con tareas de asyncio (HU-16).

Asume **una sola instancia** de la API, como las exportaciones de la HdU 19: el
estado vive en la memoria del proceso. Si la API se reinicia a mitad de camino,
la extracción se pierde y el usuario la reintenta con el botón de la ficha.
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from app.application.services.milestone_extraction_background import (
    MilestoneExtraction,
    MilestoneExtractionStatus,
)
from app.application.use_cases.milestones.milestone_views import TenderMilestonesResult
from app.domain.errors.milestone_errors import MilestoneExtractionUnavailable

logger = logging.getLogger(__name__)

_Clave = tuple[UUID, UUID]


class AsyncioMilestoneExtractionBackground:
    def __init__(
        self, open_extraction: Callable[[], AbstractAsyncContextManager[MilestoneExtraction]]
    ):
        # Abre una sesión de base de datos por pasada: la de la subida ya se cerró.
        self._open_extraction = open_extraction
        # Sin una referencia fuerte, el recolector de basura puede llevarse la
        # tarea a mitad de camino (lo advierte la documentación de asyncio).
        self._tareas: dict[_Clave, asyncio.Task[None]] = {}
        self._repetir: set[_Clave] = set()
        self._fallidas: set[_Clave] = set()
        # Uno por usuario y licitación, compartido con la extracción manual. No
        # se borran: son pocos, y quitar uno mientras alguien lo espera dejaría
        # pasar a dos extracciones a la vez.
        self._candados: dict[_Clave, asyncio.Lock] = {}

    @property
    def pending(self) -> int:
        return len(self._tareas)

    def schedule(self, user_id: UUID, tender_id: UUID) -> None:
        clave = (user_id, tender_id)
        if clave in self._tareas:
            # Ya hay una en curso: al terminar hace una pasada más, que lee
            # también lo recién subido. Varias subidas seguidas cuestan dos
            # llamadas a Gemini, no una por archivo.
            self._repetir.add(clave)
            return
        self._tareas[clave] = asyncio.create_task(self._ciclo(clave))

    def status(self, user_id: UUID, tender_id: UUID) -> MilestoneExtractionStatus:
        clave = (user_id, tender_id)
        if clave in self._tareas:
            return MilestoneExtractionStatus.RUNNING
        if clave in self._fallidas:
            return MilestoneExtractionStatus.FAILED
        return MilestoneExtractionStatus.IDLE

    async def run_now(
        self, user_id: UUID, tender_id: UUID, extraction: MilestoneExtraction
    ) -> TenderMilestonesResult:
        clave = (user_id, tender_id)
        async with self._candado(clave):
            resultado = await extraction.execute(user_id, tender_id)
        self._fallidas.discard(clave)
        return resultado

    def _candado(self, clave: _Clave) -> asyncio.Lock:
        return self._candados.setdefault(clave, asyncio.Lock())

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
        user_id, tender_id = clave
        async with self._candado(clave):
            try:
                async with self._open_extraction() as extraer:
                    await extraer.execute(user_id, tender_id)
            except MilestoneExtractionUnavailable:
                # El servicio de Gemini ya registró el motivo.
                logger.warning("No se pudieron extraer los hitos de la licitación %s", tender_id)
                self._fallidas.add(clave)
                return
            except Exception:
                logger.exception("Falló la extracción automática de hitos de %s", tender_id)
                self._fallidas.add(clave)
                return
        self._fallidas.discard(clave)

    async def wait_idle(self) -> None:
        """Espera a que terminen las extracciones en curso (para los tests)."""
        if self._tareas:
            await asyncio.gather(*self._tareas.values(), return_exceptions=True)

    async def shutdown(self) -> None:
        for tarea in list(self._tareas.values()):
            tarea.cancel()
        await self.wait_idle()
