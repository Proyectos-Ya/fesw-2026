from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities.capability import CapabilityQuestion, ExperienceItem
from app.domain.entities.proposal import DecisionAction, ProposalDraft


class ProposalDraftView(ProposalDraft):
    """El borrador tal como lo ve la API.

    `is_expired` no se guarda: se calcula al leer con `Tender.esta_cerrada()`,
    así ninguna lectura tiene que escribir. Un borrador vencido se sigue
    mostrando, pero ya no se puede avanzar.
    """

    is_expired: bool = False
    # Las preguntas a las que apuntan las exigencias, con enunciado y opciones.
    questions: list[CapabilityQuestion] = Field(default_factory=list)
    # Los elementos del catálogo que cubren alguna exigencia: explican una pausa.
    catalog_items: list[ExperienceItem] = Field(default_factory=list)
    # Exigencias cuya respuesta en el banco cambió desde que se usó (por ejemplo
    # corregida en otra pantalla). Se aplican con `POST /sync-answers`.
    changed_requirement_ids: list[str] = Field(default_factory=list)


class AnswerProposalQuestionInput(BaseModel):
    """Respuesta a una pregunta de la postulación.

    Sin `supplier_id`: la empresa sale de la sesión. `extra="forbid"` rechaza a
    quien lo mande.
    """

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=500)


class DecideDiscrepancyInput(BaseModel):
    """Decisión ante un "No" a una exigencia excluyente (CA8, CA9).

    `requirement_id` es la exigencia que el usuario vio en el aviso: si la pausa
    ya es otra, la API responde 409 en vez de decidir sobre algo que no vio.
    """

    model_config = ConfigDict(extra="forbid")

    requirement_id: str = Field(min_length=1)
    action: DecisionAction


class RegenerateProposalInput(BaseModel):
    """Instrucciones libres para volver a redactar el borrador (CA4)."""

    model_config = ConfigDict(extra="forbid")

    instructions: str = Field(min_length=1, max_length=1000)


# --- HU-032: Postulación en Mercado Público ---

class PostulationTenderInfo(BaseModel):
    id: str
    code: str
    name: str
    closing_at: str | None = None


class PostulationCompanyInfo(BaseModel):
    rut: str
    legal_name: str
    trade_name: str | None = None


class PostulationItem(BaseModel):
    position: int
    product_code: str | None = None
    name: str
    description: str | None = None
    quantity: float
    unit_of_measure: str | None = None
    unit_price: int | None = None
    price_source: str = "sin_precio"  # "cotizacion" | "sin_precio"
    quotation_quantity: float | None = None


class PostulationRequiredDocument(BaseModel):
    name: str
    is_mandatory: bool = True
    kind: str = "documento"


class PostulationPackage(BaseModel):
    tender: PostulationTenderInfo
    company: PostulationCompanyInfo
    offer_name: str
    offer_description: str
    offer_description_placeholders: list[str] = Field(default_factory=list)
    items: list[PostulationItem] = Field(default_factory=list)
    technical_document_available: bool = False
    required_documents: list[PostulationRequiredDocument] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    quotation_updated_at: str | None = None
    shipping_clp: int | None = None
