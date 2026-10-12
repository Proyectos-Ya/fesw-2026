"""Tablas del banco de capacidades y de las evidencias de experiencia (HU-20).

`kind`, `origin` y los demás vocabularios son texto con CHECK y no ENUM de
Postgres: sumar un valor es cambiar código y la restricción, no un `ALTER TYPE`
en una migración que corre antes de levantar la versión nueva.

Toda llave foránea tiene índice propio o queda cubierta por una restricción única
que empieza por ella: Postgres no los crea solo, y sin ellos borrar una empresa o
un usuario recorre la tabla entera para aplicar el CASCADE o el SET NULL.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    SmallInteger,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class CapabilityQuestionModel(SQLModel, table=True):
    __tablename__ = "capability_question"  # type: ignore

    id: UUID = Field(primary_key=True)
    question: str
    target_field: str
    category: str
    kind: str
    work_type: str | None = None
    options: list[dict] = Field(sa_column=Column(JSONB, nullable=False))
    origin: str
    active: bool = Field(default=True)
    created_at: datetime
    updated_at: datetime

    __table_args__ = (
        # La deduplicación del banco. La categoría va en la clave porque un
        # mismo campo puede preguntarse distinto en rubros distintos.
        UniqueConstraint(
            "category", "target_field", name="uq_capability_question_category_field"
        ),
        CheckConstraint(
            "kind IN ('capacidad', 'certificacion', 'experiencia_proyecto')",
            name="ck_capability_question_kind",
        ),
        CheckConstraint(
            "origin IN ('semilla', 'ia')", name="ck_capability_question_origin"
        ),
    )


class CapabilityAnswerModel(SQLModel, table=True):
    __tablename__ = "capability_answer"  # type: ignore

    id: UUID = Field(primary_key=True)
    # Sin índice propio: lo cubre la restricción única, que empieza por esta columna.
    supplier_id: UUID = Field(foreign_key="supplier.id", ondelete="CASCADE")
    question_id: UUID = Field(
        foreign_key="capability_question.id", index=True, ondelete="RESTRICT"
    )
    answer: str | None = None
    answered: bool = Field(default=False)
    omitted: bool = Field(default=False)
    tender_id: UUID | None = Field(
        default=None, foreign_key="tender.id", index=True, ondelete="SET NULL"
    )
    # Si el miembro se va, la respuesta sigue siendo de la empresa.
    answered_by_user_id: UUID | None = Field(
        default=None, foreign_key="users.id", index=True, ondelete="SET NULL"
    )
    valid_until: datetime | None = None
    generated_at: datetime
    answered_at: datetime | None = None

    __table_args__ = (
        UniqueConstraint(
            "supplier_id", "question_id", name="uq_capability_answer_supplier_question"
        ),
        CheckConstraint(
            "NOT (answered AND omitted)", name="ck_capability_answer_estado"
        ),
    )


class CapabilityEvidenceModel(SQLModel, table=True):
    __tablename__ = "capability_evidence"  # type: ignore

    id: UUID = Field(primary_key=True)
    supplier_id: UUID = Field(foreign_key="supplier.id", index=True, ondelete="CASCADE")
    # Nulo en las evidencias importadas y en las que perdieron su respuesta: el
    # proyecto sigue siendo experiencia de la empresa, clasificado por `work_type`.
    answer_id: UUID | None = Field(
        default=None,
        foreign_key="capability_answer.id",
        index=True,
        ondelete="SET NULL",
    )
    work_type: str
    origin: str = Field(default="manual")
    title: str
    buyer: str | None = None
    year: int = Field(sa_column=Column(SmallInteger, nullable=False))
    # Pesos chilenos enteros; un contrato público supera con holgura los 2^31.
    amount_clp: int | None = Field(default=None, sa_column=Column(BigInteger))
    description: str | None = None
    created_by_user_id: UUID | None = Field(
        default=None, foreign_key="users.id", index=True, ondelete="SET NULL"
    )
    created_at: datetime

    __table_args__ = (
        CheckConstraint(
            "origin IN ('manual', 'mercado_publico')",
            name="ck_capability_evidence_origin",
        ),
        CheckConstraint(
            "amount_clp IS NULL OR amount_clp >= 0",
            name="ck_capability_evidence_amount",
        ),
        CheckConstraint("year >= 1900", name="ck_capability_evidence_year"),
    )
