from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime, utc_now_naive

__all__ = ["utc_now_naive"]


class Region(BaseModel):
    """Represents a political region in Chile (1 to 16)."""

    id: int
    name: str


class TenderStatus(BaseModel):
    """Represents the possible states of a tender."""

    id: int
    code: str  # e.g., 'publicada', 'cerrada', 'desierta', 'cancelada'
    name: str  # Glosa/Description of the status


class BuyerInstitution(BaseModel):
    """Represents the public organization that publishes the tender."""

    rut: str
    name: str
    region_id: int
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)


class TenderItem(BaseModel):
    """Represents a specific product or service requested in a tender."""

    id: UUID = Field(default_factory=uuid4)
    tender_id: UUID
    product_code: str
    name: str
    description: str | None = None
    quantity: float
    unit_of_measure: str


class TenderAIAnalysis(BaseModel):
    """Represents the AI matching results generated for a tender against a supplier."""

    id: UUID = Field(default_factory=uuid4)
    tender_id: UUID
    supplier_id: UUID
    match_score: float  # Compatibility percentage (0.0 to 100.0)
    match_justification: dict  # AI detailed breakdown
    generated_at: UtcDateTime = Field(default_factory=utc_now_naive)


class Tender(BaseModel):
    """Represents a public purchasing process (Compra Ágil)."""

    id: UUID = Field(default_factory=uuid4)
    code: str  # Unique external code (e.g. 1057539-228-COT26)
    name: str
    description: str | None = None
    status_id: int
    status_code: str | None = (
        None  # Código del estado de la licitación (ej: 'publicada', 'cerrada')
    )
    published_at: UtcDateTime
    closing_at: UtcDateTime
    last_change_at: UtcDateTime
    buyer_rut: str
    buyer_name: str | None = None  # Nombre de la institución compradora
    buyer_unit: str
    region: str | None = None  # Region name derived from the buyer institution
    available_amount_clp: float | None = None  # Budget normalized to CLP
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)
    items: list[TenderItem] = Field(default_factory=list)
