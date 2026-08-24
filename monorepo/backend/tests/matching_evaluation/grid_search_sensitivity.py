import asyncio
import os
import sys
from uuid import UUID, uuid4

import numpy as np

# Asegurar sys.path
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
from app.infrastructure.services.bge_reranker_service import BgeRerankerService
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


def scale_cosine(
    sim: float, baseline: float = 0.35, max_expected: float = 0.65
) -> float:
    """Escala linealmente la similitud coseno densa para proyectar [baseline, max_expected] -> [0.0, 1.0]."""
    if sim <= baseline:
        return 0.0
    val = (sim - baseline) / (max_expected - baseline)
    return min(max(val, 0.0), 1.0)


async def run_sensitivity_analysis():
    print("=" * 100, flush=True)
    print(
        "🔬 ANÁLISIS DE SENSIBILIDAD Y BÚSQUEDA DE PONDERACIONES ÓPTIMAS (GRID SEARCH)",
        flush=True,
    )
    print("=" * 100, flush=True)

    tenders_dict = await load_all_tenders()
    print(f"[POSTGRES] {len(tenders_dict)} licitaciones cargadas.", flush=True)

    qdrant_client = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    loop = asyncio.get_running_loop()
    embed_model = await loop.run_in_executor(
        None, lambda: SentenceTransformer(MODEL_NAME)
    )
    reranker = BgeRerankerService(temperature=1.2)
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

    # 1. Preparar vectores del proveedor
    sup_ov, sup_it, sup_req = MultiVectorTextBuilder.build_supplier_texts(supplier)
    sup_vectors = await loop.run_in_executor(
        None,
        lambda: embed_model.encode(
            [sup_ov, sup_it, sup_req], normalize_embeddings=True
        ),
    )
    v_sup_ov, v_sup_it, v_sup_req = sup_vectors[0], sup_vectors[1], sup_vectors[2]

    # 2. Recuperar Top 60 candidatos iniciales desde Qdrant
    supplier_global_text = text_builder.build_from_supplier(supplier)
    query_vector = (
        await loop.run_in_executor(
            None,
            lambda: embed_model.encode(
                [supplier_global_text], normalize_embeddings=True
            ),
        )
    )[0].tolist()

    res = await qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        using="tender",
        limit=60,
    )

    valid_candidates = []
    for p in res.points:
        uid = UUID(str(p.id))
        t = tenders_dict.get(uid)
        if t and (
            not supplier.regions or are_regions_matching(t.region, supplier.regions)
        ):
            valid_candidates.append(t)

    print(
        f"[CANDIDATOS] {len(valid_candidates)} licitaciones candidatas recuperadas de Qdrant.",
        flush=True,
    )

    # 3. Generar los 3 Named Vectors para los candidatos
    t_overviews = []
    t_items = []
    t_requirements = []
    for t in valid_candidates:
        ov, it, req = MultiVectorTextBuilder.build_tender_texts(t)
        t_overviews.append(ov)
        t_items.append(it)
        t_requirements.append(req)

    t_ov_vecs = await loop.run_in_executor(
        None,
        lambda: embed_model.encode(
            t_overviews, normalize_embeddings=True, batch_size=32
        ),
    )
    t_it_vecs = await loop.run_in_executor(
        None,
        lambda: embed_model.encode(t_items, normalize_embeddings=True, batch_size=32),
    )
    t_req_vecs = await loop.run_in_executor(
        None,
        lambda: embed_model.encode(
            t_requirements, normalize_embeddings=True, batch_size=32
        ),
    )

    # Pre-calcular similitudes crudas y escaladas para cada candidato
    raw_sims = {}
    for i, t in enumerate(valid_candidates):
        s_ov = cosine_similarity(v_sup_ov, t_ov_vecs[i])
        s_it = cosine_similarity(v_sup_it, t_it_vecs[i])
        s_req = cosine_similarity(v_sup_req, t_req_vecs[i])

        raw_sims[t.id] = {
            "s_ov": s_ov,
            "s_it": s_it,
            "s_req": s_req,
            "sc_ov": scale_cosine(s_ov, 0.35, 0.65),
            "sc_it": scale_cosine(s_it, 0.35, 0.65),
            "sc_req": scale_cosine(s_req, 0.35, 0.65),
        }

    # Pre-calcular Reranker sobre los candidatos
    rerank_pairs = [
        (t.id, text_builder.build_from_tender(tender=t, items=t.items))
        for t in valid_candidates
    ]
    reranked = await reranker.rerank(
        query_text=supplier_global_text,
        candidates=rerank_pairs,
        limit=len(valid_candidates),
    )
    rerank_map = {uid: score for uid, score in reranked}

    # Banderas léxicas
    lexical_flags = {}
    for t in valid_candidates:
        all_text = (
            f"{t.name} {t.description or ''} {' '.join([i.name for i in t.items])}"
        )
        sec_m = any(s.lower() in all_text.lower() for s in (supplier.sectors or []))
        kw_m = any(kw.lower() in all_text.lower() for kw in (supplier.keywords or []))
        lexical_flags[t.id] = (sec_m, kw_m)

    # Identificadores de licitaciones críticas para optimización
    CORE_CODES = [
        "1101892-152-COT26",
        "3113-38-COT26",
        "4066-312-COT26",
        "1593-148-COT26",
        "5504-260-COT26",
    ]
    SECONDARY_CODES = ["324-451-COT26", "2211-938-COT26", "2440-1307-COT26"]

    # ==========================================================
    # GRID SEARCH: Probar combinaciones de pesos
    # ==========================================================
    vector_weight_configs = [
        (0.45, 0.45, 0.10),
        (0.40, 0.40, 0.20),
        (0.50, 0.35, 0.15),
        (0.35, 0.50, 0.15),
        (0.50, 0.40, 0.10),
    ]

    hybrid_weight_configs = [
        # (W_vec, W_rr, W_sec, W_kw)
        (0.45, 0.35, 0.10, 0.10),
        (0.50, 0.30, 0.10, 0.10),
        (0.40, 0.40, 0.10, 0.10),
        (0.35, 0.35, 0.15, 0.15),
        (0.40, 0.30, 0.15, 0.15),
        (0.45, 0.25, 0.15, 0.15),
        (0.50, 0.20, 0.15, 0.15),
        (0.35, 0.45, 0.10, 0.10),
    ]

    scaling_modes = ["scaled", "raw"]

    all_experiments = []

    for w_ov, w_it, w_req in vector_weight_configs:
        for W_vec, W_rr, W_sec, W_kw in hybrid_weight_configs:
            for mode in scaling_modes:
                scores_by_code = {}
                for t in valid_candidates:
                    sim = raw_sims[t.id]
                    if mode == "scaled":
                        v_score = (
                            (w_ov * sim["sc_ov"])
                            + (w_it * sim["sc_it"])
                            + (w_req * sim["sc_req"])
                        )
                    else:
                        v_score = (
                            (w_ov * sim["s_ov"])
                            + (w_it * sim["s_it"])
                            + (w_req * sim["s_req"])
                        )

                    r_score = rerank_map.get(t.id, 0.0)
                    sec_m, kw_m = lexical_flags[t.id]

                    final = (
                        W_vec * v_score
                        + W_rr * r_score
                        + (W_sec if sec_m else 0.0)
                        + (W_kw if kw_m else 0.0)
                    )
                    final = min(final, 1.0)
                    scores_by_code[t.code] = final

                core_scores = [
                    scores_by_code.get(c, 0.0)
                    for c in CORE_CODES
                    if c in scores_by_code
                ]
                sec_scores = [
                    scores_by_code.get(c, 0.0)
                    for c in SECONDARY_CODES
                    if c in scores_by_code
                ]

                avg_core = np.mean(core_scores) if core_scores else 0.0
                min_core = np.min(core_scores) if core_scores else 0.0
                avg_sec = np.mean(sec_scores) if sec_scores else 0.0

                # Recompensa: queremos avg_core >= 0.70 y separación clara
                penalization = 0.0
                if min_core < 0.65:
                    penalization += (0.65 - min_core) * 4.0

                separation = avg_core - avg_sec
                optimization_metric = avg_core + (separation * 1.2) - penalization

                exp_data = {
                    "v_weights": (w_ov, w_it, w_req),
                    "h_weights": (W_vec, W_rr, W_sec, W_kw),
                    "mode": mode,
                    "avg_core": avg_core,
                    "min_core": min_core,
                    "avg_sec": avg_sec,
                    "separation": separation,
                    "metric": optimization_metric,
                    "scores": scores_by_code,
                }
                all_experiments.append(exp_data)

    all_experiments.sort(key=lambda x: x["metric"], reverse=True)

    print("\n" + "=" * 100, flush=True)
    print(
        "📊 RESULTADOS DEL GRID SEARCH - TOP 5 COMBINACIONES DE PESOS ENCONTRADAS",
        flush=True,
    )
    print("=" * 100, flush=True)

    for i, exp in enumerate(all_experiments[:5], 1):
        w_ov, w_it, w_req = exp["v_weights"]
        W_vec, W_rr, W_sec, W_kw = exp["h_weights"]
        print(
            f"Opción #{i} | Puntuación de Calidad: {exp['metric']:.4f} | Modo: {exp['mode'].upper()}",
            flush=True,
        )
        print(
            f"   📐 Named Vectors: Overview={w_ov * 100:.0f}%, Items={w_it * 100:.0f}%, Requisitos={w_req * 100:.0f}%",
            flush=True,
        )
        print(
            f"   ⚙️ Pesos Híbridos: MultiVector={W_vec * 100:.0f}%, Reranker={W_rr * 100:.0f}%, Sector={W_sec * 100:.0f}%, Keywords={W_kw * 100:.0f}%",
            flush=True,
        )
        print(
            f"   🎯 Promedio Licitaciones Core: {exp['avg_core'] * 100:.1f}% (Mínimo: {exp['min_core'] * 100:.1f}%) | Licitaciones Secundarias: {exp['avg_sec'] * 100:.1f}%",
            flush=True,
        )
        print("   Detalle de Licitaciones Clave:")
        for c in CORE_CODES:
            if c in exp["scores"]:
                print(
                    f"      • [{c}]: {round(exp['scores'][c] * 100)}% (Score: {exp['scores'][c]:.4f})",
                    flush=True,
                )
        print("-" * 100, flush=True)

    best = all_experiments[0]
    print("\n" + "=" * 100, flush=True)
    print("🏆 CONFIGURACIÓN ÓPTIMA Y TOP 10 DE CONSTRUCCIÓN RESULTANTE", flush=True)
    print("=" * 100, flush=True)

    sorted_tenders = sorted(
        valid_candidates, key=lambda t: best["scores"].get(t.code, 0.0), reverse=True
    )
    for rank, t in enumerate(sorted_tenders[:10], 1):
        score = best["scores"].get(t.code, 0.0)
        percentage = round(score * 100)
        sec_m, kw_m = lexical_flags[t.id]
        flags = []
        if sec_m:
            flags.append("Sector")
        if kw_m:
            flags.append("Keywords")
        flags_str = ", ".join(flags) if flags else "Semántico"
        amount_str = (
            f"${t.available_amount_clp:,.0f} CLP" if t.available_amount_clp else "N/A"
        )
        print(
            f"#{rank:02d} | [{t.code}] | Compatibilidad: {percentage}% (Score: {score:.4f})",
            flush=True,
        )
        print(f"     Nombre: {t.name}", flush=True)
        print(
            f"     Comprador: {t.buyer_name or 'N/A'} | Coincidencias: [{flags_str}] | Monto: {amount_str}",
            flush=True,
        )
        print("-" * 100, flush=True)


if __name__ == "__main__":
    asyncio.run(run_sensitivity_analysis())
