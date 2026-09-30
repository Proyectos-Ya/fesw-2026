from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.application.services.tender_assistant_ai_service import DocumentContextDTO


class ExtractedMilestone(BaseModel):
    """Hito tal como lo entrega el motor de IA, antes de validar su fecha."""

    kind: str
    title: str
    description: str | None = None
    fecha: str
    hora: str | None = None
    texto_original: str | None = None
    documento: str | None = None


class IMilestoneExtractionAIService(ABC):
    @abstractmethod
    async def extract(
        self, documents: list[DocumentContextDTO], tender_context: str
    ) -> list[ExtractedMilestone]:
        """Identifica en los documentos los párrafos con plazos, entregas o visitas."""
