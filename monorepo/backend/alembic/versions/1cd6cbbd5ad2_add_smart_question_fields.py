"""add_smart_question_fields

Revision ID: 1cd6cbbd5ad2
Revises: e7123e26c0be
Create Date: 2026-10-27 21:09:56.493550

Campos para el motor dinámico de Smart Questions:
- `profile_question.tender_id`: UUID nullable con índice. Vincula preguntas a licitaciones.
- `profile_question.target_keyword`: String nullable con la keyword asociada.
- `supplier.negative_keywords`: JSONB nullable con lista de descartes y fecha.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '1cd6cbbd5ad2'
down_revision: str | Sequence[str] | None = 'e7123e26c0be'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "profile_question",
        sa.Column("tender_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "profile_question",
        sa.Column("target_keyword", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index(
        op.f("ix_profile_question_tender_id"),
        "profile_question",
        ["tender_id"],
        unique=False,
    )
    op.add_column(
        "supplier",
        sa.Column(
            "negative_keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("supplier", "negative_keywords")
    op.drop_index(op.f("ix_profile_question_tender_id"), table_name="profile_question")
    op.drop_column("profile_question", "target_keyword")
    op.drop_column("profile_question", "tender_id")
