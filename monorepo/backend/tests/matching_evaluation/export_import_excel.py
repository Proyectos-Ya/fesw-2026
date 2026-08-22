import asyncio
import os
import sys
import time
import math
from typing import Any, Dict, List
import pandas as pd
import numpy as np

# Asegurar que el directorio raíz de backend esté en sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Forzar UTF-8 en Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import asyncpg
from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from app.application.services.text_builder import TextBuilder
from app.domain.entities.tender import Tender, TenderItem

# Cargar variables de entorno del monorepo
DOTENV_PATH = os.path.abspath(os.path.join(BASE_DIR, "../.env"))
load_dotenv(dotenv_path=DOTENV_PATH)

# ==========================================================
# CONFIGURACIÓN
# ==========================================================
SRC_HOST = "localhost"
SRC_PORT = 5432
SRC_USER = "postgres"
SRC_PASSWORD = "1234"
SRC_DB = "chiripa"

EXCEL_PATH = os.path.abspath(os.path.join(BASE_DIR, "../../project-data/chiripa_tenders.xlsx"))

# Destino Docker
DST_HOST = os.getenv("POSTGRES_HOST", "localhost")
DST_PORT = int(os.getenv("POSTGRES_PORT", 5432))
DST_USER = os.getenv("POSTGRES_USER", "proyectosya")
DST_PASSWORD = os.getenv("POSTGRES_PASSWORD", "proyectosya_secret")
DST_DB = os.getenv("POSTGRES_DB", "proyectosya_db")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_COLLECTION = "tenders"
QDRANT_VECTOR_NAME = "tender"

MODEL_NAME = "BAAI/bge-m3"
VECTOR_DIM = 1024
BATCH_SIZE = 32


def clean_val(val):
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    if isinstance(val, pd.Timestamp):
        return val.to_pydatetime()
    # String representation checks
    val_str = str(val).strip()
    if val_str in ("nan", "NaN", "NaT", "<NA>", "None"):
        return None
    return val


async def export_chiripa_to_excel():
    print("=" * 80)
    print(f"📊 EXPORTANDO DATA DE CHIRIPA A EXCEL: {EXCEL_PATH}")
    print("=" * 80)
    
    # Asegurar que el directorio de destino existe
    os.makedirs(os.path.dirname(EXCEL_PATH), exist_ok=True)

    # Conectar usando asyncpg
    src_conn = await asyncpg.connect(
        database=SRC_DB, user=SRC_USER, password=SRC_PASSWORD, host=SRC_HOST, port=SRC_PORT
    )

    tables = ["region", "tender_status", "buyer_institution", "tender", "tender_item"]
    
    try:
        with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl") as writer:
            for table in tables:
                print(f"[EXPORT] Leyendo tabla '{table}' desde chiripa...")
                rows = await src_conn.fetch(f"SELECT * FROM {table};")
                data = [dict(r) for r in rows]
                df = pd.DataFrame(data)
                df.to_excel(writer, sheet_name=table, index=False)
                print(f"   ✓ {len(df)} filas escritas en hoja '{table}'.")
    finally:
        await src_conn.close()

    print("✅ Exportación a Excel completada con éxito.")


async def import_excel_to_docker():
    print("\n" + "=" * 80)
    print(f"📥 IMPORTANDO DATA DESDE EXCEL A DOCKER POSTGRES ({DST_DB})")
    print("=" * 80)

    # Conectar a base de datos destino en Docker
    print(f"[DST] Conectando a {DST_DB} en {DST_HOST}:{DST_PORT}...")
    try:
        dst_conn = await asyncpg.connect(
            database=DST_DB, user=DST_USER, password=DST_PASSWORD, host=DST_HOST, port=DST_PORT
        )
    except Exception as e:
        print(f"❌ Error al conectar a la base de datos de Docker ({DST_DB}): {e}")
        return False

    try:
        # Cargar hojas de Excel usando pandas
        excel_file = pd.ExcelFile(EXCEL_PATH)

        # Helper para insertar dataframes con tipos correctos
        async def insert_df(table_name: str, query: str, string_columns: List[int] = None):
            df = excel_file.parse(table_name)
            print(f"[IMPORT] Insertando filas en la tabla '{table_name}'...")
            
            success_count = 0
            fail_count = 0
            for idx, row in df.iterrows():
                values = [clean_val(val) for val in row]
                if string_columns:
                    for col_idx in string_columns:
                        if col_idx < len(values) and values[col_idx] is not None:
                            values[col_idx] = str(values[col_idx])
                try:
                    await dst_conn.execute(query, *values)
                    success_count += 1
                except Exception as e:
                    # Mostrar error real si no es una violación de clave única
                    if "unique constraint" not in str(e).lower() and "duplicate key" not in str(e).lower():
                        print(f"      [ERR] Fila {idx}: {e}")
                    fail_count += 1
            print(f"   ✓ Tabla '{table_name}': {success_count} insertados exitosamente, {fail_count} omitidos/duplicados.")

        # 1. region
        await insert_df(
            "region",
            "INSERT INTO region (id, name) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING;",
            string_columns=[1]
        )

        # 2. tender_status
        await insert_df(
            "tender_status",
            "INSERT INTO tender_status (id, code, name) VALUES ($1, $2, $3) ON CONFLICT (id) DO NOTHING;",
            string_columns=[1, 2]
        )

        # 3. buyer_institution
        await insert_df(
            "buyer_institution",
            """
            INSERT INTO buyer_institution (rut, name, region_id, created_at, updated_at) 
            VALUES ($1, $2, $3, $4, $5) 
            ON CONFLICT (rut) DO NOTHING;
            """,
            string_columns=[0, 1]
        )

        # 4. tender
        await insert_df(
            "tender",
            """
            INSERT INTO tender (id, code, name, description, status_id, published_at, closing_at, 
                                last_change_at, buyer_rut, buyer_unit, province, available_amount_clp, 
                                created_at, updated_at) 
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14) 
            ON CONFLICT (id) DO NOTHING;
            """,
            string_columns=[0, 1, 2, 3, 8, 9, 10]
        )

        # 5. tender_item
        await insert_df(
            "tender_item",
            """
            INSERT INTO tender_item (id, tender_id, product_code, name, description, quantity, unit_of_measure) 
            VALUES ($1, $2, $3, $4, $5, $6, $7) 
            ON CONFLICT (id) DO NOTHING;
            """,
            string_columns=[0, 1, 2, 3, 4, 6]
        )

    finally:
        await dst_conn.close()

    print("✅ Importación a Postgres completada con éxito.")
    return True


async def generate_qdrant_embeddings():
    print("\n" + "=" * 80)
    print(f"🎯 GENERANDO E INDEXANDO EMBEDDINGS EN QDRANT ({QDRANT_COLLECTION})")
    print("=" * 80)

    dst_conn = await asyncpg.connect(
        database=DST_DB, user=DST_USER, password=DST_PASSWORD, host=DST_HOST, port=DST_PORT
    )
    qdrant_client = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    # 1. Asegurar la colección en Qdrant con vector 'tender'
    result = await qdrant_client.get_collections()
    existing_collections = {c.name for c in result.collections}

    if QDRANT_COLLECTION in existing_collections:
        await qdrant_client.delete_collection(collection_name=QDRANT_COLLECTION)

    await qdrant_client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config={
            QDRANT_VECTOR_NAME: VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)
        },
    )

    # 2. Cargar modelo
    loop = asyncio.get_running_loop()
    model = await loop.run_in_executor(None, lambda: SentenceTransformer(MODEL_NAME))

    # 3. Obtener licitaciones
    tenders_rows = await dst_conn.fetch(
        """
        SELECT t.id, t.code, t.name, t.description, t.status_id, t.province, t.available_amount_clp,
               b.name AS buyer_name, r.name AS region_name
        FROM tender t
        LEFT JOIN buyer_institution b ON t.buyer_rut = b.rut
        LEFT JOIN region r ON b.region_id = r.id;
        """
    )

    tenders_dict = {}
    for r in tenders_rows:
        t_id = r["id"]
        tenders_dict[t_id] = {
            "id": t_id,
            "code": r["code"],
            "name": r["name"],
            "description": r["description"],
            "province": r["province"],
            "region": r["region_name"],
            "buyer_name": r["buyer_name"],
            "available_amount_clp": float(r["available_amount_clp"]) if r["available_amount_clp"] is not None else None,
            "items": [],
        }

    items_rows = await dst_conn.fetch(
        "SELECT id, tender_id, name, description, quantity, unit_of_measure FROM tender_item;"
    )
    for it in items_rows:
        t_id = it["tender_id"]
        if t_id in tenders_dict:
            tenders_dict[t_id]["items"].append(
                TenderItem(
                    id=it["id"],
                    tender_id=t_id,
                    product_code="",
                    name=it["name"] or "",
                    description=it["description"],
                    quantity=float(it["quantity"]) if it["quantity"] is not None else 1.0,
                    unit_of_measure=it["unit_of_measure"] or "UN",
                )
            )

    tenders_list = list(tenders_dict.values())
    total = len(tenders_list)
    text_builder = TextBuilder()

    # 4. Generar e indexar en lotes
    print(f"[EMBEDDINGS] Indexando {total} licitaciones en lotes de {BATCH_SIZE}...")

    for i in range(0, total, BATCH_SIZE):
        batch = tenders_list[i : i + BATCH_SIZE]
        texts = []
        for t in batch:
            tender_obj = Tender(
                id=t["id"],
                code=t["code"],
                name=t["name"],
                description=t["description"],
                status_id=1,
                status_code="publicada",
                published_at=time.time(),  # type: ignore
                closing_at=time.time(),  # type: ignore
                last_change_at=time.time(),  # type: ignore
                buyer_rut="1-1",
                buyer_unit="TI",
                items=t["items"],
            )
            texts.append(text_builder.build_from_tender(tender=tender_obj, items=t["items"]))

        embeddings = await loop.run_in_executor(
            None, lambda: model.encode(texts, normalize_embeddings=True).tolist()
        )

        points = []
        for idx, t in enumerate(batch):
            point = PointStruct(
                id=str(t["id"]),
                vector={QDRANT_VECTOR_NAME: embeddings[idx]},
                payload={
                    "code": t["code"],
                    "region": t["region"],
                    "province": t["province"],
                    "available_amount_clp": t["available_amount_clp"],
                    "status_code": "publicada",
                },
            )
            points.append(point)

        await qdrant_client.upsert(collection_name=QDRANT_COLLECTION, points=points)
        print(f"   [OK] Lote {i + 1} - {min(i + len(batch), total)} / {total} indexado.")

    await dst_conn.close()
    await qdrant_client.close()
    print("✅ Indexación de embeddings completada.")


async def main():
    await export_chiripa_to_excel()
    success = await import_excel_to_docker()
    if success:
        await generate_qdrant_embeddings()


if __name__ == "__main__":
    asyncio.run(main())
