"""Bucle del procesamiento de anexos (plan 233, decisión 4).

Mismo enfoque que `MilestoneRefreshScheduler` y `RankingTelemetryScheduler`: una tarea
asyncio en el lifespan, que asume una sola instancia. Con dos (solapamiento de deploy),
`SKIP LOCKED` evita que tomen el mismo trabajo y el tope diario es atómico.
Concurrencia 1 a propósito: el proceso ya carga el modelo de ~3 GB y cada archivo
puede ocupar 50 MB más sus copias.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from app.application.services.attachment_processing_notifier import (
    IAttachmentProcessingNotifier,
)

logger = logging.getLogger(__name__)


class AsyncioProcessingSignal(IAttachmentProcessingNotifier):
    def __init__(self) -> None:
        self._evento: asyncio.Event | None = None

    def conectar(self) -> asyncio.Event:
        # Se crea dentro del loop del lifespan: un Event creado al importar quedaría atado a otro loop.
        self._evento = asyncio.Event()
        return self._evento

    def notify(self) -> None:
        if self._evento is not None:  # sin scheduler (flag apagado, tests) no hace nada
            self._evento.set()


class AttachmentProcessingScheduler:
    def __init__(
        self,
        *,
        process_next: Callable[[], Awaitable[bool]],
        sweep: Callable[[], Awaitable[object]],
        signal: AsyncioProcessingSignal,
        poll_interval_seconds: float,
        sweep_interval_seconds: float,
        initial_delay_seconds: float = 2.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.process_next = process_next
        self.sweep = sweep
        self.signal = signal
        self.poll_interval_seconds = poll_interval_seconds
        self.sweep_interval_seconds = sweep_interval_seconds
        self.initial_delay_seconds = initial_delay_seconds
        self._monotonic = monotonic

    async def start_loop(self) -> None:
        evento = self.signal.conectar()
        logger.info(
            "Procesando anexos (aviso inmediato o cada %s s)",
            self.poll_interval_seconds,
        )
        await asyncio.sleep(self.initial_delay_seconds)  # no compite con el arranque
        proximo_barrido = 0.0
        while True:
            evento.clear()  # antes de vaciar: un aviso que llegue mientras tanto no se pierde
            try:
                if self._monotonic() >= proximo_barrido:
                    proximo_barrido = self._monotonic() + self.sweep_interval_seconds
                    await self.sweep()
                while await self.process_next():  # uno por vez: concurrencia 1
                    await asyncio.sleep(0)
            except Exception as error:
                # Un fallo no puede matar el loop: la próxima vuelta lo reintenta.
                logger.warning("Error en el procesamiento de anexos: %s", error)
            try:
                await asyncio.wait_for(
                    evento.wait(), timeout=self.poll_interval_seconds
                )
            except TimeoutError:
                pass
