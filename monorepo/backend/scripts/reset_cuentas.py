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

Anexos compartidos
------------------
`TRUNCATE ... CASCADE` vacía tablas *enteras*, sin importar el `ON DELETE` de cada
clave foránea. Los aportes de cada empresa en `attachment_file` apuntan a
`supplier`, así que el reset vaciaría la tabla completa, y con ella las versiones
canónicas (`workspace_id` nulo): el documento oficial que dos fuentes confirmaron
(plan 233, decisión 6). Esas filas no son de ninguna cuenta, y borrar una cuenta no
debe llevárselas, igual que no lo hace el borrado de una sola empresa. No se puede
hacer el TRUNCATE selectivo, así que se apartan en una tabla temporal y se reponen
en la misma transacción. Lo que cuelgue de ellas (las extracciones de la decisión 4)
sí se pierde y se vuelve a calcular.

Qdrant
------
Cada proveedor tiene además un punto en la colección `suppliers`. Se borran
aquí mismo: dejarlos fuera convertía la limpieza en algo que había que acordarse
de terminar a mano, y es justo la clase de huérfano que ya causó un problema
antes (`fix/vector-huerfano-al-crear-empresa`).

El orden es deliberado: primero la base, después los vectores. Al revés, si
fallara el borrado en Postgres quedarían proveedores sin vector —y el matching
deja de funcionar para ellos, en silencio—. En este orden, lo peor que puede
pasar es quedarse con vectores sin dueño, que no rompe nada y se puede repetir.

La colección **no** se borra entera: se eliminan solo los puntos de los
proveedores que se están borrando. Aunque hoy se borren todos, tirar la
colección obligaría a reiniciar la API para que la recree (`main.py`), y eso es
un efecto que un script de limpieza de cuentas no debería tener.

Modo `--solo-empresas`
----------------------
Borra los perfiles de empresa y lo que es de ellos, pero no las cuentas: las filas
de `users` siguen y vuelven a pasar por el wizard. Existe para cambiar la lista de
rubros (HdU 311): las empresas de prueba se borran y no se migran.

No usa `TRUNCATE`. `TRUNCATE ... CASCADE` vacía tablas enteras, y además de
`attachment_file` hay filas compartidas (`workspace_id` nulo) en
`attachment_processing_job` y `tender_digest`, que cuestan llamadas a Gemini y no
son de ninguna empresa. Con `DELETE` decide el `ON DELETE` de cada clave foránea,
y una fila con `workspace_id` o `supplier_id` nulo no apunta a ninguna empresa, así
que nadie la toca.

El grafo es el mismo de arriba, con `supplier` como única raíz, y se le pregunta a
Postgres también qué hace cada clave foránea al borrar (`confdeltype`). Las que
tienen `CASCADE` las resuelve el motor. Las que no (hoy `deep_analysis`,
`matching_result`, `quotation` y `tender_ai_analysis`) harían fallar el `DELETE
FROM supplier`, así que sus filas se borran antes, empezando por las hojas. Las de
`SET NULL` conservan la fila. Todo va en una transacción, y los vectores de Qdrant
se borran después del commit, igual que en el modo de siempre.

Sin `--ejecutar` informa cuántas filas borraría en cada tabla, contando también las
que se irían por `CASCADE`, y cuántos puntos de Qdrant.

Uso
---
    docker compose exec api python -m scripts.reset_cuentas            # dry-run
    docker compose exec api python -m scripts.reset_cuentas --ejecutar
    docker compose exec api python -m scripts.reset_cuentas --solo-empresas
    docker compose exec api python -m scripts.reset_cuentas --solo-empresas --ejecutar

Con el entorno virtual activado, `python -m scripts.reset_cuentas`.
"""

import argparse
import asyncio

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointIdsList
from sqlalchemy import text

from app.config import settings
from app.infrastructure.db import async_session_maker

# Mismo nombre que usa `QdrantSupplierRepository`. Se repite acá y no se importa
# porque ese atributo es privado: la alternativa era exponerlo solo para esto.
COLECCION_PROVEEDORES = "suppliers"

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


# Las versiones canónicas de los anexos (`attachment_file` sin empresa) no son de
# ninguna cuenta: son el documento oficial que dos fuentes confirmaron (plan 233,
# decisión 6). `TRUNCATE ... CASCADE` vaciaría la tabla entera, porque los aportes de
# cada empresa sí apuntan a `supplier`, y no se puede hacer selectivo. Se apartan y se
# reponen en la misma transacción. Lo que cuelgue de ellas (extracciones de la
# decisión 4) sí se pierde y se vuelve a calcular.
_HAY_ANEXOS = text("SELECT to_regclass('attachment_file') IS NOT NULL")
_CONTAR_COMPARTIDOS = text("SELECT count(*) FROM attachment_file WHERE workspace_id IS NULL")
_APARTAR_COMPARTIDOS = text(
    "CREATE TEMP TABLE _anexos_compartidos ON COMMIT DROP AS "
    "SELECT * FROM attachment_file WHERE workspace_id IS NULL"
)
_REPONER_COMPARTIDOS = text("INSERT INTO attachment_file SELECT * FROM _anexos_compartidos")


async def _tablas_afectadas(session) -> list[str]:
    resultado = await session.execute(_DEPENDIENTES, {"raices": list(RAICES)})
    return [fila[0] for fila in resultado]


async def _contar(session, tablas: list[str]) -> dict[str, int]:
    conteos: dict[str, int] = {}
    for tabla in tablas:
        resultado = await session.execute(text(f'SELECT count(*) FROM "{tabla}"'))  # noqa: S608
        conteos[tabla] = resultado.scalar_one()
    return conteos


async def _truncar_conservando_compartidos(session) -> int:
    """TRUNCATE de las cuentas que conserva los anexos compartidos. No hace commit.

    Devuelve cuántas versiones compartidas se repusieron. Todo ocurre en la
    transacción de `session`: si algo falla, el `rollback` deja la base intacta.
    """
    hay_anexos = (await session.execute(_HAY_ANEXOS)).scalar_one()
    if hay_anexos:
        await session.execute(_APARTAR_COMPARTIDOS)
    nombres = ", ".join(f'"{t}"' for t in RAICES)
    await session.execute(text(f"TRUNCATE TABLE {nombres} CASCADE"))  # noqa: S608
    if not hay_anexos:
        return 0
    return (await session.execute(_REPONER_COMPARTIDOS)).rowcount or 0


# Modo `--solo-empresas`: solo `supplier` es raíz, y `users` no se toca.
RAIZ_EMPRESAS = "supplier"

# Las claves foráneas que apuntan a alguna tabla del grafo, con lo que hacen al
# borrar la fila referenciada (`a` no action, `r` restrict, `c` cascade, `n` set
# null, `d` set default) y sus columnas en orden, para las claves compuestas.
_CLAVES_FORANEAS = text("""
    SELECT c.conrelid::regclass::text AS hija,
           c.confrelid::regclass::text AS madre,
           c.confdeltype::text AS al_borrar,
           ARRAY(
               SELECT a.attname::text
               FROM unnest(c.conkey) WITH ORDINALITY AS k(num, orden)
               JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.num
               ORDER BY k.orden
           ) AS columnas_hija,
           ARRAY(
               SELECT a.attname::text
               FROM unnest(c.confkey) WITH ORDINALITY AS k(num, orden)
               JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.num
               ORDER BY k.orden
           ) AS columnas_madre
    FROM pg_constraint c
    WHERE c.contype = 'f'
      AND c.conrelid <> c.confrelid
      AND c.confrelid::regclass::text = ANY(CAST(:tablas AS text[]))
    ORDER BY hija, c.conname
""")

# Borrar la fila madre se lleva la hija (`CASCADE`) o la bloquea (sin acción).
_SE_LLEVA = "c"
_BLOQUEA = ("a", "r")


def _columnas(nombres: list[str], alias: str = "") -> str:
    prefijo = f"{alias}." if alias else ""
    return "(" + ", ".join(f'{prefijo}"{n}"' for n in nombres) + ")"


async def _plan_empresas(session) -> tuple[dict[str, list[str]], list[tuple[str, str]]]:
    """Qué filas se van al borrar todas las empresas, y qué hay que borrar a mano.

    Devuelve `(alcanzadas, borrados)`. `alcanzadas` dice, por tabla, las
    condiciones que cumplen las filas que se irían (por `CASCADE` o a mano); una
    fila se va si cumple cualquiera. `borrados` son los `DELETE` explícitos de las
    tablas sin `CASCADE`, en orden: primero las hojas, para que ninguna clave
    foránea bloquee el siguiente. El `DELETE FROM supplier` va al final, aparte.

    Las condiciones son subconsultas sobre la tabla madre, así que se evalúan
    mientras sus filas todavía existen: por eso se borra de las hojas hacia arriba.
    """
    resultado = await session.execute(_DEPENDIENTES, {"raices": [RAIZ_EMPRESAS]})
    tablas = [fila[0] for fila in resultado]
    claves = (await session.execute(_CLAVES_FORANEAS, {"tablas": tablas})).all()
    por_madre: dict[str, list] = {}
    for clave in claves:
        por_madre.setdefault(clave.madre, []).append(clave)

    alcanzadas: dict[str, list[str]] = {RAIZ_EMPRESAS: ["true"]}
    borrados: list[tuple[str, str]] = []

    def recorrer(madre: str, condicion: str, camino: tuple[str, ...]) -> None:
        for clave in por_madre.get(madre, []):
            if clave.al_borrar != _SE_LLEVA and clave.al_borrar not in _BLOQUEA:
                continue  # SET NULL o SET DEFAULT: la fila hija se queda.
            if clave.hija in camino:
                continue  # Un ciclo: esa tabla ya se está borrando más arriba.
            condicion_hija = (
                f"{_columnas(clave.columnas_hija)} IN "
                f"(SELECT {_columnas(clave.columnas_madre)} "
                f'FROM "{madre}" WHERE {condicion})'
            )
            alcanzadas.setdefault(clave.hija, []).append(condicion_hija)
            recorrer(clave.hija, condicion_hija, (*camino, clave.hija))
            if clave.al_borrar in _BLOQUEA:
                borrados.append((clave.hija, condicion_hija))

    recorrer(RAIZ_EMPRESAS, "true", (RAIZ_EMPRESAS,))
    return alcanzadas, borrados


async def _contar_empresas(session) -> dict[str, int]:
    """Filas que borraría `--solo-empresas`, por tabla. No cambia nada."""
    alcanzadas, _ = await _plan_empresas(session)
    conteos: dict[str, int] = {}
    for tabla in sorted(alcanzadas):
        donde = " OR ".join(f"({c})" for c in alcanzadas[tabla])
        resultado = await session.execute(
            text(f'SELECT count(*) FROM "{tabla}" WHERE {donde}')  # noqa: S608
        )
        conteos[tabla] = resultado.scalar_one()
    return conteos


async def _borrar_empresas(session) -> None:
    """Borra todas las empresas con `DELETE`, sin tocar `users`. No hace commit.

    Primero las filas de las tablas que apuntan a `supplier` sin `CASCADE`, de las
    hojas hacia arriba; después `supplier`, y el `ON DELETE` de cada clave foránea
    resuelve el resto. Las filas con la clave nula no apuntan a ninguna empresa y
    no se tocan. Todo ocurre en la transacción de `session`.
    """
    _, borrados = await _plan_empresas(session)
    for tabla, condicion in borrados:
        await session.execute(text(f'DELETE FROM "{tabla}" WHERE {condicion}'))  # noqa: S608
    await session.execute(text(f'DELETE FROM "{RAIZ_EMPRESAS}"'))  # noqa: S608


async def _ids_de_proveedores(session) -> list[str]:
    resultado = await session.execute(text("SELECT id FROM supplier"))
    return [str(fila[0]) for fila in resultado]


async def _borrar_vectores(ids: list[str]) -> None:
    """Elimina de Qdrant los puntos de esos proveedores.

    Un fallo acá no aborta el script: la base ya quedó limpia y lo que sobra son
    vectores sin dueño, que no rompen nada. Se avisa para poder repetirlo, en
    vez de dejar a quien lo corrió pensando que falló todo.
    """
    if not ids:
        return

    cliente = AsyncQdrantClient(
        url=settings.qdrant_url, api_key=settings.qdrant_api_key
    )
    try:
        await cliente.delete(
            collection_name=COLECCION_PROVEEDORES,
            points_selector=PointIdsList(points=list(ids)),
        )
        print(f"  Qdrant: {len(ids)} vectores eliminados de '{COLECCION_PROVEEDORES}'.")
    except Exception as e:  # noqa: BLE001 - se informa, no se propaga
        print(
            f"\n  AVISO: la base quedó limpia, pero no se pudieron borrar los "
            f"vectores de Qdrant ({settings.qdrant_url}): {e}"
            f"\n  No rompe nada —quedan sin dueño y nadie los consulta—, pero "
            f"conviene repetirlo cuando Qdrant responda."
        )
    finally:
        await cliente.close()


async def _ejecutar_solo_empresas(ejecutar: bool) -> None:
    async with async_session_maker() as session:
        conteos = await _contar_empresas(session)
        ids_proveedores = await _ids_de_proveedores(session)

        print("\nFilas que se borrarían (las cuentas de `users` se conservan):\n")
        for tabla, cantidad in conteos.items():
            print(f"  {tabla:<28} {cantidad:>8}")
        print(f"\n  {'TOTAL':<28} {sum(conteos.values()):>8}")
        print(
            f"\nY en Qdrant: {len(ids_proveedores)} vectores de la colección "
            f"'{COLECCION_PROVEEDORES}'."
        )

        if not ejecutar:
            print(
                "\nNada se borró: esto es un ensayo. Para hacerlo de verdad,"
                "\nvuelve a correrlo con --solo-empresas --ejecutar.\n"
            )
            return

        if conteos.get(RAIZ_EMPRESAS, 0) == 0:
            print("\nNo hay empresas que borrar.\n")
            return

        # Una sola transacción: si un DELETE falla, el rollback deja todo como estaba.
        await _borrar_empresas(session)
        await session.commit()

        await _borrar_vectores(ids_proveedores)

        print("\nListo. Las cuentas siguen y vuelven a crear su empresa.\n")


async def _ejecutar(ejecutar: bool, solo_empresas: bool = False) -> None:
    if solo_empresas:
        await _ejecutar_solo_empresas(ejecutar)
        return
    async with async_session_maker() as session:
        tablas = await _tablas_afectadas(session)
        conteos = await _contar(session, tablas)
        ids_proveedores = await _ids_de_proveedores(session)

        print("\nFilas que se borrarían:\n")
        for tabla, cantidad in conteos.items():
            print(f"  {tabla:<28} {cantidad:>8}")
        print(f"\n  {'TOTAL':<28} {sum(conteos.values()):>8}")
        print(
            f"\nY en Qdrant: {len(ids_proveedores)} vectores de la colección "
            f"'{COLECCION_PROVEEDORES}'."
        )

        if not ejecutar:
            print(
                "\nNada se borró: esto es un ensayo. Para hacerlo de verdad,"
                "\nvuelve a correrlo con --ejecutar.\n"
            )
            return

        if conteos.get("users", 0) == 0 and conteos.get("supplier", 0) == 0:
            print("\nNo hay cuentas ni perfiles que borrar.\n")
            return

        # Una sola transacción: si algo falla, no queda media base con proveedores
        # sin dueño ni anexos compartidos apartados y sin reponer.
        conservados = await _truncar_conservando_compartidos(session)
        await session.commit()
        if conservados:
            print(f"  Anexos compartidos conservados: {conservados}.")

        await _borrar_vectores(ids_proveedores)

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
    parser.add_argument(
        "--solo-empresas",
        action="store_true",
        help="Borra solo los perfiles de empresa y lo que es de ellos, con DELETE. "
        "Conserva las cuentas de users y las filas compartidas (workspace_id nulo).",
    )
    argumentos = parser.parse_args()
    asyncio.run(_ejecutar(argumentos.ejecutar, argumentos.solo_empresas))


if __name__ == "__main__":
    main()
