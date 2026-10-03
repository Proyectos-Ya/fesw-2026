"""Lista oficial de anexos de cada licitación (plan 233, decisión 1).

Compatible hacia atrás: crea una tabla nueva y agrega una columna nullable a
`tender`. La versión anterior no conoce ninguna de las dos y sigue funcionando.

Revision ID: cad6ec974305
Revises: ea51f4f30556
Create Date: 2026-10-03 06:28:14.306933
"""
from collections.abc import Sequence

import sqlalchemy as sa

# SQLModel mapea `str` a `sqlmodel.sql.sqltypes.AutoString`, así que las
# migraciones autogeneradas lo referencian. Sin este import fallan con
# NameError al aplicarse.
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cad6ec974305"
down_revision: str | Sequence[str] | None = "ea51f4f30556"  # = salida de `alembic heads`
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tender_attachment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("mp_document_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sqlmodel.AutoString(), nullable=False),
        sa.Column("name_normalized", sqlmodel.AutoString(), nullable=False),
        sa.Column("ext", sqlmodel.AutoString(length=16), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        # CASCADE: la lista es un dato derivado de la licitación.
        sa.ForeignKeyConstraint(["tender_id"], ["tender.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tender_id", "mp_document_id", name="uq_tender_attachment_tender_document"
        ),
    )
    # Nullable y sin default: en Postgres es un cambio de catálogo, instantáneo
    # aunque `tender` tenga cientos de miles de filas.
    op.add_column(
        "tender", sa.Column("attachments_synced_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("tender", "attachments_synced_at")
    op.drop_table("tender_attachment")
