"""matching_result admite cálculos a pedido

El ranking solo puntúa su top-N y reescribe esas filas enteras en cada
recálculo. Desde ahora el usuario también puede pedir el puntaje de una
licitación que encontró buscando, y ese resultado tiene que sobrevivir a los
recálculos: `source` distingue las dos poblaciones para que el pipeline borre
las suyas sin llevarse las del usuario.

`similarity_score` pasa a nullable porque un cálculo a pedido no pasa por
Qdrant: no hay similitud vectorial que guardar, y un 0.0 se leería como "sin
ningún parecido", que es una afirmación distinta a "no se midió".

Compatible hacia atrás, como exige el `preDeployCommand` de `railway.toml`: las
dos columnas admiten NULL y `source` trae `server_default`, así que la versión
anterior del código —que inserta sin nombrarla— sigue escribiendo filas válidas,
y quedan marcadas como del ranking, que es lo que son.

Revision ID: a4f71c2ed903
Revises: d7f2a9c41b58
Create Date: 2026-09-16 10:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4f71c2ed903"
down_revision: str | Sequence[str] | None = "d7f2a9c41b58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "matching_result",
        sa.Column(
            "source",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
            server_default="ranking",
        ),
    )
    # Las filas que ya existen son todas del ranking: es el único que las
    # escribía hasta ahora.
    op.execute("UPDATE matching_result SET source = 'ranking' WHERE source IS NULL")

    op.alter_column(
        "matching_result",
        "similarity_score",
        existing_type=sa.Float(),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Volver a NOT NULL exige un valor para las filas a pedido. Se usa 0.0 por
    # ser el único neutro disponible; el dato de similitud no existe y no se
    # puede reconstruir.
    op.execute("UPDATE matching_result SET similarity_score = 0.0 WHERE similarity_score IS NULL")
    op.alter_column(
        "matching_result",
        "similarity_score",
        existing_type=sa.Float(),
        nullable=False,
    )
    op.drop_column("matching_result", "source")
