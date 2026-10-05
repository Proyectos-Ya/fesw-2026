"""source_file_id en hitos (plan 233, decision 5)

Revision ID: d7a1b3c9e524
Revises: c5f8a2d7e413
Create Date: 2026-10-04 12:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7a1b3c9e524"
down_revision: Union[str, None] = "c5f8a2d7e413"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tender_milestone", sa.Column("source_file_id", sa.Uuid(), nullable=True))
    op.create_index("ix_tender_milestone_source_file_id", "tender_milestone", ["source_file_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tender_milestone_source_file_id", table_name="tender_milestone")
    op.drop_column("tender_milestone", "source_file_id")
