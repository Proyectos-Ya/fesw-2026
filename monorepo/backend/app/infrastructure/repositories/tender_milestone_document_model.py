from datetime import datetime
from uuid import UUID

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class TenderMilestoneDocumentModel(SQLModel, table=True):
    """Bases ya leídas por la extracción de hitos (HU-16, criterio 1).

    Al borrar el documento en el asistente, su registro se va en cascada y una
    nueva subida se vuelve a leer.
    """

    __tablename__ = "tender_milestone_document"  # type: ignore
    __table_args__ = (
        # La ficha pregunta por los procesados del usuario en cada consulta.
        Index("ix_tender_milestone_document_user_tender", "user_id", "tender_id"),
    )

    document_id: UUID = Field(
        primary_key=True, foreign_key="tender_chat_documents.id", ondelete="CASCADE"
    )
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    # Índice propio para el borrado en cascada desde `tender`; `user_id` ya lo
    # cubre el índice compuesto.
    tender_id: UUID = Field(foreign_key="tender.id", ondelete="CASCADE", index=True)
    extracted_at: datetime
    milestones_found: int
