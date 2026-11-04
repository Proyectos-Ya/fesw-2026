"""Puerto para inspeccionar y extraer texto de documentos de anexos (plan 233, decisión 4)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.services.attachment_file_signatures import (
    ArchivoInspeccionado,
    FormatoLegible,
)

MIN_CARACTERES_DE_TEXTO = 50


@dataclass(frozen=True)
class SeccionDeTexto:
    etiqueta: str  # número de página, nombre de hoja o "documento"
    texto: str


@dataclass(frozen=True)
class TextoDelDocumento:
    secciones: tuple[SeccionDeTexto, ...]
    para_modelo: str | None = None  # docx/xlsx: lo que se manda a Gemini; PDF e imagen: None
    paginas: int | None = None

    @property
    def disponible(self) -> bool:
        return (
            sum(c.isalnum() for s in self.secciones for c in s.texto)
            >= MIN_CARACTERES_DE_TEXTO
        )


class IAttachmentContentReader(ABC):
    @abstractmethod
    async def inspect(self, data: bytes, ext: str) -> ArchivoInspeccionado: ...

    @abstractmethod
    async def read_text(
        self, data: bytes, formato: FormatoLegible, *, nombre: str
    ) -> TextoDelDocumento: ...
