from datetime import datetime
from uuid import UUID

from sqlalchemy import Index, func
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
    # Antes era un `UniqueConstraint` plano `(user_id, tender_id)`. Con el
    # soft-delete (HdU 10 CA4), queremos que la misma licitación pueda volver
    # a entrar al tablero después de archivarse, pero sin permitir dos filas
    # activas simultáneas. Un índice único **parcial** sobre
    # `archived_at IS NULL` resuelve ambas cosas en una sola restricción, y es
    # soportado por Postgres (lo que usamos en prod y local).
    __table_args__ = (
        Index(
            "uq_kanban_card_user_tender_active",
            "user_id",
            "tender_id",
            unique=True,
            postgresql_where="archived_at IS NULL",
            sqlite_where="archived_at IS NULL",
        ),
    )

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    column_id: UUID = Field(foreign_key="kanban_column.id", index=True)
    position: int
    created_at: datetime
    updated_at: datetime
    # Archivado (HdU 10, CA4). `board_entered_at` registra cuándo entró la
    # tarjeta al tablero y **no cambia** al moverla entre columnas: el scheduler
    # usa esa fecha para auto-archivar a los 90 días. `archived_at` NULL
    # significa "en el tablero activo"; `archived_reason` distingue las que se
    # pueden restaurar ('manual') de las que no ('auto_3m').
    #
    # `server_default=now()` existe para que las filas pre-existentes también
    # tengan un valor al aplicar la migración (compatibilidad hacia atrás);
    # el default de Python mantiene la misma convención.
    board_entered_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now()},
    )
    archived_at: datetime | None = Field(default=None, nullable=True)
    archived_reason: str | None = Field(default=None, nullable=True)

