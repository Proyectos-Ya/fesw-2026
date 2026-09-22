"""deep_analysis recuerda contra qué versión de los datos se generó

Saber si un análisis quedó viejo se resolvía comparando su `updated_at` con el
de la licitación y el del proveedor. Eso exige que las tres fechas vengan del
mismo reloj, y no vienen: un volcado restaurado o una corrida con la hora
corrida deja la licitación "en el futuro", y entonces el análisis nace viejo y
no hay forma de arreglarlo —regenerar escribe una fecha que sigue siendo
anterior a la de la licitación—. Antes de que el desfase se mostrara como
aviso, el síntoma era peor: se regeneraba con Gemini en cada visita.

Con estas dos columnas la pregunta se responde por igualdad: se guarda la marca
que tenían la licitación y el proveedor al generar, y basta ver si cambió. No
compara relojes distintos.

Nullable y sin relleno: los análisis anteriores no tienen contra qué comparar,
y la primera regeneración que pida el usuario ya deja la marca puesta.

Revision ID: c8b2e5f41a76
Revises: a4f71c2ed903
Create Date: 2026-09-16 18:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8b2e5f41a76"
down_revision: str | Sequence[str] | None = "a4f71c2ed903"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "deep_analysis",
        sa.Column("tender_updated_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "deep_analysis",
        sa.Column("supplier_updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("deep_analysis", "supplier_updated_at")
    op.drop_column("deep_analysis", "tender_updated_at")
