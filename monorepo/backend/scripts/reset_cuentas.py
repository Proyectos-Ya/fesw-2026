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

Cómo decide qué borrar
----------------------
No hay lista escrita a mano. La primera versión la tenía y estaba incompleta:
seguía solo las claves foráneas a `users.id` y se olvidaba de las que cuelgan de
`supplier.id` (`matching_result`, `deep_analysis`, `tender_ai_analysis`), así que
fallaba a mitad con una violación de clave foránea. Una lista escrita a mano
envejece mal: cada tabla nueva que apunte a una cuenta la deja obsoleta y nadie
se entera hasta que revienta.

Ahora se le pregunta a Postgres. Se parte de `users` y `supplier` y se sigue el
grafo de claves foráneas hacia abajo —quién referencia a quién— hasta cerrarlo.
El borrado es un `TRUNCATE ... CASCADE`, que hace exactamente ese mismo recorrido
del lado del motor, así que no puede quedarse corto.

`CASCADE` solo alcanza a lo que *depende* de las tablas nombradas. Las
licitaciones, regiones y comunas no dependen de una cuenta: no se tocan, y no
hace falta recargar el corpus ni regenerar embeddings.

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

# De dónde cuelga una cuenta. `supplier` va aparte de `users` y no como
# dependiente suyo porque su `user_id` es nullable: un proveedor sin dueño
# igual es un perfil de empresa que hay que llevarse.
RAICES = ("users", "supplier")

# Cierre transitivo del grafo de claves foráneas: `users`, `supplier`, y todo lo
# que las referencia directa o indirectamente. `regclass` devuelve el nombre ya
# resuelto contra el search_path, así que no hay que armar el esquema a mano.
_DEPENDIENTES = text("""
    WITH RECURSIVE raices(tabla) AS (
        SELECT unnest(CAST(:raices AS text[]))
    ),
    cerrada(tabla) AS (
        SELECT tabla FROM raices
        UNION
        SELECT c.conrelid::regclass::text
        FROM pg_constraint c
        JOIN cerrada ON c.confrelid::regclass::text = cerrada.tabla
        WHERE c.contype = 'f'
          AND c.conrelid <> c.confrelid
    )
    SELECT tabla FROM cerrada ORDER BY tabla
""")


async def _tablas_afectadas(session) -> list[str]:
    resultado = await session.execute(_DEPENDIENTES, {"raices": list(RAICES)})
    return [fila[0] for fila in resultado]


async def _contar(session, tablas: list[str]) -> dict[str, int]:
    conteos: dict[str, int] = {}
    for tabla in tablas:
        resultado = await session.execute(text(f'SELECT count(*) FROM "{tabla}"'))  # noqa: S608
        conteos[tabla] = resultado.scalar_one()
    return conteos


async def _ejecutar(ejecutar: bool) -> None:
    async with async_session_maker() as session:
        tablas = await _tablas_afectadas(session)
        conteos = await _contar(session, tablas)

        print("\nFilas que se borrarían:\n")
        for tabla, cantidad in conteos.items():
            print(f"  {tabla:<28} {cantidad:>8}")
        print(f"\n  {'TOTAL':<28} {sum(conteos.values()):>8}")

        if not ejecutar:
            print(
                "\nNada se borró: esto es un ensayo. Para hacerlo de verdad,"
                "\nvuelve a correrlo con --ejecutar.\n"
            )
            return

        if conteos.get("users", 0) == 0 and conteos.get("supplier", 0) == 0:
            print("\nNo hay cuentas ni perfiles que borrar.\n")
            return

        # Una sola sentencia y una sola transacción: si algo falla, no queda
        # media base con proveedores sin dueño.
        nombres = ", ".join(f'"{t}"' for t in RAICES)
        await session.execute(text(f"TRUNCATE TABLE {nombres} CASCADE"))  # noqa: S608
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
