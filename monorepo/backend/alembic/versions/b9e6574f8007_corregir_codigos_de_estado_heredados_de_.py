"""corregir codigos de estado heredados de licitaciones

Revision ID: b9e6574f8007
Revises: 17a3c4130f5a
Create Date: 2026-08-28

Migración de **datos**, no de esquema: no toca ninguna tabla ni columna.

La tabla `tender_status` se sembró con la numeración de la API de Licitaciones
(1, 2, 6, 7, 8, 18), que no es la de Compra Ágil v2. Medido contra la API el 28
de agosto de 2026 —consultando el listado con `estado=<valor>`—, la numeración
real es 2=publicada, 3=cerrada, 5=cancelada, 6=desierta.

Además, `code` guardaba `str(id)` en vez del código semántico, porque el estado
se derivaba de un mapa aparte. Ahora `TenderRepository._to_entity` lee `code`
directamente, así que esa columna tiene que llevar el valor real.

Lo que NO hace esta migración: corregir el `status_id` de las licitaciones ya
guardadas. Una licitación ingerida con `status_id = 6` bajo el mapa viejo se
guardó creyendo que era "publicada" y ahora pasará a leerse como "desierta", que
es lo correcto según la API pero cambia su visibilidad. Reasignarlas requiere
volver a consultar la API por cada código, así que corresponde a una
reingesta, no a una migración a ciegas. Ver PENDIENTES 6.24.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b9e6574f8007"
down_revision: str | Sequence[str] | None = "17a3c4130f5a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# El mapeo medido. Se escribe literal y no se importa de app.shared.constants a
# propósito: una migración tiene que seguir haciendo lo mismo dentro de diez
# años, aunque para entonces la constante haya cambiado.
ESTADOS = {
    2: "publicada",
    3: "cerrada",
    5: "cancelada",
    6: "desierta",
}

# Lo que sembraba la versión anterior, con su significado equivocado. Se borran
# solo las filas que ninguna licitación esté usando: si alguna las referencia,
# el FK lo impediría y además se perdería el rastro de lo ya ingerido.
IDS_HEREDADOS = (1, 7, 8, 18)


def upgrade() -> None:
    for id_, code in ESTADOS.items():
        name = code.capitalize()
        op.execute(
            sa.text(
                """
                INSERT INTO tender_status (id, code, name)
                VALUES (:id, :code, :name)
                ON CONFLICT (id) DO UPDATE SET code = :code, name = :name
                """
            ).bindparams(id=id_, code=code, name=name)
        )

    op.execute(
        sa.text(
            """
            DELETE FROM tender_status
            WHERE id = ANY(:ids)
              AND NOT EXISTS (
                  SELECT 1 FROM tender WHERE tender.status_id = tender_status.id
              )
            """
        ).bindparams(ids=list(IDS_HEREDADOS))
    )


def downgrade() -> None:
    """Restaura el sembrado anterior: code = str(id) y la numeración heredada."""
    heredados = {
        1: "Publicada",
        2: "Publicada",
        6: "Publicada",
        7: "Cerrada",
        8: "Desierta",
        18: "Adjudicada",
    }
    op.execute(sa.text("DELETE FROM tender_status WHERE id IN (3, 5)"))
    for id_, name in heredados.items():
        op.execute(
            sa.text(
                """
                INSERT INTO tender_status (id, code, name)
                VALUES (:id, :code, :name)
                ON CONFLICT (id) DO UPDATE SET code = :code, name = :name
                """
            ).bindparams(id=id_, code=str(id_), name=name)
        )
