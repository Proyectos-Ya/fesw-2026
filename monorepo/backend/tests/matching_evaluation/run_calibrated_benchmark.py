import asyncio
import json
import os
import sys
import time
from typing import Any
from uuid import UUID, uuid4

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from qdrant_client import AsyncQdrantClient
from sentence_transformers import SentenceTransformer

from app.application.services.text_builder import TextBuilder
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.infrastructure.services.bge_reranker_service import BgeRerankerService
from app.infrastructure.services.field_weighting_service import FieldWeightingService
from app.shared.regions import are_regions_matching
from tests.matching_evaluation.evaluate_matching_profiles import PROFILES
from tests.matching_evaluation.evaluate_named_vectors import (
    MultiVectorTextBuilder,
    cosine_similarity,
    load_all_tenders,
)

PG_HOST = "172.29.211.10"
PG_PORT = 5432
PG_USER = "proyectosya"
PG_PASSWORD = "proyectosya_secret"
PG_DB = "proyectosya_db"

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "tenders"

MODEL_NAME = "BAAI/bge-m3"


def scale_cosine(sim: float, baseline: float = 0.35, max_expected: float = 0.65) -> float:
    if sim <= baseline:
        return 0.0
    val = (sim - baseline) / (max_expected - baseline)
    return min(max(val, 0.0), 1.0)


async def evaluate_profile_calibrated(
    supplier: Supplier,
    tenders_dict: dict[UUID, Tender],
    qdrant_client: AsyncQdrantClient,
    embed_model: SentenceTransformer,
    reranker: BgeRerankerService,
    weighter: FieldWeightingService,
    text_builder: TextBuilder,
    top_results: int = 3,
) -> dict[str, Any]:
    start_time = time.perf_counter()

    # 1. Named Vectors del proveedor
    sup_ov, sup_it, sup_req = MultiVectorTextBuilder.build_supplier_texts(supplier)
    loop = asyncio.get_running_loop()
    sup_vectors = await loop.run_in_executor(
        None, lambda: embed_model.encode([sup_ov, sup_it, sup_req], normalize_embeddings=True)
    )
    v_sup_ov, v_sup_it, v_sup_req = sup_vectors[0], sup_vectors[1], sup_vectors[2]

    # 2. Búsqueda inicial en Qdrant
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
    for p in res.points:
        uid = UUID(str(p.id))
        t = tenders_dict.get(uid)
        if t and (not supplier.regions or are_regions_matching(t.region, supplier.regions)):
            valid_candidates.append(t)

    # 3. Named Vectors de candidatos
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

    # 4. Multi-Vector Score (45% ov + 45% it + 10% req) con escala calibrada
    candidates_with_scores = []
    sim_details = {}
    for i, t in enumerate(valid_candidates):
        s_ov = scale_cosine(cosine_similarity(v_sup_ov, t_ov_vecs[i]), 0.35, 0.65)
        s_it = scale_cosine(cosine_similarity(v_sup_it, t_it_vecs[i]), 0.35, 0.65)
        s_req = scale_cosine(cosine_similarity(v_sup_req, t_req_vecs[i]), 0.35, 0.65)

        multi_vec_score = (0.45 * s_ov) + (0.45 * s_it) + (0.10 * s_req)
        candidates_with_scores.append((t, multi_vec_score))
        sim_details[t.id] = {"s_ov": s_ov, "s_it": s_it, "s_req": s_req, "multi_vec": multi_vec_score}

    candidates_with_scores.sort(key=lambda x: x[1], reverse=True)
    top_candidates = candidates_with_scores[:20]

    # 5. Re-ranking con Cross-Encoder Platt Scaling calibrado (bias=1.5, T=1.5)
    rerank_pairs = [
        (t.id, text_builder.build_from_tender(tender=t, items=t.items))
        for t, _ in top_candidates
    ]
    rerank_start = time.perf_counter()
    reranked = await reranker.rerank(query_text=supplier_global_text, candidates=rerank_pairs, limit=20)
    rerank_duration = time.perf_counter() - rerank_start
    rerank_map = {uid: score for uid, score in reranked}

    # 6. Ponderación Híbrida (45% MultiVector + 25% Reranker + 15% Sector + 15% Keywords)
    candidates_for_weighting = [
        (t, rerank_map.get(t.id, 0.0))
        for t, _ in top_candidates
        if t.id in rerank_map
    ]
    final_weighted = weighter.calculate_scores(candidates_for_weighting, supplier)

    results_list = []
    for rank, (tid, final_score) in enumerate(final_weighted[:top_results], 1):
        t = tenders_dict[tid]
        rr_score = rerank_map.get(tid, 0.0)
        percentage = round(final_score * 100)

        all_text = f"{t.name} {t.description or ''} {' '.join([i.name for i in t.items])}"
        sec_m = any(s.lower() in all_text.lower() for s in (supplier.sectors or []))
        kw_m = any(kw.lower() in all_text.lower() for kw in (supplier.keywords or []))

        results_list.append({
            "rank": rank,
            "tender_id": str(t.id),
            "code": t.code,
            "name": t.name,
            "buyer": t.buyer_name,
            "region": t.region,
            "amount_clp": t.available_amount_clp,
            "final_percentage": f"{percentage}%",
            "final_score": round(final_score, 4),
            "reranker_score": round(rr_score, 4),
            "multi_vector_score": round(sim_details[tid]["multi_vec"], 4),
            "sector_match": sec_m,
            "keyword_match": kw_m,
        })

    total_duration = time.perf_counter() - start_time
    return {
        "supplier_name": supplier.legal_name,
        "sectors": supplier.sectors,
        "top_results": results_list,
        "total_duration_sec": round(total_duration, 3),
        "rerank_duration_sec": round(rerank_duration, 3),
    }


async def main():
    print("=" * 90, flush=True)
    print("🚀 EVALUACIÓN DEL MOTOR CON CALIBRACIÓN SIGMOIDE PLATT SCALING Y DENSIDAD LÉXICA", flush=True)
    print("=" * 90, flush=True)

    tenders_dict = await load_all_tenders()
    qdrant_client = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    loop = asyncio.get_running_loop()
    embed_model = await loop.run_in_executor(None, lambda: SentenceTransformer(MODEL_NAME))
    reranker = BgeRerankerService(temperature=1.5, bias=1.5)
    weighter = FieldWeightingService(
        reranker_weight=0.50,
        sector_weight=0.25,
        keyword_weight=0.25,
    )
    text_builder = TextBuilder()

    all_evaluations = []

    for idx, p_data in enumerate(PROFILES, 1):
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

        print(f"\n[{idx}/10] {supplier.legal_name} | Rubros: {', '.join(supplier.sectors or [])}", flush=True)
        res = await evaluate_profile_calibrated(
            supplier=supplier,
            tenders_dict=tenders_dict,
            qdrant_client=qdrant_client,
            embed_model=embed_model,
            reranker=reranker,
            weighter=weighter,
            text_builder=text_builder,
            top_results=3,
        )
        all_evaluations.append(res)

        print(f"  ⏱ Tiempo: {res['total_duration_sec']}s (Reranker: {res['rerank_duration_sec']}s)", flush=True)
        for r in res["top_results"]:
            flags = []
            if r["sector_match"]: flags.append("Sector")
            if r["keyword_match"]: flags.append("Keywords")
            flags_str = f" [Coincidencias: {', '.join(flags)}]" if flags else ""

            print(f"   #{r['rank']} [{r['code']}] {r['name'][:70]}...", flush=True)
            print(f"      🎯 Compatibilidad: {r['final_percentage']} (Score: {r['final_score']} | Reranker Calibrado: {r['reranker_score']}){flags_str}", flush=True)

    output_path = os.path.join(os.path.dirname(__file__), "matching_evaluation_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_evaluations, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Resultados actualizados guardados en: {output_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
