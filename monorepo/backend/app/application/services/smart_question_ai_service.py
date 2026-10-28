from abc import ABC, abstractmethod
from typing import Annotated

from pydantic import BaseModel, Field

from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender


class DynamicQuestionDTO(BaseModel):
    """Representa una pregunta inteligente generada dinámicamente por la IA."""

    question: str
    target_keyword: str
    options: list[str] = Field(default_factory=lambda: ["Sí", "No"])


class ISmartQuestionAIService(ABC):
    """Contrato abstracto para el servicio de generación de preguntas estratégicas con IA."""

    @abstractmethod
    async def generate_questions(
        self,
        tender: Tender,
        supplier: Supplier,
        attachment_texts: list[str],
        valid_negative_keywords: list[str],
    ) -> list[DynamicQuestionDTO]:
        """Contrasta la licitación y sus bases contra el perfil del proveedor,

        omitiendo capacidades excluidas (memoria negativa), para formular preguntas
        estratégicas que cubran vacíos de compatibilidad.
        """
        pass
