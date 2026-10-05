"""Punto de extensión "se borró el archivo de una empresa" (plan 233, decisión 6).

Borrar una captura que contradecía una versión compartida la destraba, y borrar un
aporte puede deshacer una corroboración: la promoción reevalúa el anexo desde acá.

Se invoca **después** de borrar la fila, con la entidad que se borró, y un fallo
solo se registra: el borrado ya ocurrió. Lo que se cuelgue acá tiene que ser
idempotente.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.domain.entities.attachment_file import AttachmentFile

logger = logging.getLogger(__name__)


class IAttachmentDeletedListener(ABC):
    @abstractmethod
    async def on_deleted(self, file: AttachmentFile) -> None: ...


class NoopAttachmentDeletedListener(IAttachmentDeletedListener):
    async def on_deleted(self, file: AttachmentFile) -> None:
        return None


class CompositeAttachmentDeletedListener(IAttachmentDeletedListener):
    """Avisa a todos en orden; si uno falla, lo registra y sigue con el siguiente."""

    def __init__(self, listeners: Sequence[IAttachmentDeletedListener]) -> None:
        self.listeners = list(listeners)

    async def on_deleted(self, file: AttachmentFile) -> None:
        for listener in self.listeners:
            try:
                await listener.on_deleted(file)
            except Exception:
                logger.exception(
                    "Un listener de archivos borrados falló (%s, archivo %s).",
                    type(listener).__name__,
                    file.id,
                )
