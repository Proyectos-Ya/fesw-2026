from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.entities.tender import Tender
from app.shared.datetime_utils import UtcDateTime, utc_now_naive


class MatchingResult(BaseModel):
    """Representa el resultado del cruce (match) entre un proveedor y una licitación."""

    id: UUID = Field(default_factory=uuid4)
    supplier_id: UUID  # ID del proveedor recomendado
    tender_id: UUID  # ID de la licitación recomendada
    similarity_score: float  # Score de similitud vectorial (Qdrant)
    reranker_score: float | None = None  # Score refinado por el Reranker (ONNX)
    final_score: float  # Score definitivo después de aplicar ponderaciones manuales
    model_version: str  # Versión del modelo de embeddings utilizado (para trazabilidad)
    calculated_at: UtcDateTime = Field(
        default_factory=utc_now_naive
    )  # Fecha del cálculo
    tender: Tender | None = None  # Licitación hidratada asociada
