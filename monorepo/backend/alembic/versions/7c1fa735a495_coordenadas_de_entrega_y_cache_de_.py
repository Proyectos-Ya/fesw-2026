"""coordenadas de entrega y cache de geocodificacion

Revision ID: 7c1fa735a495
Revises: a3f9c8e1d402
Create Date: 2026-10-28 15:59:25.771486

Plan #314 (HU-22). Compatible con la versión anterior durante el despliegue:
cuatro columnas nullable y sin default en `tender` (no reescriben la tabla) y
una tabla nueva que la versión vieja no lee ni escribe.

El índice parcial se crea sin `CONCURRENTLY`, como los demás del repositorio:
bloquea las escrituras de `tender` lo que tarda en recorrerla, que son segundos.

RLS: en producción lo activa el event trigger `ensure_rls` del panel de
Supabase al crear cada tabla, no esta migración.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c1fa735a495"
down_revision: str | Sequence[str] | None = "a3f9c8e1d402"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PENDIENTES = "delivery_address IS NOT NULL AND delivery_geocoded_at IS NULL"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "geocoding_cache",
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("lat", sa.Double(), nullable=True),
        sa.Column("lng", sa.Double(), nullable=True),
        sa.Column("geocoded_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("query"),
    )
    op.add_column("tender", sa.Column("delivery_lat", sa.Double(), nullable=True))
    op.add_column("tender", sa.Column("delivery_lng", sa.Double(), nullable=True))
    op.add_column(
        "tender", sa.Column("delivery_geo_precision", sa.Text(), nullable=True)
    )
    op.add_column(
        "tender", sa.Column("delivery_geocoded_at", sa.DateTime(), nullable=True)
    )
    op.create_index(
        "ix_tender_geocodificacion_pendiente",
        "tender",
        ["closing_at"],
        unique=False,
        postgresql_where=sa.text(_PENDIENTES),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_tender_geocodificacion_pendiente",
        table_name="tender",
        postgresql_where=sa.text(_PENDIENTES),
    )
    op.drop_column("tender", "delivery_geocoded_at")
    op.drop_column("tender", "delivery_geo_precision")
    op.drop_column("tender", "delivery_lng")
    op.drop_column("tender", "delivery_lat")
    op.drop_table("geocoding_cache")
