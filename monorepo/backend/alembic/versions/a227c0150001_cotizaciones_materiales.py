"""Cotizaciones por empresa y licitación (HU-15, #227)."""

import sqlalchemy as sa

from alembic import op

revision = "a227c0150001"
down_revision = "c8b2e5f41a76"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quotation",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "supplier_id", sa.Uuid(), sa.ForeignKey("supplier.id"), nullable=False
        ),
        sa.Column("tender_id", sa.Uuid(), sa.ForeignKey("tender.id"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "supplier_id", "tender_id", name="uq_quotation_company_tender"
        ),
    )
    op.create_index("ix_quotation_supplier_id", "quotation", ["supplier_id"])
    op.create_index("ix_quotation_tender_id", "quotation", ["tender_id"])
    op.create_table(
        "quotation_material",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "quotation_id",
            sa.Uuid(),
            sa.ForeignKey("quotation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_quotation_material_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_quotation_material_price"),
    )
    op.create_index(
        "ix_quotation_material_quotation_id", "quotation_material", ["quotation_id"]
    )


def downgrade():
    op.drop_table("quotation_material")
    op.drop_table("quotation")
