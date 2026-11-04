from datetime import datetime
from uuid import UUID

from sqlalchemy import Index, func
from sqlmodel import Field, SQLModel


class KanbanColumnModel(SQLModel, table=True):
    __tablename__ = "kanban_column"  # type: ignore

    id: UUID = Field(primary_key=True)
    # HU-18: el tablero pertenece al workspace; `user_id` queda como autoría.
    supplier_id: UUID = Field(foreign_key="supplier.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    name: str
    position: int
    # El `server_default` tiene que estar declarado acá y no solo en la
    # migración: si falta, `alembic check` falla en CI y `--autogenerate`
    # propone quitarlo. Además, durante el despliegue la versión anterior
    # inserta columnas sin `color`, y la columna es NOT NULL.
    color: str = Field(
        default="#A99A7C", sa_column_kwargs={"server_default": "#A99A7C"}
    )
    created_at: datetime


class KanbanCardModel(SQLModel, table=True):
    __tablename__ = "kanban_card"  # type: ignore
    # HU-18: la restricción de unicidad activa pasa de `(user_id, tender_id)`
    # a `(supplier_id, tender_id)`. Una licitación no puede estar dos veces
    # activa en el mismo tablero de workspace, independientemente de qué
    # miembro la haya agregado.
    __table_args__ = (
        Index(
            "uq_kanban_card_supplier_tender_active",
            "supplier_id",
            "tender_id",
            unique=True,
            postgresql_where="archived_at IS NULL",
            sqlite_where="archived_at IS NULL",
        ),
    )

    id: UUID = Field(primary_key=True)
    supplier_id: UUID = Field(foreign_key="supplier.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    column_id: UUID = Field(foreign_key="kanban_column.id", index=True)
    position: int
    created_at: datetime
    updated_at: datetime
    # Archivado (HdU 10, CA4). `board_entered_at` registra cuándo entró la
    # tarjeta al tablero y **no cambia** al moverla entre columnas: el
    # scheduler usa esa fecha para auto-archivar a los 90 días.
    board_entered_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now()},
    )
    archived_at: datetime | None = Field(default=None, nullable=True)
    archived_reason: str | None = Field(default=None, nullable=True)
