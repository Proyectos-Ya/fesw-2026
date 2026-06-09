from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

from app.domain.entities.tender import Tender


def utc_now_naive() -> datetime:
    """Retorna la fecha y hora UTC naive actual."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MatchingResult(BaseModel):
    """Representa el resultado del cruce (match) entre un proveedor y una licitación."""

    id: UUID = Field(default_factory=uuid4)
    supplier_id: UUID  # ID del proveedor recomendado
    tender_id: UUID  # ID de la licitación recomendada
    similarity_score: float  # Score de similitud vectorial (Qdrant)
    reranker_score: Optional[float] = None  # Score refinado por el Reranker (ONNX)
    final_score: float  # Score definitivo después de aplicar ponderaciones manuales
    model_version: str  # Versión del modelo de embeddings utilizado (para trazabilidad)
    calculated_at: datetime = Field(default_factory=utc_now_naive)  # Fecha del cálculo
    tender: Optional[Tender] = None  # Licitación hidratada asociada

