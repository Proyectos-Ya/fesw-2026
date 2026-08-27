"""Carga el dataset de prueba (`chiripa_tenders.xlsx`) en PostgreSQL.

Modo A del flujo de desarrollo: un corpus reproducible, sin consumir cuota de la
API de Mercado Público.

    python tests/matching_evaluation/load_postgres_robust.py

Después hay que indexar los vectores:

    python tests/matching_evaluation/load_dataset.py

La conexión sale de `app.config.settings`, así que respeta el `.env` y funciona
igual contra Supabase local o contra el Postgres que se configure.

**Remapeo de regiones.** El xlsx trae la numeración antigua, de norte a sur
(Arica=1 ... Metropolitana=7). El código usa la administrativa, que es la que
entrega Mercado Público (Tarapacá=1 ... Metropolitana=13). **Las 16 difieren**, así
que cargar los ids tal cual dejaría cada licitación en la región equivocada — y
como el matching filtra por región, los resultados saldrían vacíos o absurdos.
Por eso se traducen por nombre.

**Fechas revividas.** El xlsx es una foto con fecha de vencimiento: al mes ya no
queda ninguna licitación vigente y el matching, que descarta lo cerrado, no
devuelve nada. Antes de insertar, a cada licitación vencida se le suman los meses
necesarios (ver `date_shift.py`), así el dataset sirve igual de aquí a un año.
"""

import asyncio
import sys
from pathlib import Path
from typing import SupportsInt, cast
from uuid import UUID

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import asyncpg  # noqa: E402
import pandas as pd  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlmodel.ext.asyncio.session import AsyncSession  # noqa: E402

from app.config import settings  # noqa: E402
from app.infrastructure.db import engine  # noqa: E402
from app.infrastructure.seeder import seed_database_metadata  # noqa: E402
from app.shared.regions import UNKNOWN_REGION_ID, normalize_region_name  # noqa: E402
from tests.matching_evaluation.date_shift import (  # noqa: E402
    desplazar_licitaciones_vencidas,
)

EXCEL_PATH = BASE_DIR.parents[1] / "project-data" / "chiripa_tenders.xlsx"


def _dsn() -> str:
    """DSN para asyncpg, que no entiende el prefijo `+asyncpg` de SQLAlchemy."""
    url = make_url(settings.database_url)
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def _limpiar(valor):
    """Normaliza los tipos de pandas a los que acepta asyncpg."""
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, pd.Timestamp):
        return valor.to_pydatetime().replace(tzinfo=None)
    # numpy int64/float64 no son los int/float de Python
    if hasattr(valor, "item"):
        return valor.item()
    return valor


def _uuid(valor):
    """Las columnas uuid de Postgres no aceptan el texto: hay que pasar UUID."""
    limpio = _limpiar(valor)
    return UUID(str(limpio)) if limpio is not None else None


def _texto(valor):
    """Fuerza a str. `code` viene como entero en el xlsx y la columna es varchar."""
    limpio = _limpiar(valor)
    return str(limpio) if limpio is not None else None


def _entero(valor) -> int:
    """Fuerza a int. Indexar una fila de pandas devuelve un tipo unión."""
    return int(cast(SupportsInt, _limpiar(valor)))


def _mapa_de_regiones(hoja_region: pd.DataFrame) -> dict[int, int]:
    """id del xlsx -> id administrativo, resolviendo por nombre."""
    mapa: dict[int, int] = {}
    sin_resolver = []
    for _, fila in hoja_region.iterrows():
        # La fila de respaldo ("Desconocida", id 0) no es una región real y no
        # resuelve por nombre; se mapea a sí misma sin avisar de nada.
        if int(fila["id"]) == UNKNOWN_REGION_ID:
            mapa[UNKNOWN_REGION_ID] = UNKNOWN_REGION_ID
            continue
        propio = normalize_region_name(str(fila["name"]))
        if propio is None:
            sin_resolver.append(fila["name"])
            propio = UNKNOWN_REGION_ID
        mapa[_entero(fila["id"])] = propio
    if sin_resolver:
        print(f"[AVISO] regiones no reconocidas: {sin_resolver}")
    return mapa


async def _sembrar_metadata() -> None:
    """Siembra regiones y estados con el mismo seeder de la aplicación."""
    async with AsyncSession(engine) as sesion:
        await seed_database_metadata(sesion)
    await engine.dispose()


async def main() -> None:
    if not EXCEL_PATH.exists():
        raise SystemExit(f"No se encontró el dataset en {EXCEL_PATH}")

    print(f"[DATASET] Leyendo {EXCEL_PATH.name}...", flush=True)
    libro = pd.ExcelFile(EXCEL_PATH)
    regiones = pd.read_excel(libro, "region")
    estados = pd.read_excel(libro, "tender_status")
    compradores = pd.read_excel(libro, "buyer_institution")
    licitaciones = pd.read_excel(libro, "tender")
    partidas = pd.read_excel(libro, "tender_item")

    vencidas = int(
        (pd.to_datetime(licitaciones["closing_at"]) <= pd.Timestamp.now()).sum()
    )
    licitaciones = desplazar_licitaciones_vencidas(licitaciones)
    if vencidas:
        print(
            f"[DATASET] {vencidas} licitaciones cerradas revividas (+1 mes o los "
            "que hicieran falta)",
            flush=True,
        )

    traduccion = _mapa_de_regiones(regiones)
    print(
        f"[DATASET] {len(licitaciones)} licitaciones, {len(partidas)} partidas, "
        f"{len(compradores)} compradores",
        flush=True,
    )

    conn = await asyncpg.connect(_dsn())
    try:
        # Las regiones y los estados base los siembra el mismo seeder que usa la
        # aplicación, para no tener una segunda fuente de verdad de la
        # numeración. El xlsx trae su propia tabla `region`, pero se ignora: solo
        # se usa para traducir sus ids a los nuestros.
        await _sembrar_metadata()

        for _, e in estados.iterrows():
            await conn.execute(
                """INSERT INTO tender_status (id, code, name) VALUES ($1,$2,$3)
                   ON CONFLICT (id) DO NOTHING""",
                _limpiar(e["id"]),
                _texto(e["code"]),
                _limpiar(e["name"]),
            )
        print(f"[OK] {len(estados)} estados", flush=True)

        for _, c in compradores.iterrows():
            await conn.execute(
                """INSERT INTO buyer_institution (rut, name, region_id, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5)
                   ON CONFLICT (rut) DO UPDATE SET region_id = EXCLUDED.region_id""",
                _texto(c["rut"]),
                _limpiar(c["name"]),
                traduccion.get(_entero(c["region_id"]), UNKNOWN_REGION_ID),
                _limpiar(c["created_at"]),
                _limpiar(c["updated_at"]),
            )
        print(f"[OK] {len(compradores)} compradores (regiones traducidas)", flush=True)

        # `province` existe en el xlsx pero no en el esquema: la columna se
        # eliminó porque ninguna de las dos APIs de Mercado Público la entrega.
        insertadas = 0
        for _, t in licitaciones.iterrows():
            await conn.execute(
                """INSERT INTO tender (
                       id, code, name, description, status_id, published_at,
                       closing_at, last_change_at, buyer_rut, buyer_unit,
                       available_amount_clp, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                   ON CONFLICT (id) DO NOTHING""",
                _uuid(t["id"]),
                _texto(t["code"]),
                _limpiar(t["name"]),
                _limpiar(t["description"]),
                _limpiar(t["status_id"]),
                _limpiar(t["published_at"]),
                _limpiar(t["closing_at"]),
                _limpiar(t["last_change_at"]),
                _texto(t["buyer_rut"]),
                _limpiar(t["buyer_unit"]),
                _limpiar(t["available_amount_clp"]),
                _limpiar(t["published_at"]),
                _limpiar(t["last_change_at"]),
            )
            insertadas += 1
        print(f"[OK] {insertadas} licitaciones", flush=True)

        for _, i in partidas.iterrows():
            await conn.execute(
                """INSERT INTO tender_item (
                       id, tender_id, product_code, name, description,
                       quantity, unit_of_measure)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)
                   ON CONFLICT (id) DO NOTHING""",
                _uuid(i["id"]),
                _uuid(i["tender_id"]),
                _texto(i["product_code"]),
                _limpiar(i["name"]),
                _limpiar(i["description"]),
                _limpiar(i["quantity"]),
                _limpiar(i["unit_of_measure"]),
            )
        print(f"[OK] {len(partidas)} partidas", flush=True)

        total = await conn.fetchval("SELECT count(*) FROM tender")
        print(f"\n[LISTO] {total} licitaciones en la base.", flush=True)
        print("Siguiente paso: python tests/matching_evaluation/load_dataset.py")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
