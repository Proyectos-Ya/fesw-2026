"""enlaces compartidos de licitaciones (HdU 19)

Revision ID: e19a4c2b7d01
Revises: f1e2d3c4b5a6
Create Date: 2026-09-28 12:00:00.000000

Solo agrega una tabla, así que la versión anterior de la API convive sin
problemas con el esquema nuevo durante el despliegue.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e19a4c2b7d01"
down_revision: str | Sequence[str] | None = "f1e2d3c4b5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tender_share_link",
        sa.Column("id", sa.Uuid(), nullable=False),
        # SHA-256 en hexadecimal; el token en claro nunca llega a la base.
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tender_id"], ["tender.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["supplier.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tender_share_link_token_hash"),
        "tender_share_link",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_tender_share_link_tender_supplier",
        "tender_share_link",
        ["tender_id", "supplier_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tender_share_link_tender_supplier", table_name="tender_share_link")
    op.drop_index(op.f("ix_tender_share_link_token_hash"), table_name="tender_share_link")
    op.drop_table("tender_share_link")
