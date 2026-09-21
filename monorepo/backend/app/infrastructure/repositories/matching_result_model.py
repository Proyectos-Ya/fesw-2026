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
    similarity_score: float | None = Field(
        default=None
    )  # Score vectorial inicial (nulo si no pasó por Qdrant)
    reranker_score: float | None = Field(
        default=None
    )  # Score del re-ranker ONNX (opcional)
    final_score: float  # Score ponderado final
    model_version: str  # Versión del modelo de embeddings
    # Nullable en la base: la versión anterior al cálculo a pedido inserta sin
    # esta columna, y esas filas son del ranking. Por eso NULL se lee como
    # "ranking" en vez de tratarse como un valor desconocido.
    # El `server_default` tiene que estar declarado acá y no solo en la
    # migración: si falta, `alembic revision --autogenerate` propone quitarlo.
    source: str | None = Field(
        default="ranking", sa_column_kwargs={"server_default": "ranking"}
    )
    calculated_at: datetime  # Fecha en que se calculó la recomendación
