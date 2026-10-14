from datetime import datetime
from uuid import UUID

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class TenderMilestoneAttachmentModel(SQLModel, table=True):
    """Anexos ya leídos por la extracción de hitos de cada usuario (plan 233).

    Los hitos son por usuario y los anexos por empresa: el mismo archivo se lee
    una vez para cada miembro que abre la ficha. Al borrar el archivo, su registro
    se va en cascada.
    """

    __tablename__ = "tender_milestone_attachment"  # type: ignore
    __table_args__ = (
        # La ficha pregunta por los leídos del usuario en cada consulta.
        Index("ix_tender_milestone_attachment_user_tender", "user_id", "tender_id"),
    )

    user_id: UUID = Field(primary_key=True, foreign_key="users.id", ondelete="CASCADE")
    # Índice propio para el borrado en cascada desde `attachment_file`: la PK
    # empieza por `user_id` y no lo cubre.
    attachment_file_id: UUID = Field(
        primary_key=True, foreign_key="attachment_file.id", ondelete="CASCADE", index=True
    )
    tender_id: UUID = Field(foreign_key="tender.id", ondelete="CASCADE", index=True)
    extracted_at: datetime
    milestones_found: int
