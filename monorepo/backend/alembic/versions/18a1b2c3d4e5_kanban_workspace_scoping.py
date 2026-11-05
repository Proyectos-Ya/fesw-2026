"""kanban workspace scoping

Revision ID: 18a1b2c3d4e5
Revises: 9fc5e8be46b9
Create Date: 2026-10-27 10:00:00.000000

HU-18: el tablero kanban deja de ser personal (`user_id`) y pasa a ser de
*workspace* (`supplier_id`): todos los miembros del espacio comparten el mismo
tablero. `user_id` se conserva en ambas tablas como autoría ("quién lo creó"),
no propiedad.

Pasos de la migración (en el mismo archivo para que el rollback deje schema
consistente):

1. ADD COLUMN `supplier_id UUID NULL` en `kanban_column` y `kanban_card`.
2. Data-migration: para cada fila, resolver `supplier_id` desde la membresía
   activa más reciente del `user_id` correspondiente (`supplier_members`
   plural, con `updated_at`).
3. DELETE filas huérfanas (sin membresía activa). Son filas que vivían con un
   usuario que nunca se vinculó a un workspace: ya no pueden caber en el
   modelo de dominio nuevo. El downgrade NO las restaura (documentado).
4. Deduplicación en `kanban_card`: la nueva unicidad `(supplier_id, tender_id)
   WHERE archived_at IS NULL` puede colisionar si dos usuarios del mismo
   workspace tenían la misma licitación activa. Conservar el `updated_at` más
   reciente y archivar el resto con `archived_reason = 'migration_dedup'`.
5. SET NOT NULL en ambas tablas + FK a `supplier(id) ON DELETE CASCADE`.
6. Reemplazar el índice único parcial de kanban_card:
   DROP `uq_kanban_card_user_tender_active` ((user_id, tender_id) WHERE active)
   CREATE `uq_kanban_card_supplier_tender_active` ((supplier_id, tender_id) WHERE active)

Compatibilidad hacia atrás: la columna entra NULLABLE, se puebla, y recién
después se promueve a NOT NULL en el mismo archivo. Durante el pre-deploy la
versión vieja aún puede leer el tablero (sigue viendo `user_id`), y al
terminar la migración queda con `supplier_id` poblado. El cambio de semántica
(que la versión vieja ya no es correcta en multi-usuario) se asume aceptable
porque pre-deploy corre contra la ventana donde la versión vieja todavía
está arriba brevemente.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "18a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "9fc5e8be46b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Añadir supplier_id NULLABLE
    op.add_column("kanban_column", sa.Column("supplier_id", sa.Uuid(), nullable=True))
    op.add_column("kanban_card", sa.Column("supplier_id", sa.Uuid(), nullable=True))

    # 2. Data-migration: membresía activa más reciente por user_id
    op.execute(
        """
        UPDATE kanban_column kc
        SET supplier_id = sub.supplier_id
        FROM (
            SELECT DISTINCT ON (user_id) user_id, supplier_id
            FROM supplier_members
            WHERE status = 'active'
            ORDER BY user_id, updated_at DESC
        ) sub
        WHERE kc.user_id = sub.user_id;
        """
    )
    op.execute(
        """
        UPDATE kanban_card kc
        SET supplier_id = sub.supplier_id
        FROM (
            SELECT DISTINCT ON (user_id) user_id, supplier_id
            FROM supplier_members
            WHERE status = 'active'
            ORDER BY user_id, updated_at DESC
        ) sub
        WHERE kc.user_id = sub.user_id;
        """
    )

    # 3. Borrar huérfanas (usuarios sin workspace activo)
    # Primero las cards, para que no queden FKs apuntando a columnas eliminadas.
    op.execute("DELETE FROM kanban_card WHERE supplier_id IS NULL;")
    op.execute("DELETE FROM kanban_column WHERE supplier_id IS NULL;")

    # 4. Deduplicar kanban_card por (supplier_id, tender_id) entre filas activas:
    # conservar la más reciente, archivar el resto con razón 'migration_dedup'.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY supplier_id, tender_id
                       ORDER BY updated_at DESC, id DESC
                   ) AS rn
            FROM kanban_card
            WHERE archived_at IS NULL
        )
        UPDATE kanban_card
        SET archived_at = now(), archived_reason = 'migration_dedup'
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
        """
    )

    # 5. SET NOT NULL + FKs
    op.alter_column("kanban_column", "supplier_id", nullable=False)
    op.alter_column("kanban_card", "supplier_id", nullable=False)
    op.create_foreign_key(
        "fk_kanban_column_supplier",
        "kanban_column",
        "supplier",
        ["supplier_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_kanban_card_supplier",
        "kanban_card",
        "supplier",
        ["supplier_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_kanban_column_supplier_id", "kanban_column", ["supplier_id"], unique=False
    )
    op.create_index(
        "ix_kanban_card_supplier_id", "kanban_card", ["supplier_id"], unique=False
    )

    # 6. Reemplazar índice único parcial de kanban_card
    op.drop_index("uq_kanban_card_user_tender_active", table_name="kanban_card")
    op.create_index(
        "uq_kanban_card_supplier_tender_active",
        "kanban_card",
        ["supplier_id", "tender_id"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )


def downgrade() -> None:
    # El downgrade no restaura las filas huérfanas eliminadas ni deshace la
    # deduplicación (los archived_reason = 'migration_dedup' quedan como
    # histórico, es la señal explícita de que el merge ocurrió).
    op.drop_index("uq_kanban_card_supplier_tender_active", table_name="kanban_card")
    op.create_index(
        "uq_kanban_card_user_tender_active",
        "kanban_card",
        ["user_id", "tender_id"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    op.drop_index("ix_kanban_card_supplier_id", table_name="kanban_card")
    op.drop_index("ix_kanban_column_supplier_id", table_name="kanban_column")
    op.drop_constraint("fk_kanban_card_supplier", "kanban_card", type_="foreignkey")
    op.drop_constraint("fk_kanban_column_supplier", "kanban_column", type_="foreignkey")
    op.drop_column("kanban_card", "supplier_id")
    op.drop_column("kanban_column", "supplier_id")
