"""unir cabezas de chat y notificaciones

Revision ID: 01dffcf2bdbf
Revises: b9e6574f8007, e1b10ad7ddaf
Create Date: 2026-08-30 21:05:58.931029

No cambia el esquema: solo vuelve a dejar una sola cabeza en el grafo.

El chat llegó en dos migraciones hermanas, ambas colgando de `82786321a8db`:
`869745767a10` (documentos y mensajes) y `e1b10ad7ddaf` (sesiones). La unión
`17a3c4130f5a` juntó la primera con la de alertas, pero dejó fuera la segunda,
y nadie volvió a apuntar a ella. El grafo quedó con dos finales.

Con dos cabezas, `alembic upgrade head` aborta con "Multiple head revisions are
present" y **no aplica nada**: una base creada desde cero se queda sin esquema,
así que ni el chat ni las alertas pueden funcionar.

Se unen con una migración vacía en vez de repuntar el `down_revision` de
`e1b10ad7ddaf`, porque esa ya pudo aplicarse en algún entorno y reescribirla
dejaría esas bases en un estado que Alembic no sabe reconciliar. Unir es
aditivo y no toca lo ya aplicado.

Es seguro aplicarlas en cualquier orden: ninguna tabla se crea dos veces, y las
del chat solo tienen claves foráneas hacia `tender` y `users`, no entre ellas.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "01dffcf2bdbf"
down_revision: str | Sequence[str] | None = ("b9e6574f8007", "e1b10ad7ddaf")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
