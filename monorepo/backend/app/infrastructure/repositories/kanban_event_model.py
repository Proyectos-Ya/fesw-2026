"""SQLModel para la tabla `kanban_event` (HU-18).

Append-only: la UI solo lee, nunca borra. El `tender_title` se desnormaliza
al momento de escribir, para que el panel de historial no necesite joinear
con `tender` ni dependa de que la licitación siga existiendo.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Column, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class KanbanEventModel(SQLModel, table=True):
    __tablename__ = "kanban_event"  # type: ignore

    __table_args__ = (
        # El panel de historial filtra por workspace y pagina DESC por fecha.
        Index(
            "ix_kanban_event_supplier_created",
            "supplier_id",
            text("created_at DESC"),
        ),
    )

    id: UUID = Field(
        primary_key=True, sa_column_kwargs={"server_default": text("gen_random_uuid()")}
    )
    supplier_id: UUID = Field(foreign_key="supplier.id", index=True)
    # ON DELETE RESTRICT: borrar un usuario no debe borrar el historial;
    # la constraint lo impide por diseño (ver migración 18a2c3d4e5f6).
    user_id: UUID = Field(foreign_key="users.id")
    event_type: str = Field(max_length=50)
    entity_type: str | None = Field(default=None, max_length=20)
    entity_id: UUID | None = None
    tender_id: UUID | None = None
    tender_title: str | None = None
    details: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    )
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("now()")},
    )
