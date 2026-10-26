from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


class TenderAttachmentModel(SQLModel, table=True):
    """Lista oficial de anexos que Mercado Público publica por licitación (plan 233, decisión 1).

    No se borra lo que MP retira: se marca `removed_at`, porque la decisión 2
    colgará archivos subidos de estas filas y un anexo puede reaparecer.
    """

    __tablename__ = "tender_attachment"  # type: ignore
    # El único (tender_id, mp_document_id) es la clave del upsert, y su índice
    # implícito ya cubre las búsquedas por licitación: no hace falta otro.
    __table_args__ = (
        UniqueConstraint(
            "tender_id", "mp_document_id", name="uq_tender_attachment_tender_document"
        ),
    )

    id: UUID = Field(primary_key=True)
    tender_id: UUID = Field(foreign_key="tender.id", ondelete="CASCADE")
    mp_document_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    name: str
    name_normalized: str
    ext: str = Field(max_length=16)
    first_seen_at: datetime
    last_seen_at: datetime
    removed_at: datetime | None = Field(default=None)
