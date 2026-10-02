"""Avisos de "Fecha modificada" junto a los de compatibilidad (HU-16).

Compatible hacia atrás: la columna nueva tiene default 'match' (lo que la
versión anterior sigue insertando), `payload` es nullable y a `score` solo se le
quita el NOT NULL. La unicidad pasa a incluir `kind` para que un aviso de fecha
modificada conviva con el de compatibilidad de la misma licitación.
"""

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision = "c16d5f2a8b31"
down_revision = "b16c4e1a7d20"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "notification",
        sa.Column(
            "kind",
            sqlmodel.AutoString(length=20),
            nullable=False,
            server_default="match",
        ),
    )
    op.add_column("notification", sa.Column("payload", sa.JSON(), nullable=True))
    op.alter_column("notification", "score", existing_type=sa.Float(), nullable=True)
    op.drop_constraint("uq_notification_user_tender", "notification", type_="unique")
    op.create_unique_constraint(
        "uq_notification_user_tender_kind",
        "notification",
        ["user_id", "tender_id", "kind"],
    )


def downgrade():
    # Los avisos de fecha modificada no tienen score: no caben en el esquema anterior.
    op.execute("DELETE FROM notification WHERE kind <> 'match'")
    op.drop_constraint("uq_notification_user_tender_kind", "notification", type_="unique")
    op.create_unique_constraint(
        "uq_notification_user_tender", "notification", ["user_id", "tender_id"]
    )
    op.alter_column("notification", "score", existing_type=sa.Float(), nullable=False)
    op.drop_column("notification", "payload")
    op.drop_column("notification", "kind")
