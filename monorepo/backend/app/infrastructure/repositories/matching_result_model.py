from datetime import datetime
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class MatchingResultModel(SQLModel, table=True):
    """Modelo de base de datos para la tabla 'matching_result' en PostgreSQL."""

    __tablename__ = "matching_result"  # type: ignore

    __table_args__ = (
        UniqueConstraint(
            "supplier_id", "tender_id", name="uq_matching_result_supplier_tender"
        ),
    )

    id: UUID = Field(primary_key=True)
    supplier_id: UUID = Field(
        foreign_key="supplier.id", index=True
    )  # Referencia al proveedor
    tender_id: UUID = Field(foreign_key="tender.id")  # Referencia a la licitación
    similarity_score: float  # Score vectorial inicial
    reranker_score: float | None = Field(
        default=None
    )  # Score del re-ranker ONNX (opcional)
    final_score: float  # Score ponderado final
    model_version: str  # Versión del modelo de embeddings
    calculated_at: datetime  # Fecha en que se calculó la recomendación
