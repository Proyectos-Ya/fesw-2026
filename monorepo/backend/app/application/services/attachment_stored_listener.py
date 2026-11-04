"""Punto de extensión "el archivo quedó guardado" (plan 233, decisión 2).

La decisión 4 (extracción de texto) y la 6 (promoción a compartido) se cuelgan
de acá sin tocar los casos de uso de la subida ni pelear el mismo archivo. Hoy
no hay ninguno: `NoopAttachmentStoredListener`.

Se invoca **después** de confirmar `stored`, y un fallo solo se registra: el
archivo ya está guardado, y que falle un trabajo posterior no debe devolverle un
error a quien lo subió. Por eso lo que se cuelgue acá tiene que ser idempotente.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.domain.entities.attachment_file import AttachmentFile

logger = logging.getLogger(__name__)


class IAttachmentStoredListener(ABC):
    @abstractmethod
    async def on_stored(self, file: AttachmentFile) -> None: ...


class NoopAttachmentStoredListener(IAttachmentStoredListener):
    async def on_stored(self, file: AttachmentFile) -> None:
        return None


class CompositeAttachmentStoredListener(IAttachmentStoredListener):
    """Avisa a todos en orden; si uno falla, lo registra y sigue con el siguiente."""

    def __init__(self, listeners: Sequence[IAttachmentStoredListener]) -> None:
        self.listeners = list(listeners)

    async def on_stored(self, file: AttachmentFile) -> None:
        for listener in self.listeners:
            try:
                await listener.on_stored(file)
            except Exception:
                logger.exception(
                    "Un listener de archivos guardados falló (%s, archivo %s).",
                    type(listener).__name__,
                    file.id,
                )
