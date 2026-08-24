import asyncio
import os
import sys
from typing import Any

# Forzar codificación UTF-8 en stdout/stderr en entornos Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import asyncpg
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

# ==========================================================
# 1. CONFIGURACIÓN (PostgreSQL 'chiripa' y Qdrant)
# ==========================================================
PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = int(os.getenv("POSTGRES_PORT", 5432))
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "1234")
PG_DB = os.getenv("POSTGRES_DB", "chiripa")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
TEST_COLLECTION_NAME = "chiripa_tenders_named_vectors"

MODEL_NAME = "BAAI/bge-m3"
VECTOR_DIM = 1024
BATCH_SIZE = 32


# ==========================================================
# 2. FUNCIONES DE TEXTO (PARTICIONAMIENTO SEMÁNTICO)
# ==========================================================
def build_overview_text(name: str, description: str | None) -> str:
    """Construye el texto para el vector 'overview'."""
    parts = [name.strip()] if name else []
    if description and description.strip():
        parts.append(description.strip())
    return ". ".join(parts) if parts else "Licitacion sin descripcion."


def build_items_text(items: list[dict[str, Any]]) -> str:
    """Construye el texto agregado para el vector 'items'."""
    if not items:
        return "Sin detalle especifico de items."

    formatted_items = []
    for it in items:
        name = it.get("name", "").strip()
        desc = it.get("description")
        qty = it.get("quantity", 0)
        unit = it.get("unit_of_measure", "UN")

        detail = f"{name}"
        if desc and str(desc).strip():
            detail += f" ({str(desc).strip()})"
        if qty is not None:
            detail += f" [Cant: {qty} {unit}]"
        formatted_items.append(detail)

    return "; ".join(formatted_items)


# ==========================================================
# 3. EXTRACCIÓN SOLO-LECTURA (SELECT) DESDE POSTGRESQL
# ==========================================================
async def fetch_tenders_from_db() -> list[dict[str, Any]]:
    """Extrae las licitaciones y sus items de 'chiripa' garantizando SOLO operaciones SELECT."""
    print(
        f"[POSTGRES] Conectando en modo SOLO LECTURA a PostgreSQL ({PG_DB}@{PG_HOST}:{PG_PORT})...",
        flush=True,
    )

    conn = await asyncpg.connect(
        database=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=PG_PORT,
    )

    tenders_dict: dict[str, dict[str, Any]] = {}

    try:
        # 1. Identificar tablas existentes en la BD con SELECT
        tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
        table_records = await conn.fetch(tables_query)
        existing_tables = {row["table_name"] for row in table_records}
        print(
            f"[POSTGRES] Tablas encontradas en '{PG_DB}': {sorted(list(existing_tables))}",
            flush=True,
        )

        # 2. Consultar según la estructura de tablas disponible
        if "tender" in existing_tables:
            print(
                "[POSTGRES] Extrayendo desde tablas 'tender' y 'tender_item'...",
                flush=True,
            )
            has_items = "tender_item" in existing_tables
            has_buyer = "buyer_institution" in existing_tables
            has_region = "region" in existing_tables

            select_sql = """
                SELECT 
                    t.id AS tender_id,
                    t.code AS tender_code,
                    t.name AS tender_name,
                    t.description AS tender_description,
                    t.status_id,
                    t.available_amount_clp,
            """
            if has_buyer:
                select_sql += ", b.name AS buyer_name"
            else:
                select_sql += ", NULL AS buyer_name"

            if has_region and has_buyer:
                select_sql += ", r.name AS region_name"
            else:
                select_sql += ", NULL AS region_name"

            if has_items:
                select_sql += """,
                    ti.id AS item_id,
                    ti.product_code AS item_product_code,
                    ti.name AS item_name,
                    ti.description AS item_description,
                    ti.quantity AS item_quantity,
                    ti.unit_of_measure AS item_unit_of_measure
                """
            else:
                select_sql += """,
                    NULL AS item_id,
                    NULL AS item_product_code,
                    NULL AS item_name,
                    NULL AS item_description,
                    NULL AS item_quantity,
                    NULL AS item_unit_of_measure
                """

            select_sql += " FROM tender t "
            if has_buyer:
                select_sql += " LEFT JOIN buyer_institution b ON t.buyer_rut = b.rut "
            if has_region and has_buyer:
                select_sql += " LEFT JOIN region r ON b.region_id = r.id "
            if has_items:
                select_sql += " LEFT JOIN tender_item ti ON t.id = ti.tender_id "
            select_sql += " ORDER BY t.created_at DESC;"

            rows = await conn.fetch(select_sql)

            for row in rows:
                t_id = str(row["tender_id"])
                if t_id not in tenders_dict:
                    tenders_dict[t_id] = {
                        "id": t_id,
                        "code": row["tender_code"] or t_id,
                        "name": row["tender_name"] or "",
                        "description": row["tender_description"],
                        "status_id": row["status_id"],
                        "available_amount_clp": float(row["available_amount_clp"])
                        if row["available_amount_clp"] is not None
                        else None,
                        "buyer_name": row["buyer_name"],
                        "region": row["region_name"],
                        "items": [],
                    }

                if row["item_id"] is not None:
                    tenders_dict[t_id]["items"].append(
                        {
                            "id": str(row["item_id"]),
                            "product_code": row["item_product_code"] or "",
                            "name": row["item_name"] or "",
                            "description": row["item_description"],
                            "quantity": float(row["item_quantity"])
                            if row["item_quantity"] is not None
                            else 1.0,
                            "unit_of_measure": row["item_unit_of_measure"] or "UN",
                        }
                    )

        elif "licitacion" in existing_tables:
            print("[POSTGRES] Extrayendo desde tabla 'licitacion'...", flush=True)
            rows = await conn.fetch("""
                SELECT 
                    id, 
                    codigo_externo, 
                    nombre, 
                    descripcion, 
                    organismo_nombre, 
                    region, 
                    comuna, 
                    monto_estimado
                FROM licitacion;
            """)
            for row in rows:
                t_id = str(row["id"])
                tenders_dict[t_id] = {
                    "id": t_id,
                    "code": row["codigo_externo"] or t_id,
                    "name": row["nombre"] or "",
                    "description": row["descripcion"],
                    "status_id": 1,
                    "available_amount_clp": float(row["monto_estimado"])
                    if row["monto_estimado"] is not None
                    else None,
                    "buyer_name": row["organismo_nombre"],
                    "region": row["region"],
                    "items": [],
                }
    finally:
        await conn.close()

    result = list(tenders_dict.values())
    print(
        f"[POSTGRES] Se extrajeron exitosamente {len(result)} licitaciones de PostgreSQL (Base de datos: {PG_DB}).",
        flush=True,
    )
    return result


# ==========================================================
# 4. GESTIÓN DE QDRANT Y CARGA CON NAMED VECTORS
# ==========================================================
async def setup_qdrant_collection(client: AsyncQdrantClient):
    """Crea la colección con vectores nombrados 'overview' e 'items'."""
    print(
        f"[QDRANT] Preparando coleccion '{TEST_COLLECTION_NAME}' en Qdrant ({QDRANT_HOST}:{QDRANT_PORT})...",
        flush=True,
    )

    result = await client.get_collections()
    collections = [c.name for c in result.collections]
    if TEST_COLLECTION_NAME in collections:
        print(f"[QDRANT] Recreando coleccion '{TEST_COLLECTION_NAME}'...", flush=True)
        await client.delete_collection(collection_name=TEST_COLLECTION_NAME)

    await client.create_collection(
        collection_name=TEST_COLLECTION_NAME,
        vectors_config={
            "overview": VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
            "items": VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        },
    )
    print(
        f"[QDRANT] Coleccion '{TEST_COLLECTION_NAME}' creada con vectores nombrados: 'overview' e 'items' ({VECTOR_DIM} dim).",
        flush=True,
    )


async def generate_and_upload_named_vectors(
    tenders: list[dict[str, Any]],
    client: AsyncQdrantClient,
    model: SentenceTransformer,
):
    """Genera embeddings por aspecto semántico y realiza el upsert a Qdrant."""
    total = len(tenders)
    print(
        f"[EMBEDDINGS] Generando Named Vectors para {total} licitaciones en lotes de {BATCH_SIZE}...",
        flush=True,
    )
    loop = asyncio.get_running_loop()

    for i in range(0, total, BATCH_SIZE):
        batch = tenders[i : i + BATCH_SIZE]

        overview_texts = [
            build_overview_text(t["name"], t["description"]) for t in batch
        ]
        items_texts = [build_items_text(t["items"]) for t in batch]

        # Generar embeddings de ambos aspectos en ejecutor de hilo
        overview_vectors = await loop.run_in_executor(
            None,
            lambda: model.encode(overview_texts, normalize_embeddings=True).tolist(),
        )
        items_vectors = await loop.run_in_executor(
            None, lambda: model.encode(items_texts, normalize_embeddings=True).tolist()
        )

        points: list[PointStruct] = []
        for idx, t in enumerate(batch):
            point = PointStruct(
                id=t["id"],
                vector={
                    "overview": overview_vectors[idx],
                    "items": items_vectors[idx],
                },
                payload={
                    "code": t["code"],
                    "name": t["name"],
                    "buyer_name": t["buyer_name"],
                    "region": t["region"],
                    "available_amount_clp": t["available_amount_clp"],
                    "items_count": len(t["items"]),
                },
            )
            points.append(point)

        await client.upsert(collection_name=TEST_COLLECTION_NAME, points=points)
        print(
            f"   [OK] Lote {i + 1} - {min(i + len(batch), total)} / {total} cargado en Qdrant.",
            flush=True,
        )

    print(
        f"[QDRANT] Carga finalizada: {total} licitaciones indexadas con Named Vectors en Qdrant.",
        flush=True,
    )


# ==========================================================
# 5. DEMOSTRACIÓN DE BÚSQUEDA PONDERADA
# ==========================================================
async def run_search_demo(client: AsyncQdrantClient, model: SentenceTransformer):
    """Demuestra una búsqueda multi-vector con ponderación en la colección recién creada."""
    print("\n" + "=" * 70, flush=True)
    print(
        "[SEARCH] PRUEBA DE BUSQUEDA MULTI-VECTOR PONDERADA (70% Items / 30% Overview)",
        flush=True,
    )
    print("=" * 70, flush=True)

    query_overview = "Servicios generales de mantencion, aseo y obras menores"
    query_items = "Articulos de limpieza, desinfectante, bolsas de basura y mopas"

    w_overview = 0.30
    w_items = 0.70

    loop = asyncio.get_running_loop()
    v_overview = (
        await loop.run_in_executor(
            None, lambda: model.encode([query_overview], normalize_embeddings=True)
        )
    )[0].tolist()
    v_items = (
        await loop.run_in_executor(
            None, lambda: model.encode([query_items], normalize_embeddings=True)
        )
    )[0].tolist()

    res_overview = await client.query_points(
        collection_name=TEST_COLLECTION_NAME,
        query=v_overview,
        using="overview",
        limit=5,
    )

    res_items = await client.query_points(
        collection_name=TEST_COLLECTION_NAME,
        query=v_items,
        using="items",
        limit=5,
    )

    combined_scores: dict[str, dict[str, Any]] = {}
    for p in res_overview.points:
        pid = str(p.id)
        combined_scores[pid] = {
            "score": float(p.score) * w_overview,
            "payload": p.payload,
        }

    for p in res_items.points:
        pid = str(p.id)
        if pid in combined_scores:
            combined_scores[pid]["score"] += float(p.score) * w_items
        else:
            combined_scores[pid] = {
                "score": float(p.score) * w_items,
                "payload": p.payload,
            }

    ranking = sorted(combined_scores.items(), key=lambda x: x[1]["score"], reverse=True)

    print("[SEARCH] Top 3 Resultados Obtenidos:", flush=True)
    for rank, (tid, data) in enumerate(ranking[:3], 1):
        payload = data["payload"]
        print(f"  {rank}. [{payload.get('code')}] {payload.get('name')}", flush=True)
        print(
            f"     Score Final: {data['score']:.4f} | Organismo: {payload.get('buyer_name')} | Items: {payload.get('items_count')}",
            flush=True,
        )


# ==========================================================
# 6. ENTRADA PRINCIPAL
# ==========================================================
async def main():
    print("=" * 70, flush=True)
    print(
        "[INIT] INICIANDO SINCRONIZACION DE LICITACIONES A QDRANT (NAMED VECTORS)",
        flush=True,
    )
    print("=" * 70, flush=True)

    # 1. Extraer licitaciones (SOLO SELECT)
    tenders = await fetch_tenders_from_db()
    if not tenders:
        print(
            "[WARN] No se encontraron licitaciones en la base de datos 'chiripa'.",
            flush=True,
        )
        return

    # 2. Conectar a Qdrant y preparar colección
    qdrant_client = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    await setup_qdrant_collection(qdrant_client)

    # 3. Cargar modelo
    print(f"[MODEL] Cargando modelo de embeddings '{MODEL_NAME}'...", flush=True)
    loop = asyncio.get_running_loop()
    model = await loop.run_in_executor(None, lambda: SentenceTransformer(MODEL_NAME))

    # 4. Generar y subir Named Vectors
    await generate_and_upload_named_vectors(tenders, qdrant_client, model)

    # 5. Ejecutar test de búsqueda
    await run_search_demo(qdrant_client, model)


if __name__ == "__main__":
    asyncio.run(main())
