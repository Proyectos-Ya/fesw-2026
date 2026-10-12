from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Column, LargeBinary, Text
from sqlmodel import Field, SQLModel


class ExportJobModel(SQLModel, table=True):
    __tablename__ = "export_job"

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    supplier_id: UUID = Field(foreign_key="supplier.id", ondelete="CASCADE")
    tender_id: UUID = Field(foreign_key="tender.id", ondelete="CASCADE")
    format: str = Field(max_length=8)
    sections: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    # El arranque busca los que quedaron en proceso tras un reinicio.
    status: str = Field(max_length=16, index=True)
    file_name: str = Field(max_length=255)
    # En la base y no en disco: el disco del contenedor se pierde en cada
    # despliegue. Son KB, y se vacían al vencer.
    content: bytes | None = Field(default=None, sa_column=Column(LargeBinary, nullable=True))
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime
    finished_at: datetime | None = None
    expires_at: datetime
