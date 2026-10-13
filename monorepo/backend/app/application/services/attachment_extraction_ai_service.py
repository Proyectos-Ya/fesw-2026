"""Puerto para el servicio de extracción de anexos con Gemini (plan 233, decisión 4)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.domain.entities.attachment_extraction import (
    AttachmentExtractionData,
    ExtractionInputMode,
)


@dataclass(frozen=True)
class ExtractionDocument:
    name: str
    sha256: str
    tender_code: str
    tender_name: str
    mime: str  # application/pdf, image/*, text/plain
    data: bytes | None = None  # PDF o imagen
    text: str | None = None  # docx o xlsx ya convertidos
    pages: int | None = None


@dataclass(frozen=True)
class ExtractionAIResult:
    data: AttachmentExtractionData  # validado y saneado
    model: str
    input_mode: ExtractionInputMode
    usage_metadata: dict[str, Any]


class IAttachmentExtractionAIService(ABC):
    @abstractmethod
    async def extract(self, document: ExtractionDocument) -> ExtractionAIResult: ...
