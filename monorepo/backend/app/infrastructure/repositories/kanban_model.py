from datetime import datetime
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class KanbanColumnModel(SQLModel, table=True):
    __tablename__ = "kanban_column"  # type: ignore

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    name: str
    position: int
    # El `server_default` tiene que estar declarado acá y no solo en la
    # migración: si falta, `alembic check` falla en CI y `--autogenerate`
    # propone quitarlo. Además, durante el despliegue la versión anterior
    # inserta columnas sin `color`, y la columna es NOT NULL.
    color: str = Field(default="#A99A7C", sa_column_kwargs={"server_default": "#A99A7C"})
    created_at: datetime


class KanbanCardModel(SQLModel, table=True):
    __tablename__ = "kanban_card"  # type: ignore
    __table_args__ = (
        UniqueConstraint("user_id", "tender_id", name="uq_kanban_card_user_tender"),
    )

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    column_id: UUID = Field(foreign_key="kanban_column.id", index=True)
    position: int
    created_at: datetime
    updated_at: datetime

