"""unir cabezas de ingesta y chat

Revision ID: 5d0cd7e936db
Revises: 9809f07342d5, c952eb0506d2
Create Date: 2026-09-02

No cambia el esquema: solo vuelve a dejar una sola cabeza en el grafo.

Dos trabajos en paralelo colgaron de `7df7c9a1ca0a` sin saber el uno del otro:
la ingesta con su cola de reintentos y su historial de corridas
(`0af9129cc120` → `9809f07342d5`), y las columnas de la HdU 05.2 en
`tender_chat_messages` (`c952eb0506d2`, PR #200). Ninguna de las dos está mal;
el problema es que al mergear ambas a `main` el grafo quedó con dos finales.

Con dos cabezas, `alembic upgrade head` aborta con "Multiple head revisions are
present" y **no aplica nada**. Como las migraciones corren en el
`preDeployCommand` de `railway.toml`, el despliegue entero se cae antes de
levantar la versión nueva: producción sigue sirviendo la anterior y el código
recién mergeado no llega nunca.

Se unen con una migración vacía en vez de repuntar el `down_revision` de
`c952eb0506d2`: esa ya pudo aplicarse en algún entorno, y reescribirla dejaría
esas bases en un estado que Alembic no sabe reconciliar. Unir es aditivo y
funciona igual en una base al día que en una recién creada.

Es la segunda vez que pasa —ver `01dffcf2bdbf`, que unió chat con alertas— y la
causa es la misma: dos ramas largas partiendo del mismo punto. Lo que lo
evitaría de raíz es un CI que corra `alembic heads` sobre cada PR y falle si
devuelve más de una (pendiente 2.3).

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "5d0cd7e936db"
down_revision: str | Sequence[str] | None = ("9809f07342d5", "c952eb0506d2")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Nada que aplicar: la unión ocurre en el grafo, no en el esquema."""


def downgrade() -> None:
    """Nada que deshacer."""
