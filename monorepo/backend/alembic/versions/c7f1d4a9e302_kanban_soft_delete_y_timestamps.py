"""kanban soft-delete y timestamps

Revision ID: c7f1d4a9e302
Revises: b3c2d1e0f9a8
Create Date: 2026-10-07 00:00:00.000000

HdU 10, CA4: archivado y registro histórico de tarjetas Kanban.
- `board_entered_at`: cuándo entró la tarjeta al tablero. No cambia al mover
  entre columnas; es la referencia para el scheduler de auto-archivado.
  Backfill: `now()` para las filas existentes (equivalente a "entró ahora",
  el reloj de 90 días recomienza, que es más seguro que archivar en masa).
- `archived_at`: NULL mientras la tarjeta está en el tablero activo; con
  valor cuando se archiva (soft-delete).
- `archived_reason`: 'manual' (restaurable) o 'auto_3m' (no restaurable).
- `uq_kanban_card_user_tender`: reemplazado por un índice único **parcial**
  sobre `(user_id, tender_id) WHERE archived_at IS NULL`, para que la misma
  licitación pueda volver a entrar al tablero después de archivarse sin
  colisionar con la fila del historial.

Compatible hacia atrás: columnas nullable o con `server_default`. El cambio
de restricción deja la unicidad por par activo intacta durante la ventana
de pre-deploy, en la que la versión vieja aún no sabe de archived_at pero
tampoco inserta filas archivadas.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c7f1d4a9e302"
down_revision: str | Sequence[str] | None = "b3c2d1e0f9a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Columnas nuevas. `board_entered_at` NOT NULL con server_default para que
    # las filas existentes queden en now() y los INSERT de la versión vieja
    # (sin el campo) sigan funcionando durante el pre-deploy.
    op.add_column(
        "kanban_card",
        sa.Column(
            "board_entered_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "kanban_card",
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "kanban_card",
        sa.Column("archived_reason", sa.String(), nullable=True),
    )

    # Reemplaza la restricción de unicidad plena por un índice único parcial
    # sobre las filas activas (archived_at IS NULL). Así una tarjeta archivada
    # convive con la nueva fila activa de la misma licitación.
    op.drop_constraint("uq_kanban_card_user_tender", "kanban_card", type_="unique")
    op.create_index(
        "uq_kanban_card_user_tender_active",
        "kanban_card",
        ["user_id", "tender_id"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_kanban_card_user_tender_active", table_name="kanban_card")
    op.create_unique_constraint(
        "uq_kanban_card_user_tender",
        "kanban_card",
        ["user_id", "tender_id"],
    )
    op.drop_column("kanban_card", "archived_reason")
    op.drop_column("kanban_card", "archived_at")
    op.drop_column("kanban_card", "board_entered_at")
