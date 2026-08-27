"""Vuelca las licitaciones vigentes de la base al dump (`chiripa_tenders.xlsx`).

Último paso al regenerar el dataset, después de `generar_dataset.py`:

    python tests/matching_evaluation/export_dataset.py

Sobrescribe el xlsx, así que se corre a propósito y con la base en el estado que
quieres congelar (ver "Regenerar el dump" en el README).

El origen es la base configurada en el `.env`, no una local fija: se exporta lo
que la aplicación realmente tiene. La carga en sentido contrario es de
`load_postgres_robust.py` y `load_dataset.py`, que traducen las regiones y
reviven las fechas vencidas; acá no hay una segunda copia de esa lógica.
"""

import asyncio
import io
import os
import sys

import pandas as pd

# Asegurar que el directorio raíz de backend esté en sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Forzar UTF-8 en Windows
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if isinstance(sys.stderr, io.TextIOWrapper):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import asyncpg  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

# Cargar variables de entorno del monorepo
DOTENV_PATH = os.path.abspath(os.path.join(BASE_DIR, "../.env"))
load_dotenv(dotenv_path=DOTENV_PATH)

EXCEL_PATH = os.path.abspath(
    os.path.join(BASE_DIR, "../../project-data/chiripa_tenders.xlsx")
)


def _dsn() -> str:
    """DSN para asyncpg, que no entiende el prefijo `+asyncpg` de SQLAlchemy."""
    from sqlalchemy.engine import make_url

    from app.config import settings

    url = make_url(settings.database_url)
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


async def export_chiripa_to_excel():
    print("=" * 80)
    print(f"📊 EXPORTANDO DATA DE CHIRIPA A EXCEL: {EXCEL_PATH}")
    print("=" * 80)

    # Asegurar que el directorio de destino existe
    os.makedirs(os.path.dirname(EXCEL_PATH), exist_ok=True)

    src_conn = await asyncpg.connect(_dsn())

    # Solo licitaciones VIGENTES. Un dump con cerradas es inútil: el matching
    # descarta todo lo que tenga `closing_at` en el pasado, así que el equipo
    # cargaría miles de filas para ver un dashboard vacío. Además las cerradas
    # ocupan cupo en las 50 candidatas que devuelve Qdrant, desplazando a las
    # que sí sirven.
    #
    # Los compradores y las partidas se acotan a las que quedan referenciadas,
    # para no arrastrar filas huérfanas.
    tables = {
        "region": "SELECT * FROM region",
        "tender_status": "SELECT * FROM tender_status",
        "buyer_institution": """
            SELECT DISTINCT b.* FROM buyer_institution b
            JOIN tender t ON t.buyer_rut = b.rut
            WHERE t.closing_at > now()
        """,
        "tender": "SELECT * FROM tender WHERE closing_at > now()",
        "tender_item": """
            SELECT ti.* FROM tender_item ti
            JOIN tender t ON t.id = ti.tender_id
            WHERE t.closing_at > now()
        """,
    }

    try:
        with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl") as writer:
            for table, consulta in tables.items():
                print(f"[EXPORT] Leyendo tabla '{table}'...")
                rows = await src_conn.fetch(consulta)
                data = [dict(r) for r in rows]
                df = pd.DataFrame(data)
                df.to_excel(writer, sheet_name=table, index=False)
                print(f"   ✓ {len(df)} filas escritas en hoja '{table}'.")
    finally:
        await src_conn.close()

    print("✅ Exportación a Excel completada con éxito.")


async def main() -> None:
    await export_chiripa_to_excel()
    print("\n[LISTO] Dataset actualizado. El equipo lo carga con:")
    print("  python tests/matching_evaluation/load_postgres_robust.py")
    print("  python tests/matching_evaluation/load_dataset.py")


if __name__ == "__main__":
    asyncio.run(main())
