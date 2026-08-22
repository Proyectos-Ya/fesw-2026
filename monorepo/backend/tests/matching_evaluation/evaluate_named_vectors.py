import asyncio
import os
import sys
import time
from typing import Any, Dict, List, Tuple
from uuid import UUID, uuid4
import numpy as np
import asyncpg

# Asegurar sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Forzar UTF-8 en Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from qdrant_client import AsyncQdrantClient
from sentence_transformers import SentenceTransformer
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender, TenderItem
from app.infrastructure.services.bge_reranker_service import BgeRerankerService
from app.infrastructure.services.field_weighting_service import FieldWeightingService
from app.application.services.text_builder import TextBuilder
from app.shared.region_normalizer import are_regions_matching
from tests.matching_evaluation.evaluate_matching_profiles import PROFILES

PG_HOST = "172.29.211.10"
PG_PORT = 5432
PG_USER = "proyectosya"
PG_PASSWORD = "proyectosya_secret"
PG_DB = "proyectosya_db"

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "tenders"

MODEL_NAME = "BAAI/bge-m3"


class MultiVectorTextBuilder:
    """Construye las representaciones semánticas independientes para los 3 Named Vectors."""

    @staticmethod
    def build_tender_texts(tender: Tender) -> Tuple[str, str, str]:
        # 1. Overview: Nombre/Título + Descripción general del objeto
        overview = f"{tender.name}. {tender.description or ''}".strip()
        
        # 2. Items: Detalle de productos, partidas y cantidades
        if tender.items:
            items_str = ". ".join([
                f"{i.name}" + (f" ({i.description})" if i.description and i.description != i.name else "")
                for i in tender.items
            ])
            items = f"Partidas e insumos requeridos: {items_str}"
        else:
            items = f"Requerimiento de suministro y servicio: {tender.name}"

        # 3. Requirements: Condiciones del comprador, unidad técnica y requisitos
        req_parts = []
        if tender.buyer_name:
            req_parts.append(f"Institución compradora: {tender.buyer_name}")
        if tender.buyer_unit:
            req_parts.append(f"Unidad técnica requirente: {tender.buyer_unit}")
        if tender.description:
            req_parts.append(f"Términos de referencia y requerimientos: {tender.description}")
        requirements = ". ".join(req_parts) if req_parts else f"Requisitos de contratación para {tender.name}"

        return overview, items, requirements

    @staticmethod
    def build_supplier_texts(supplier: Supplier) -> Tuple[str, str, str]:
        # 1. Overview: Rubros principales y descripción de la empresa
        sectors_str = ", ".join(supplier.sectors or [])
        overview = f"Proveedor del rubro {sectors_str}. {supplier.description or supplier.legal_name}".strip()

        # 2. Items: Capacidades, especialidades, partidas y palabras clave
        kw_str = ", ".join(supplier.keywords or [])
        items = f"Catálogo de productos, servicios y partidas técnicas: {kw_str}".strip()

        # 3. Requirements: Certificaciones técnicas, registros y experiencia
        certs_str = ", ".join(supplier.certifications or []) if supplier.certifications else "Sin certificaciones especiales requeridas"
        years = supplier.years_experience or 5
        requirements = f"Certificaciones y registros: {certs_str}. Experiencia técnica en el rubro: {years} años.".strip()

        return overview, items, requirements


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    dot = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


async def load_all_tenders() -> Dict[UUID, Tender]:
    conn = await asyncpg.connect(database=PG_DB, user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT)
    rows = await conn.fetch("""
        SELECT t.id AS tender_id, t.code AS tender_code, t.name AS tender_name, t.description AS tender_description,
               t.status_id, t.published_at, t.closing_at, t.last_change_at, t.buyer_rut, t.buyer_unit,
               t.province, t.available_amount_clp, t.created_at, t.updated_at,
               b.name AS buyer_name, r.name AS region_name,
               ti.id AS item_id, ti.product_code AS item_product_code, ti.name AS item_name,
               ti.description AS item_description, ti.quantity AS item_quantity, ti.unit_of_measure AS item_unit_of_measure
        FROM tender t
        LEFT JOIN buyer_institution b ON t.buyer_rut = b.rut
        LEFT JOIN region r ON b.region_id = r.id
        LEFT JOIN tender_item ti ON t.id = ti.tender_id
        ORDER BY t.created_at DESC;
    """)
    await conn.close()

    tenders_dict = {}
    for row in rows:
        t_id = row["tender_id"]
        if t_id not in tenders_dict:
            tenders_dict[t_id] = Tender(
                id=t_id,
                code=row["tender_code"] or str(t_id),
                name=row["tender_name"] or "",
                description=row["tender_description"],
                status_id=row["status_id"] or 1,
                status_code="publicada",
                published_at=row["published_at"] or row["created_at"],
                closing_at=row["closing_at"] or row["created_at"],
                last_change_at=row["last_change_at"] or row["created_at"],
                buyer_rut=row["buyer_rut"] or "60.000.000-1",
                buyer_name=row["buyer_name"],
                buyer_unit=row["buyer_unit"] or "",
                province=row["province"],
                region=row["region_name"],
                available_amount_clp=float(row["available_amount_clp"]) if row["available_amount_clp"] is not None else None,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                items=[],
            )
        if row["item_id"] is not None:
            tenders_dict[t_id].items.append(
                TenderItem(
                    id=row["item_id"],
                    tender_id=t_id,
                    product_code=row["item_product_code"] or "",
                    name=row["item_name"] or "",
                    description=row["item_description"],
                    quantity=float(row["item_quantity"]) if row["item_quantity"] is not None else 1.0,
                    unit_of_measure=row["item_unit_of_measure"] or "UN",
                )
            )
    return tenders_dict


async def evaluate_with_named_vectors(
    supplier: Supplier,
    tenders_dict: Dict[UUID, Tender],
    qdrant_client: AsyncQdrantClient,
    embed_model: SentenceTransformer,
    reranker: BgeRerankerService,
    text_builder: TextBuilder,
    w_overview: float = 0.40,
    w_items: float = 0.40,
    w_requirements: float = 0.20,
    top_k: int = 10,
) -> Dict[str, Any]:
    # 1. Construir los 3 textos del proveedor
    sup_ov, sup_it, sup_req = MultiVectorTextBuilder.build_supplier_texts(supplier)

    # 2. Generar los 3 Named Vectors del proveedor
    loop = asyncio.get_running_loop()
    sup_vectors = await loop.run_in_executor(
        None, lambda: embed_model.encode([sup_ov, sup_it, sup_req], normalize_embeddings=True)
    )
    v_sup_ov, v_sup_it, v_sup_req = sup_vectors[0], sup_vectors[1], sup_vectors[2]

    # 3. Búsqueda vectorial inicial en Qdrant para obtener el conjunto de candidatos
    supplier_global_text = text_builder.build_from_supplier(supplier)
    query_vector = (await loop.run_in_executor(
        None, lambda: embed_model.encode([supplier_global_text], normalize_embeddings=True)
    ))[0].tolist()

    res = await qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        using="tender",
        limit=50,
    )

    valid_candidates = []
    hydrated_tenders = {}
    for p in res.points:
        uid = UUID(str(p.id))
        t = tenders_dict.get(uid)
        if t:
            if supplier.regions and not are_regions_matching(t.region or t.province, supplier.regions):
                continue
            hydrated_tenders[uid] = t
            valid_candidates.append(t)

    # 4. Generar los 3 Named Vectors para los candidatos filtrados (40 candidatos)
    t_overviews = []
    t_items = []
    t_requirements = []
    for t in valid_candidates:
        ov, it, req = MultiVectorTextBuilder.build_tender_texts(t)
        t_overviews.append(ov)
        t_items.append(it)
        t_requirements.append(req)

    t_ov_vecs = await loop.run_in_executor(None, lambda: embed_model.encode(t_overviews, normalize_embeddings=True, batch_size=32))
    t_it_vecs = await loop.run_in_executor(None, lambda: embed_model.encode(t_items, normalize_embeddings=True, batch_size=32))
    t_req_vecs = await loop.run_in_executor(None, lambda: embed_model.encode(t_requirements, normalize_embeddings=True, batch_size=32))

    # 5. Calcular Similitud Multi-Vector: w1*requirements + w2*overview + w3*items
    candidates_with_scores = []
    sim_details = {}
    for i, t in enumerate(valid_candidates):
        s_ov = cosine_similarity(v_sup_ov, t_ov_vecs[i])
        s_it = cosine_similarity(v_sup_it, t_it_vecs[i])
        s_req = cosine_similarity(v_sup_req, t_req_vecs[i])

        # Ponderación Multi-Vector
        multi_vec_score = (w_requirements * s_req) + (w_overview * s_ov) + (w_items * s_it)
        candidates_with_scores.append((t, multi_vec_score))
        sim_details[t.id] = {"s_ov": s_ov, "s_it": s_it, "s_req": s_req, "multi_vec": multi_vec_score}

    # Tomar Top 20 para Re-ranking con Cross-Encoder
    candidates_with_scores.sort(key=lambda x: x[1], reverse=True)
    top_candidates = candidates_with_scores[:20]

    # 6. Re-ranking con Cross-Encoder
    rerank_pairs = [
        (t.id, text_builder.build_from_tender(tender=t, items=t.items))
        for t, _ in top_candidates
    ]
    reranked = await reranker.rerank(query_text=supplier_global_text, candidates=rerank_pairs, limit=20)
    rerank_map = {uid: score for uid, score in reranked}

    # 7. FÓRMULA COMBINADA INTEGRADA:
    # 40% Multi-Vector (w1*req + w2*ov + w3*items) + 40% Reranker + 10% Sector Match + 10% Keywords Match
    final_scored = []
    for t, m_score in top_candidates:
        r_score = rerank_map.get(t.id, 0.0)
        
        # Evaluar coincidencias léxicas
        tender_overview = f"{t.name} {t.description or ''}"
        items_text = " ".join([f"{it.name} {it.description or ''}" for it in t.items])
        all_text = f"{tender_overview} {items_text}"

        sector_matched = any(s.lower() in all_text.lower() for s in (supplier.sectors or []))
        keyword_matched = any(kw.lower() in all_text.lower() for kw in (supplier.keywords or []))

        # Combinación híbrida integrada
        hybrid_score = (
            0.40 * m_score +
            0.40 * r_score +
            (0.10 if sector_matched else 0.0) +
            (0.10 if keyword_matched else 0.0)
        )
        hybrid_score = min(hybrid_score, 1.0)
        final_scored.append((t, hybrid_score, r_score, sim_details[t.id], sector_matched, keyword_matched))

    final_scored.sort(key=lambda x: x[1], reverse=True)

    results = []
    for rank, (t, final_score, rr_score, s_dict, sec_m, kw_m) in enumerate(final_scored[:top_k], 1):
        percentage = round(final_score * 100)
        results.append({
            "rank": rank,
            "code": t.code,
            "name": t.name,
            "buyer": t.buyer_name,
            "region": t.region or t.province,
            "amount_clp": t.available_amount_clp,
            "final_percentage": f"{percentage}%",
            "final_score": round(final_score, 4),
            "multi_vec_score": round(s_dict["multi_vec"], 4),
            "s_overview": round(s_dict["s_ov"], 4),
            "s_items": round(s_dict["s_it"], 4),
            "s_requirements": round(s_dict["s_req"], 4),
            "reranker_score": round(rr_score, 4),
            "sector_match": sec_m,
            "keyword_match": kw_m,
        })

    return {
        "supplier_name": supplier.legal_name,
        "results": results,
    }


async def main():
    print("=" * 100, flush=True)
    print("🎯 EVALUACIÓN DE PONDERACIÓN CON NAMED VECTORS (w1*req + w2*overview + w3*items)", flush=True)
    print("=" * 100, flush=True)

    tenders_dict = await load_all_tenders()
    print(f"[POSTGRES] {len(tenders_dict)} licitaciones cargadas en memoria.", flush=True)

    print("[MODELS] Inicializando SentenceTransformer BGE-M3 y Reranker ONNX...", flush=True)
    qdrant_client = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    loop = asyncio.get_running_loop()
    embed_model = await loop.run_in_executor(None, lambda: SentenceTransformer(MODEL_NAME))
    reranker = BgeRerankerService(temperature=1.5)
    text_builder = TextBuilder()

    # Perfil Construcción
    p_data = PROFILES[0]
    supplier = Supplier(
        id=uuid4(),
        rut=p_data["rut"],
        legal_name=p_data["legal_name"],
        trade_name=p_data.get("trade_name"),
        description=p_data.get("description"),
        regions=p_data.get("regions"),
        sectors=p_data.get("sectors"),
        certifications=p_data.get("certificaciones"),
        keywords=p_data.get("keywords"),
    )

    print(f"\n[PERFIL] {supplier.legal_name}", flush=True)
    print("Ponderaciones Named Vectors: w_overview=0.40, w_items=0.40, w_requirements=0.20", flush=True)
    
    res = await evaluate_with_named_vectors(
        supplier=supplier,
        tenders_dict=tenders_dict,
        qdrant_client=qdrant_client,
        embed_model=embed_model,
        reranker=reranker,
        text_builder=text_builder,
        w_overview=0.40,
        w_items=0.40,
        w_requirements=0.20,
        top_k=10,
    )

    print("\n" + "=" * 100, flush=True)
    print("🏆 RESULTADOS TOP 10 CON PONDERACIÓN MULTI-VECTOR + RERANKER HÍBRIDO", flush=True)
    print("=" * 100, flush=True)

    for r in res["results"]:
        amount_str = f"${r['amount_clp']:,.0f} CLP" if r["amount_clp"] else "N/A"
        flags = []
        if r["sector_match"]: flags.append("Sector")
        if r["keyword_match"]: flags.append("Keywords")
        flags_str = ", ".join(flags) if flags else "Semántico puro"

        print(f"#{r['rank']:02d} | [{r['code']}] | Compatibilidad: {r['final_percentage']} (Final Score: {r['final_score']})", flush=True)
        print(f"     Nombre: {r['name'][:80]}", flush=True)
        print(f"     📊 Multi-Vector: {r['multi_vec_score']} [Overview (40%): {r['s_overview']} | Items (40%): {r['s_items']} | Requisitos (20%): {r['s_requirements']}]", flush=True)
        print(f"     🔍 Reranker: {r['reranker_score']} | Coincidencias: [{flags_str}] | Monto: {amount_str}", flush=True)
        print("-" * 100, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
