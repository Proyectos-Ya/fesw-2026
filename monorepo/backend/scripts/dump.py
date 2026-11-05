"""Dump de licitaciones para desarrollo: exportar, cargar y revivir.

Un solo archivo (`project-data/chiripa_tenders.xlsx`) y tres pasos:

    # Quien tiene acceso de solo lectura a producción saca un pedazo y lo comparte.
    DATABASE_URL="postgresql://matching_lectura...@<host>:5432/postgres" python -m scripts.dump exportar --limite 300

    # Cada persona lo carga: reemplaza el catálogo local e indexa Qdrant.
    python -m scripts.dump cargar

    # Cuando las licitaciones vuelven a vencer, sin recargar nada.
    python -m scripts.dump revivir

**exportar** solo ejecuta `SELECT` contra la base de `DATABASE_URL`. Toma las
licitaciones vigentes y, con `--limite`, primero las que traen dirección de
entrega y después las que además tienen coordenadas (HU-22).

**cargar** deja el entorno local como recién instalado, sin preguntar: borra el
catálogo, las cuentas (también los logins de Supabase Auth), las empresas y todo
lo que cuelga de ellas, en Postgres y en Qdrant. Después carga el dump, lo revive
y calcula los vectores de `tenders`, `tender_items` y `tender_lexical` con el
mismo código que la ingesta. Se niega a correr si la base o Qdrant no son
locales. El embedding sale de `EMBEDDING_PROVIDER`:
con `deepinfra` tarda un par de minutos; con `local`, bastante más.

Las columnas de cada tabla se cargan según el esquema de la base, no con una
lista fija: una columna nueva viaja en el dump sin tocar este script. Quedan
fuera `attachments_synced_at` y `offers_checked_at`, que son estado de los
procesos de quien exportó.

**revivir** corre todas las fechas del catálogo en bloque, en días enteros, hasta
que la licitación publicada más reciente quede publicada hoy. El catálogo vuelve a
verse como el día del export, con los mismos plazos hasta el cierre. Solo toca las
licitaciones del dump (las que no tienen fila en `tender_metadata`, la cola de la
ingesta real), actualiza el payload de Qdrant sin recalcular vectores y borra el
caché de `matching_result`.
"""

import argparse
import asyncio
import logging
import math
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg
import pandas as pd
from sqlalchemy.engine import make_url

from app.config import settings
from app.shared.comunas import resolve_comuna
from app.shared.regions import UNKNOWN_REGION_ID, normalize_region_name

DUMP = Path(__file__).resolve().parents[3] / "project-data" / "chiripa_tenders.xlsx"

HOJAS = ("region", "tender_status", "buyer_institution", "tender", "tender_item")

COLECCIONES = ("tenders", "tender_items", "tender_lexical")

# Estado de procesos de la base de origen, no datos de la licitación: con
# `attachments_synced_at` puesto, la app daría por bajados unos anexos que en
# la base local no existen.
COLUMNAS_DE_ESTADO_LOCAL = frozenset({"attachments_synced_at", "offers_checked_at"})

# Fechas de calendario que se corren juntas al revivir.
COLUMNAS_DE_FECHA = (
    "published_at",
    "closing_at",
    "last_change_at",
    "first_call_closing_at",
    "second_call_closing_at",
)

# Solo las licitaciones del dump: las de la ingesta real pasan por la cola.
DEL_DUMP = "NOT EXISTS (SELECT 1 FROM tender_metadata m WHERE m.code = t.code)"


def _dsn() -> str:
    """DSN para asyncpg, que no entiende el prefijo `+asyncpg` de SQLAlchemy."""
    url = make_url(settings.database_url)
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def _silenciar_sql(engine) -> None:
    """Con IS_DEV el engine registra cada consulta; acá solo ensucia el progreso."""
    engine.sync_engine.echo = False
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)


async def _probar_embedding() -> None:
    """Falla antes de borrar nada si el proveedor de embeddings no responde."""
    from app.bootstrap.builders import build_embedding_service

    try:
        await build_embedding_service().embed(["prueba"])
    except Exception as error:  # noqa: BLE001 - se reporta tal cual y se sale
        sys.exit(
            f"El embedding ({settings.embedding_provider}) no funciona: {error}\n"
            "Revisa EMBEDDING_API_KEY en monorepo/.env. No se tocó nada."
        )


def _host(url: str) -> str:
    """Solo el host, para mostrarlo sin la contraseña."""
    return make_url(url).host or "?"


# --- exportar ---------------------------------------------------------------


def consultas_de_export(
    limite: int | None, columnas_tender: set[str] = frozenset()
) -> tuple[dict[str, str], list[int]]:
    """Una consulta por hoja del xlsx y los parámetros que comparten.

    Solo licitaciones VIGENTES: el matching descarta lo cerrado. Las tres hojas
    que dependen de la selección parten del mismo CTE, sin filas huérfanas. El
    orden por `md5(id)` reparte la muestra entre regiones y da siempre el mismo
    pedazo para la misma base. Solo se prioriza por columnas de entrega que el
    origen ya tenga, porque producción puede ir una migración atrás.
    """
    prioridades = [
        f"{columna} IS NULL"
        for columna in ("delivery_address", "delivery_lat")
        if columna in columnas_tender
    ]
    orden = ", ".join([*prioridades, "md5(id::text)"])
    if limite is None:
        seleccion = "SELECT id FROM tender WHERE closing_at > now()"
        parametros: list[int] = []
    else:
        seleccion = f"""
            SELECT id FROM tender
            WHERE closing_at > now()
            ORDER BY {orden}
            LIMIT $1"""
        parametros = [limite]

    con_seleccion = f"WITH seleccion AS ({seleccion})"
    consultas = {
        "region": "SELECT * FROM region",
        "tender_status": "SELECT * FROM tender_status",
        "buyer_institution": f"""{con_seleccion}
            SELECT DISTINCT b.* FROM buyer_institution b
            JOIN tender t ON t.buyer_rut = b.rut
            JOIN seleccion s ON s.id = t.id""",
        "tender": f"""{con_seleccion}
            SELECT t.* FROM tender t JOIN seleccion s ON s.id = t.id""",
        "tender_item": f"""{con_seleccion}
            SELECT ti.* FROM tender_item ti JOIN seleccion s ON s.id = ti.tender_id""",
    }
    return consultas, parametros


async def exportar(limite: int | None, archivo: Path) -> None:
    print(f"Origen  : {_host(settings.database_url)} (solo lectura)")
    print(f"Archivo : {archivo}\n")
    archivo.parent.mkdir(parents=True, exist_ok=True)

    conn = await asyncpg.connect(_dsn())
    try:
        columnas = set((await _esquema(conn, "tender")).keys())
        consultas, parametros = consultas_de_export(limite, columnas)
        hojas: dict[str, pd.DataFrame] = {}
        for hoja, consulta in consultas.items():
            filas = await conn.fetch(
                consulta, *(parametros if "seleccion" in consulta else [])
            )
            hojas[hoja] = pd.DataFrame([dict(f) for f in filas])
    finally:
        await conn.close()

    with pd.ExcelWriter(archivo, engine="openpyxl") as writer:
        for hoja, df in hojas.items():
            df.to_excel(writer, sheet_name=hoja, index=False)

    t = hojas["tender"]
    print(
        f"{len(t)} licitaciones, {len(hojas['tender_item'])} partidas, "
        f"{len(hojas['buyer_institution'])} compradores."
    )
    print(
        f"{_con_dato(t, 'delivery_address')} con dirección de entrega, "
        f"{_con_dato(t, 'delivery_lat')} ya ubicadas en el mapa."
    )
    if t.empty:
        print(
            "\n[AVISO] El origen no tiene licitaciones vigentes: el dump quedó vacío."
        )
    print("\nSe carga con: python -m scripts.dump cargar")


def _con_dato(df: pd.DataFrame, columna: str) -> int:
    """Filas con la columna llena; 0 si la hoja no la tiene."""
    return int(df[columna].notna().sum()) if columna in df.columns else 0


# --- cargar -----------------------------------------------------------------


def columnas_a_cargar(columnas_dump: list[str], esquema: dict[str, str]) -> list[str]:
    """Columnas del xlsx que existen en la tabla, menos el estado local."""
    return [
        columna
        for columna in columnas_dump
        if columna in esquema and columna not in COLUMNAS_DE_ESTADO_LOCAL
    ]


def _limpiar(valor: Any) -> Any:
    """Normaliza los tipos de pandas a los que acepta asyncpg."""
    if valor is None or (not isinstance(valor, (list, dict)) and pd.isna(valor)):
        return None
    if isinstance(valor, pd.Timestamp):
        return valor.to_pydatetime().replace(tzinfo=None)
    # numpy int64/float64/bool_ no son los tipos de Python.
    if hasattr(valor, "item"):
        return valor.item()
    return valor


def convertir(valor: Any, tipo: str) -> Any:
    """Lleva una celda de pandas al tipo de Postgres de su columna."""
    limpio = _limpiar(valor)
    if limpio is None:
        return None
    if tipo == "uuid":
        return UUID(str(limpio))
    if tipo in ("character varying", "text"):
        # `code` o un RUT sin guion se leen del xlsx como número.
        return str(limpio)
    if tipo in ("integer", "bigint", "smallint"):
        # Una columna entera con celdas vacías la lee pandas como float.
        return int(limpio)
    if tipo == "double precision":
        return float(limpio)
    if tipo == "boolean":
        return bool(limpio)
    if tipo.startswith("timestamp") and isinstance(limpio, str):
        return pd.Timestamp(limpio).to_pydatetime().replace(tzinfo=None)
    return limpio


async def _esquema(conn: asyncpg.Connection, tabla: str) -> dict[str, str]:
    """columna -> tipo de Postgres."""
    filas = await conn.fetch(
        """SELECT column_name, data_type FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = $1""",
        tabla,
    )
    return {f["column_name"]: f["data_type"] for f in filas}


async def _insertar(
    conn: asyncpg.Connection, tabla: str, df: pd.DataFrame, clave: str
) -> int:
    """Inserta las filas con las columnas que tabla y hoja comparten."""
    if df.empty:
        return 0
    esquema = await _esquema(conn, tabla)
    columnas = columnas_a_cargar(list(df.columns), esquema)
    ignoradas = sorted(set(df.columns) - set(columnas) - COLUMNAS_DE_ESTADO_LOCAL)
    if ignoradas:
        print(f"  [{tabla}] columnas del dump que la tabla no tiene: {ignoradas}")
    marcadores = ", ".join(f"${n}" for n in range(1, len(columnas) + 1))
    filas = [
        tuple(convertir(fila[c], esquema[c]) for c in columnas)
        for _, fila in df.iterrows()
    ]
    await conn.executemany(
        f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES ({marcadores}) "
        f"ON CONFLICT ({clave}) DO NOTHING",
        filas,
    )
    return len(filas)


def _mapa_de_regiones(hoja_region: pd.DataFrame) -> dict[int, int]:
    """id de región del dump -> id administrativo, resolviendo por nombre.

    Los dumps viejos traen la numeración de norte a sur (Metropolitana=7); el
    código usa la de Mercado Público (Metropolitana=13).
    """
    mapa: dict[int, int] = {}
    for _, fila in hoja_region.iterrows():
        origen = int(fila["id"])
        if origen == UNKNOWN_REGION_ID:
            mapa[origen] = UNKNOWN_REGION_ID
            continue
        propio = normalize_region_name(str(fila["name"]))
        if propio is None:
            print(f"  [AVISO] región no reconocida: {fila['name']}")
        mapa[origen] = propio if propio is not None else UNKNOWN_REGION_ID
    return mapa


async def _compradores(
    conn: asyncpg.Connection, compradores: pd.DataFrame, regiones: pd.DataFrame
) -> pd.DataFrame:
    """Traduce la región y resuelve la comuna, igual que la ingesta real."""
    traduccion = _mapa_de_regiones(regiones)
    comunas = {
        f["name"]: f["id"] for f in await conn.fetch("SELECT id, name FROM comuna")
    }
    df = compradores.copy().astype(object)
    for indice, fila in df.iterrows():
        df.at[indice, "region_id"] = traduccion.get(
            int(fila["region_id"]), UNKNOWN_REGION_ID
        )
        nombre, fuente = resolve_comuna(
            str(fila["name"]),
            use_generic_fallback=settings.enable_comuna_generic_heuristic,
        )
        comuna_id = comunas.get(nombre) if nombre else None
        df.at[indice, "comuna_id"] = comuna_id
        df.at[indice, "comuna_resolution_source"] = fuente if comuna_id else None
    return df


def _exigir_local() -> None:
    from scripts.ingesta_compartida import es_local

    remotos = [
        nombre
        for nombre, url in (
            ("la base", settings.database_url),
            ("Qdrant", settings.qdrant_url),
        )
        if not es_local(url)
    ]
    if remotos:
        sys.exit(
            f"{' y '.join(remotos).capitalize()} no es local. Este comando reemplaza "
            "el catálogo y solo corre contra tu máquina."
        )


async def _vaciar_entorno(conn: asyncpg.Connection, qdrant) -> None:
    """Borra catálogo, cuentas y empresas: nada de lo anterior sobrevive.

    `CASCADE` sigue las claves foráneas, así que se lleva también lo que cuelga
    de cada tabla (guardadas, kanban, chats, cotizaciones, alertas). Las cuentas
    de `auth.users` son los logins de Supabase Auth: sin borrarlas, el correo
    seguiría registrado sin perfil en la app.
    """
    from qdrant_client.models import Filter, FilterSelector

    await conn.execute(
        "TRUNCATE tender_item, tender, tender_metadata, matching_result, "
        "buyer_institution, users, supplier CASCADE"
    )
    if await conn.fetchval("SELECT to_regclass('auth.users') IS NOT NULL"):
        await conn.execute("DELETE FROM auth.users")
    for coleccion in COLECCIONES:
        if await qdrant.collection_exists(coleccion):
            await qdrant.delete_collection(coleccion)
    # La API crea `suppliers` al arrancar y no la vuelve a crear: se vacía en vez
    # de borrarla, para no tener que reiniciarla.
    if await qdrant.collection_exists("suppliers"):
        await qdrant.delete(
            collection_name="suppliers", points_selector=FilterSelector(filter=Filter())
        )


async def cargar(archivo: Path) -> None:
    from qdrant_client import AsyncQdrantClient

    from app.infrastructure.db import engine
    from scripts.ingesta_compartida import preparar_destino

    _silenciar_sql(engine)
    _exigir_local()
    if not archivo.exists():
        sys.exit(f"No se encontró el dump en {archivo}")
    print(f"Dump        : {archivo}")
    print(f"Embeddings  : {settings.embedding_provider}")
    if settings.embedding_provider == "local":
        print(
            "  [AVISO] Con EMBEDDING_PROVIDER=local los vectores se calculan en la CPU "
            "y tarda mucho más. Con deepinfra y EMBEDDING_API_KEY son un par de minutos."
        )
    print()

    libro = pd.read_excel(archivo, sheet_name=None)
    faltan = [h for h in HOJAS if h not in libro]
    if faltan:
        sys.exit(f"Al dump le faltan hojas: {faltan}")
    await _probar_embedding()
    t0 = time.perf_counter()

    conn = await asyncpg.connect(_dsn())
    qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    try:
        print("1/4 Vaciando el entorno local (catálogo, cuentas y empresas)...")
        await _vaciar_entorno(conn, qdrant)
        await preparar_destino(engine, qdrant)

        print("2/4 Cargando Postgres...")
        await _insertar(conn, "tender_status", libro["tender_status"], "id")
        compradores = await _compradores(
            conn, libro["buyer_institution"], libro["region"]
        )
        await _insertar(conn, "buyer_institution", compradores, "rut")
        n = await _insertar(conn, "tender", libro["tender"], "id")
        partidas = await _insertar(conn, "tender_item", libro["tender_item"], "id")
        con_direccion = await conn.fetchval(
            "SELECT count(delivery_address) FROM tender"
        )
        print(
            f"  {n} licitaciones ({con_direccion} con dirección de entrega), "
            f"{partidas} partidas, {len(compradores)} compradores"
        )

        dias, _ = await _revivir_sql(conn)
        print(f"3/4 Fechas corridas {dias} días para que el catálogo quede vigente.")
    finally:
        await conn.close()

    print("4/4 Indexando Qdrant...")
    try:
        await _indexar_tenders(engine, qdrant)
    finally:
        await qdrant.close()
    await _indexar_partidas_y_lexico()
    await engine.dispose()

    print(f"\nListo en {(time.perf_counter() - t0) / 60:.1f} min.")


# --- indexar ----------------------------------------------------------------


def seleccionar_pendientes(
    textos: dict[UUID, str], ya_indexadas: set[UUID], reindexar: bool = False
) -> list[UUID]:
    """Ids a indexar, del texto más corto al más largo.

    Se omiten los que ya están en Qdrant, salvo con `reindexar`. Ordenados por
    largo, los lotes casi no rellenan, y lo que más memoria pide queda al final.
    """
    ids = [i for i in textos if reindexar or i not in ya_indexadas]
    return sorted(ids, key=lambda i: len(textos[i]))


class _Simple:
    """Objeto mínimo con los atributos que `TextBuilder` lee."""

    def __init__(self, name: str, description: str | None = None) -> None:
        self.name = name
        self.description = description


_SQL_LICITACIONES = """
    SELECT t.id, t.name, t.description, t.status_id, t.closing_at,
           t.published_at, t.available_amount_clp, b.region_id,
           b.comuna_id, c.provincia_id
    FROM tender t
    LEFT JOIN buyer_institution b ON b.rut = t.buyer_rut
    LEFT JOIN comuna c ON c.id = b.comuna_id
"""


async def _indexar_tenders(engine, qdrant) -> None:
    """Colección `tenders`: un vector por licitación, como la ingesta."""
    from sqlalchemy import text

    from app.application.services.text_builder import TextBuilder
    from app.bootstrap.builders import build_embedding_service
    from app.infrastructure.repositories.qdrant_tender_repository import (
        QdrantTenderRepository,
    )
    from scripts.backfill_tender_payloads import _build_payload

    async with engine.connect() as c:
        licitaciones = {
            f.id: f for f in (await c.execute(text(_SQL_LICITACIONES))).all()
        }
        partidas: dict[UUID, list[_Simple]] = {}
        for f in (
            await c.execute(
                text("SELECT tender_id, name, description FROM tender_item")
            )
        ).all():
            if f.name:
                partidas.setdefault(f.tender_id, []).append(
                    _Simple(f.name, f.description)
                )

    constructor = TextBuilder()
    textos = {
        i: constructor.build_from_tender(
            tender=_Simple(f.name or "", f.description), items=partidas.get(i, [])
        )
        for i, f in licitaciones.items()
    }
    repositorio = QdrantTenderRepository(
        client=qdrant, vector_size=settings.embedding_vector_size
    )
    embeddings = build_embedding_service()
    # Con BGE-M3 en la CPU, lotes grandes se quedan sin memoria con partidas
    # largas; por API el proveedor acepta lotes mayores.
    lote = 8 if settings.embedding_provider == "local" else 64
    pendientes = seleccionar_pendientes(textos, set())
    t0 = time.perf_counter()
    for inicio in range(0, len(pendientes), lote):
        ids = pendientes[inicio : inicio + lote]
        vectores = await embeddings.embed([textos[i] for i in ids])
        for i, vector in zip(ids, vectores, strict=True):
            await repositorio.upsert(
                tender_id=i, embedding=vector, payload=_build_payload(licitaciones[i])
            )
        print(
            f"  tenders: {min(inicio + lote, len(pendientes))}/{len(pendientes)} "
            f"({time.perf_counter() - t0:.0f} s)",
            flush=True,
        )


async def _indexar_partidas_y_lexico() -> None:
    """`tender_items` y `tender_lexical`, con los mismos scripts de backfill.

    Sin estas dos colecciones el matching calcula los vectores de las partidas en
    cada petición del dashboard, y el canal léxico no devuelve nada.
    """
    from scripts import backfill_tender_item_vectors as partidas
    from scripts import backfill_tender_lexical as lexico

    print("  tender_items:")
    await partidas.cargar(
        argparse.Namespace(
            solo_payload=False,
            incluir_cerradas=False,
            tamano_lote=partidas.TAMANO_LOTE_EMBEDDING,
            limite=None,
        )
    )
    print("  tender_lexical:")
    await lexico.ejecutar(
        argparse.Namespace(
            solo_contar=False, incluir_cerradas=False, forzar=False, limite=None
        )
    )


# --- revivir ----------------------------------------------------------------


def dias_para_revivir(ultima_publicacion: datetime | None, ahora: datetime) -> int:
    """Días enteros que hay que sumarle al catálogo para que la última
    publicación quede hoy. 0 si ya está al día o no hay licitaciones."""
    if ultima_publicacion is None:
        return 0
    return max(0, math.floor((ahora - ultima_publicacion) / timedelta(days=1)))


async def _revivir_sql(conn: asyncpg.Connection) -> tuple[int, list[UUID]]:
    """Corre las fechas de las licitaciones del dump. Devuelve días e ids."""
    ahora = datetime.now(UTC).replace(tzinfo=None)
    ultima = await conn.fetchval(
        f"SELECT max(published_at) FROM tender t WHERE {DEL_DUMP}"
    )
    dias = dias_para_revivir(ultima, ahora)
    if not dias:
        return 0, []
    esquema = await _esquema(conn, "tender")
    asignaciones = ", ".join(
        f"{c} = {c} + make_interval(days => $1)"
        for c in COLUMNAS_DE_FECHA
        if c in esquema
    )
    filas = await conn.fetch(
        f"UPDATE tender t SET {asignaciones} WHERE {DEL_DUMP} RETURNING t.id", dias
    )
    # El ranking guardado se calculó con las fechas viejas.
    await conn.execute("TRUNCATE matching_result")
    return dias, [f["id"] for f in filas]


async def revivir() -> None:
    from qdrant_client import AsyncQdrantClient
    from sqlalchemy import bindparam, text

    from app.infrastructure.db import engine
    from app.infrastructure.repositories.qdrant_lexical_tender_repository import (
        QdrantLexicalTenderRepository,
    )
    from app.infrastructure.repositories.qdrant_tender_item_vector_repository import (
        QdrantTenderItemVectorRepository,
    )
    from app.infrastructure.repositories.qdrant_tender_repository import (
        QdrantTenderRepository,
    )
    from scripts.backfill_tender_payloads import _build_payload

    _silenciar_sql(engine)
    _exigir_local()
    conn = await asyncpg.connect(_dsn())
    try:
        dias, ids = await _revivir_sql(conn)
        vigentes = await conn.fetchval(
            f"SELECT count(*) FROM tender t WHERE {DEL_DUMP} AND closing_at > now()"
        )
    finally:
        await conn.close()
    if not dias:
        print(
            f"El catálogo ya está al día ({vigentes} licitaciones del dump vigentes)."
        )
        return
    print(f"{len(ids)} licitaciones corridas {dias} días; {vigentes} vigentes.")

    qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    try:
        async with engine.connect() as c:
            filas = (
                await c.execute(
                    text(_SQL_LICITACIONES + " WHERE t.id IN :ids").bindparams(
                        bindparam("ids", expanding=True)
                    ),
                    {"ids": ids},
                )
            ).all()
        payloads = {f.id: _build_payload(f) for f in filas}
        repos = {
            "tenders": QdrantTenderRepository(
                client=qdrant, vector_size=settings.embedding_vector_size
            ),
            "tender_items": QdrantTenderItemVectorRepository(
                client=qdrant, vector_size=settings.embedding_vector_size
            ),
            "tender_lexical": QdrantLexicalTenderRepository(client=qdrant),
        }
        sin_punto = 0
        for nombre, repo in repos.items():
            if not await qdrant.collection_exists(nombre):
                continue
            existentes = await _ids_con_punto(qdrant, nombre, list(payloads))
            if nombre == "tenders":
                sin_punto = len(payloads) - len(existentes)
            for i in existentes if nombre != "tender_items" else payloads:
                await repo.set_payload(i, payloads[i])
        print("Payload de Qdrant actualizado (sin recalcular vectores).")
        if sin_punto:
            print(
                f"[AVISO] {sin_punto} licitaciones no están en Qdrant y no saldrán en "
                "el matching. Para reindexarlas: python -m scripts.dump cargar"
            )
    finally:
        await qdrant.close()
        await engine.dispose()


async def _ids_con_punto(qdrant, coleccion: str, ids: list[UUID]) -> list[UUID]:
    """Cuáles de estos ids tienen punto en la colección."""
    existentes: list[UUID] = []
    for inicio in range(0, len(ids), 256):
        puntos = await qdrant.retrieve(
            collection_name=coleccion,
            ids=[str(i) for i in ids[inicio : inicio + 256]],
            with_payload=False,
            with_vectors=False,
        )
        existentes.extend(UUID(str(p.id)) for p in puntos)
    return existentes


def main() -> None:
    # Sin esto, redirigido a un archivo, el error de `sys.exit` sale antes que el
    # progreso que lo explica.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser(
        "exportar", help="Escribe el dump desde la base de DATABASE_URL."
    )
    p.add_argument(
        "--limite",
        type=int,
        default=None,
        help="Cuántas licitaciones; prioriza las que traen dirección de entrega.",
    )
    p.add_argument("--archivo", type=Path, default=DUMP, help="Ruta del xlsx.")

    p = sub.add_parser(
        "cargar",
        help="Borra todo el entorno local (catálogo, cuentas, empresas) y carga el dump.",
    )
    p.add_argument("--archivo", type=Path, default=DUMP, help="Ruta del xlsx.")

    sub.add_parser(
        "revivir", help="Corre las fechas del catálogo para que vuelva a estar vigente."
    )

    args = parser.parse_args()
    if args.comando == "exportar":
        asyncio.run(exportar(args.limite, args.archivo))
    elif args.comando == "cargar":
        asyncio.run(cargar(args.archivo))
    else:
        asyncio.run(revivir())


if __name__ == "__main__":
    main()
