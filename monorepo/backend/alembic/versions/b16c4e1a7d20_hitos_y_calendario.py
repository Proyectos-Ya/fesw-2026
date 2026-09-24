"""Hitos de licitación y sincronización con calendarios externos (HU-16)."""

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision = "b16c4e1a7d20"
down_revision = "a227c0150001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tender_milestone",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tender_id", sa.Uuid(), sa.ForeignKey("tender.id"), nullable=False),
        sa.Column("kind", sqlmodel.AutoString(length=40), nullable=False),
        sa.Column("title", sqlmodel.AutoString(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sqlmodel.AutoString(length=40), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=True),
        sa.Column("source_excerpt", sqlmodel.AutoString(length=1000), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("has_time", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tender_milestone_tender_id", "tender_milestone", ["tender_id"])
    op.create_index(
        "ix_tender_milestone_user_tender", "tender_milestone", ["user_id", "tender_id"]
    )

    op.create_table(
        "calendar_connection",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("account_email", sqlmodel.AutoString(length=320), nullable=True),
        sa.Column("status", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "user_id", "provider", name="uq_calendar_connection_user_provider"
        ),
    )
    op.create_index(
        "ix_calendar_connection_user_id", "calendar_connection", ["user_id"]
    )

    op.create_table(
        "calendar_oauth_state",
        sa.Column("state_hash", sqlmodel.AutoString(length=64), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("tender_id", sa.Uuid(), sa.ForeignKey("tender.id"), nullable=False),
        sa.Column("milestone_ids", sa.JSON(), nullable=False),
        sa.Column("default_time", sa.Time(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_calendar_oauth_state_user_id", "calendar_oauth_state", ["user_id"]
    )

    op.create_table(
        "calendar_event_link",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "milestone_id",
            sa.Uuid(),
            sa.ForeignKey("tender_milestone.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("external_event_id", sa.Text(), nullable=False),
        sa.Column("synced_due_at", sa.DateTime(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "milestone_id",
            "provider",
            name="uq_calendar_event_link_milestone_provider",
        ),
    )
    op.create_index(
        "ix_calendar_event_link_user_id", "calendar_event_link", ["user_id"]
    )


def downgrade():
    op.drop_table("calendar_event_link")
    op.drop_table("calendar_oauth_state")
    op.drop_table("calendar_connection")
    op.drop_table("tender_milestone")
