"""Borra las cuentas locales y todo lo que cuelga de ellas.

Por qué existe
--------------
Al pasar la autenticación a Supabase Auth, las filas de `users` anteriores
quedan sin `auth_provider_id`: nadie puede volver a entrar en ellas, pero siguen
ocupando el correo y arrastrando perfiles de empresa, licitaciones guardadas,
historiales de chat y alertas. La decisión de producto fue borrarlas.

Por qué no es una migración de Alembic
--------------------------------------
Las migraciones corren en el `preDeployCommand` de Railway, o sea en cada
despliegue y sin que nadie lo pida en ese momento. Un `DELETE FROM users` ahí
sería un borrado de datos disparado por un `git push`. Esto se ejecuta a mano,
una vez, mirando lo que va a pasar.

Orden de borrado
----------------
Ninguna clave foránea a `users.id` declara `ON DELETE`, así que son `NO ACTION`:
un `DELETE FROM users` a secas **falla** mientras algo apunte a esas filas. Hay
que bajar por el árbol de dependencias, de las hojas a la raíz.

Lo que este script NO limpia
----------------------------
Los vectores de los proveedores en Qdrant. Al borrar `supplier` quedan huérfanos
(la misma clase de problema que arregló `fix/vector-huerfano-al-crear-empresa`).
En local se resuelve recreando la colección; en un entorno compartido hay que
mirarlo antes.

Uso
---
    docker compose exec api python -m scripts.reset_cuentas            # dry-run
    docker compose exec api python -m scripts.reset_cuentas --ejecutar

Con el entorno virtual activado, `python -m scripts.reset_cuentas`.
"""

import argparse
import asyncio

from sqlalchemy import text

from app.infrastructure.db import async_session_maker

# De las hojas a la raíz. El orden no es decorativo: invertirlo hace fallar el
# borrado con una violación de clave foránea a mitad de camino.
TABLAS_EN_ORDEN = (
    "notification_delivery",
    "notification",
    "notification_preference",
    "tender_chat_documents",
    "tender_chat_messages",
    "tender_chat_sessions",
    "saved_tender",
    "supplier",
    "users",
)


async def _contar(session) -> dict[str, int]:
    conteos: dict[str, int] = {}
    for tabla in TABLAS_EN_ORDEN:
        resultado = await session.execute(text(f"SELECT count(*) FROM {tabla}"))  # noqa: S608
        conteos[tabla] = resultado.scalar_one()
    return conteos


async def _ejecutar(ejecutar: bool) -> None:
    async with async_session_maker() as session:
        conteos = await _contar(session)

        print("\nFilas que se borrarían:\n")
        for tabla, cantidad in conteos.items():
            print(f"  {tabla:<28} {cantidad:>6}")

        if not ejecutar:
            print(
                "\nNada se borró: esto es un ensayo. Para hacerlo de verdad,"
                "\nvuelve a correrlo con --ejecutar.\n"
            )
            return

        if conteos["users"] == 0:
            print("\nNo hay cuentas que borrar.\n")
            return

        # Todo en una transacción: si falla a mitad, no queda media base con
        # proveedores sin dueño.
        for tabla in TABLAS_EN_ORDEN:
            await session.execute(text(f"DELETE FROM {tabla}"))  # noqa: S608
        await session.commit()

        print("\nListo. Las cuentas se crean de nuevo desde /register.\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Borra las cuentas locales y todo lo que cuelga de ellas. "
            "Sin --ejecutar solo informa."
        )
    )
    parser.add_argument(
        "--ejecutar",
        action="store_true",
        help="Borra de verdad. Es irreversible: perfiles de empresa, "
        "licitaciones guardadas, chats y alertas se van con las cuentas.",
    )
    asyncio.run(_ejecutar(parser.parse_args().ejecutar))


if __name__ == "__main__":
    main()
