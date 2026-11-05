"""saved tender workspace scoping

Revision ID: 18a4e5f6a7b8
Revises: 18a3d4e5f6a7
Create Date: 2026-10-27 10:15:00.000000

HU-18: las licitaciones guardadas pasan de `user_id` (personal) a
`supplier_id` (workspace). Todos los miembros del espacio ven la misma lista
y la operación "guardar" se vuelve idempotente a nivel de workspace.
`user_id` se conserva como auditoría (quién la guardó primero).

Dedup: si dos usuarios del mismo workspace tenían la misma licitación
guardada, conservar la más antigua (`saved_at ASC`) y eliminar las demás —
el `saved_at` del "primero que marcó interés" refleja mejor la historia que
quedarse con el último.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "18a4e5f6a7b8"
down_revision: str | Sequence[str] | None = "18a3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Añadir supplier_id NULLABLE
    op.add_column("saved_tender", sa.Column("supplier_id", sa.Uuid(), nullable=True))

    # 2. Data-migration: resolver supplier_id desde la membresía activa más
    # reciente del user_id (mismo patrón que kanban).
    op.execute(
        """
        UPDATE saved_tender st
        SET supplier_id = sub.supplier_id
        FROM (
            SELECT DISTINCT ON (user_id) user_id, supplier_id
            FROM supplier_members
            WHERE status = 'active'
            ORDER BY user_id, updated_at DESC
        ) sub
        WHERE st.user_id = sub.user_id;
        """
    )

    # 3. Borrar huérfanas
    op.execute("DELETE FROM saved_tender WHERE supplier_id IS NULL;")

    # 4. Deduplicar (supplier_id, tender_id): conservar la más antigua.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY supplier_id, tender_id
                       ORDER BY saved_at ASC, id ASC
                   ) AS rn
            FROM saved_tender
        )
        DELETE FROM saved_tender
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
        """
    )

    # 5. SET NOT NULL + FK
    op.alter_column("saved_tender", "supplier_id", nullable=False)
    op.create_foreign_key(
        "fk_saved_tender_supplier",
        "saved_tender",
        "supplier",
        ["supplier_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 6. Reemplazar unicidad: (user_id, tender_id) → (supplier_id, tender_id)
    op.drop_constraint("uq_saved_tender_user_tender", "saved_tender", type_="unique")
    op.create_unique_constraint(
        "uq_saved_tender_supplier_tender",
        "saved_tender",
        ["supplier_id", "tender_id"],
    )
    op.create_index(
        "ix_saved_tender_supplier_id", "saved_tender", ["supplier_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_saved_tender_supplier_id", table_name="saved_tender")
    op.drop_constraint(
        "uq_saved_tender_supplier_tender", "saved_tender", type_="unique"
    )
    op.create_unique_constraint(
        "uq_saved_tender_user_tender",
        "saved_tender",
        ["user_id", "tender_id"],
    )
    op.drop_constraint("fk_saved_tender_supplier", "saved_tender", type_="foreignkey")
    op.drop_column("saved_tender", "supplier_id")
