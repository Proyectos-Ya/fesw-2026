"""Contrato de la IA que analiza la factibilidad de una postulación (HU-20, B2)."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from app.application.services.tender_assistant_ai_service import DocumentContextDTO
from app.domain.entities.capability import (
    CapabilityKind,
    CapabilityQuestion,
    ExperienceCatalog,
)
from app.domain.entities.proposal import (
    ProposalWarning,
    Requirement,
    RequirementKind,
)
from app.domain.entities.tender import Tender


class NewQuestionDTO(BaseModel):
    """Pregunta que la IA propone sumar al banco, porque ninguna cubre la exigencia.

    Se redacta neutra y en tercera persona: el banco es compartido y la
    verían todas las empresas (`question_leaks_supplier_data` lo verifica).
    """

    question: str
    # Clave normalizada, por ejemplo `sec_clase_a` o `experiencia:obras-viales`.
    target_field: str
    kind: CapabilityKind
    # Solo en `experiencia_proyecto`.
    work_type: str | None = None


class FeasibilityRequirementDTO(BaseModel):
    """Una exigencia de las bases y cómo la cubre (o no) lo que se sabe de la empresa.

    Exactamente una de tres cosas:
    - `catalog_item_id`: un elemento del catálogo la cubre, a favor o en contra;
    - `question_key`: una pregunta del banco que la empresa aún no respondió;
    - `new_question`: ninguna pregunta del banco sirve, y se propone una.
    """

    text: str
    kind: RequirementKind
    mandatory: bool
    origin: str
    catalog_item_id: str | None = None
    question_key: str | None = None
    new_question: NewQuestionDTO | None = None


class FeasibilityResultDTO(BaseModel):
    requirements: list[FeasibilityRequirementDTO] = Field(default_factory=list)
    requires_technical_document: bool = False
    technical_document_reason: str | None = None


class DraftParagraphDTO(BaseModel):
    """Un párrafo tal como lo redacta la IA.

    `text` puede traer marcas `[[INSERTAR: X]]` donde falta un dato (CA2).
    `source_ids` son ids del catálogo que lo respaldan (CA5); el caso de uso
    descarta los que no existan. `asserts_company_fact` indica si el párrafo
    afirma algo de la empresa (experiencia, certificaciones, capacidad): si es
    así y no queda ninguna fuente válida, se le agrega un vacío en vez de dejar
    una afirmación sin respaldo.
    """

    text: str
    source_ids: list[str] = Field(default_factory=list)
    asserts_company_fact: bool = False


class DraftSectionDTO(BaseModel):
    paragraphs: list[DraftParagraphDTO] = Field(default_factory=list)


class DraftContentDTO(BaseModel):
    offer_name: DraftSectionDTO
    offer_description: DraftSectionDTO
    # Documentos que la IA encuentre además de los detectados en la factibilidad.
    required_documents: DraftSectionDTO = Field(default_factory=DraftSectionDTO)
    technical_document: DraftSectionDTO | None = None


class ProposalAIServiceError(Exception):
    """La IA no respondió o respondió algo que no se pudo interpretar. La API da 502."""


class IProposalAIService(ABC):
    @abstractmethod
    async def analyze_feasibility(
        self,
        tender: Tender,
        catalog: ExperienceCatalog,
        bank_questions: list[CapabilityQuestion],
        documents: list[DocumentContextDTO],
    ) -> FeasibilityResultDTO:
        """Extrae todas las exigencias y decide, para cada una, qué la cubre.

        Recibe el catálogo completo de la empresa y las preguntas activas del
        banco para su rubro: con eso no vuelve a preguntar lo que ya se sabe ni
        crea preguntas repetidas.
        """

    @abstractmethod
    async def generate_draft(
        self,
        tender: Tender,
        requirements: list[Requirement],
        catalog: ExperienceCatalog,
        warnings: list[ProposalWarning],
        include_technical_document: bool,
        documents: list[DocumentContextDTO],
        instructions: str | None = None,
    ) -> DraftContentDTO:
        """Redacta el borrador de la oferta (CA1, CA2, CA5).

        Solo puede citar ids del catálogo y debe marcar con `[[INSERTAR: X]]` lo
        que no sabe, en vez de inventarlo. `instructions` son las indicaciones
        del usuario para regenerar (CA4).
        """
