from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.entities.tender import Tender
from app.shared.datetime_utils import UtcDateTime, utc_now_naive

# De dónde salió la fila. `ranking` es el top-N que el pipeline recalcula y
# reescribe entero; `on_demand` es un cálculo que pidió el usuario sobre una
# licitación que no está en ese top, y que por eso debe sobrevivir a los
# recálculos en vez de borrarse con ellos.
MatchingSource = Literal["ranking", "on_demand"]


class MatchingResult(BaseModel):
    """Representa el resultado del cruce (match) entre un proveedor y una licitación."""

    id: UUID = Field(default_factory=uuid4)
    supplier_id: UUID  # ID del proveedor recomendado
    tender_id: UUID  # ID de la licitación recomendada
    # Nulo en los cálculos a pedido: ahí no se pasa por Qdrant, y un 0.0 diría
    # "sin ningún parecido", que es una afirmación distinta a "no se midió".
    similarity_score: float | None = None  # Score de similitud vectorial (Qdrant)
    reranker_score: float | None = None  # Score refinado por el Reranker (ONNX)
    # Nulo cuando todavía nadie lo calculó: una licitación guardada que no
    # está en el top-N ni se pidió a mano no tiene puntaje, y mostrarla con 0.0
    # sería afirmar que no calza.
    final_score: float | None = None  # Score definitivo tras las ponderaciones
    model_version: str  # Versión del modelo de embeddings utilizado (para trazabilidad)
    source: MatchingSource = "ranking"  # Quién originó el cálculo
    calculated_at: UtcDateTime = Field(
        default_factory=utc_now_naive
    )  # Fecha del cálculo
    tender: Tender | None = None  # Licitación hidratada asociada
