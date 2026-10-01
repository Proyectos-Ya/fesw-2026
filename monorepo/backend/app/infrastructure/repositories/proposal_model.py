"""Tabla de borradores de postulación (HU-20).

Las exigencias, decisiones, advertencias y el contenido van en JSONB: son parte
del borrador, se leen y escriben siempre juntos y ninguna consulta filtra por
ellos. `status` es texto con CHECK, no ENUM, por la misma razón que en el banco
de capacidades: sumar un estado no debe exigir un `ALTER TYPE`.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class ProposalDraftModel(SQLModel, table=True):
    __tablename__ = "proposal_drafts"  # type: ignore

    id: UUID = Field(primary_key=True)
    # Sin índice propio: lo cubre la restricción única, que empieza por esta columna.
    supplier_id: UUID = Field(foreign_key="supplier.id", ondelete="CASCADE")
    tender_id: UUID = Field(foreign_key="tender.id", index=True, ondelete="CASCADE")
    status: str
    requirements: list[dict[str, Any]] = Field(sa_column=Column(JSONB, nullable=False))
    paused_requirement_id: str | None = None
    requires_technical_document: bool = Field(default=False)
    technical_document_reason: str | None = None
    warnings: list[dict[str, Any]] = Field(sa_column=Column(JSONB, nullable=False))
    discrepancy_decisions: list[dict[str, Any]] = Field(
        sa_column=Column(JSONB, nullable=False)
    )
    # `none_as_null`: sin él, None se guarda como el JSON `null` y no como NULL de
    # SQL, y `WHERE content IS NULL` no encuentra los borradores sin redactar.
    content: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB(none_as_null=True))
    )
    last_instructions: str | None = None
    # Huella de los insumos del análisis; nula en los borradores anteriores.
    analysis_fingerprint: str | None = None
    # Si el miembro se va, el borrador sigue siendo de la empresa.
    created_by_user_id: UUID | None = Field(
        default=None, foreign_key="users.id", index=True, ondelete="SET NULL"
    )
    created_at: datetime
    updated_at: datetime

    __table_args__ = (
        UniqueConstraint(
            "supplier_id", "tender_id", name="uq_proposal_drafts_supplier_tender"
        ),
        CheckConstraint(
            "status IN ('FEASIBILITY', 'PAUSED', 'STOPPED', 'READY')",
            name="ck_proposal_drafts_status",
        ),
    )
