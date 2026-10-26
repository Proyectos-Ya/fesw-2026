"""Punto de extensión "una versión entró o salió de lo compartido" (plan 233, decisión 6).

La decisión 4 (resumen compartido de los anexos) se cuelga de acá para reconstruir
lo que ven todas las empresas sin tocar la promoción.

Contrato:

- `file` es la **versión canónica** (sin empresa) después del cambio. Con
  `visibility == shared` entra al resumen compartido; con `private` sale de él
  (hubo un conflicto o la reemplazó otra versión).
- Se invoca después del commit de la promoción y fuera del candado del anexo. Un
  fallo solo se registra: la promoción ya se guardó.
- Puede repetirse para la misma fila (dos promociones, o una que se reintenta), así
  que lo que se cuelgue acá tiene que ser idempotente.
- No lleva sesión de base de datos: si necesita una, que abra la suya.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.domain.entities.attachment_file import AttachmentFile

logger = logging.getLogger(__name__)


class IAttachmentVisibilityListener(ABC):
    @abstractmethod
    async def on_visibility_changed(self, file: AttachmentFile) -> None: ...


class NoopAttachmentVisibilityListener(IAttachmentVisibilityListener):
    async def on_visibility_changed(self, file: AttachmentFile) -> None:
        return None


class CompositeAttachmentVisibilityListener(IAttachmentVisibilityListener):
    """Avisa a todos en orden; si uno falla, lo registra y sigue con el siguiente."""

    def __init__(self, listeners: Sequence[IAttachmentVisibilityListener]) -> None:
        self.listeners = list(listeners)

    async def on_visibility_changed(self, file: AttachmentFile) -> None:
        for listener in self.listeners:
            try:
                await listener.on_visibility_changed(file)
            except Exception:
                logger.exception(
                    "Un listener de visibilidad de anexos falló (%s, archivo %s).",
                    type(listener).__name__,
                    file.id,
                )
