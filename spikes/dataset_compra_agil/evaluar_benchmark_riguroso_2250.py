"""
Benchmark Riguroso de Matching y Ranking (Spike 2 - Paso 3)
Evaluación sobre Catálogo Abierto (2.250 Licitaciones: 250 Ground Truth + 2.000 Distractores)
y 50 Proveedores con Perfil Wizard (Cero Data Leakage), utilizando BGE-M3 (1024 dims).

Estrategias evaluadas:
  - Estrategia A: Baseline Producción BGE-M3 (Coseno denso puro)
  - Estrategia B: Búsqueda Híbrida (BGE-M3 + Léxico limpio en Título, Descripción y Partidas)
  - Estrategia C: Híbrido + Boost Regional Canónico (are_regions_matching, +0.05)
  - Estrategia D: Pipeline Producción (First-Stage Top 20 + BGE-Reranker v2 ONNX INT8 con Consulta Corta y RRF k=60)

Métricas reportadas:
  - Tabla 1: Métricas Duras (Solo Adjudicaciones Reales - Ground Truth, rel=2)
  - Tabla 2: Métricas con Juez LLM (Pool Fijo, con advertencia de Kappa = 0.0909)
  - Pruebas Estadísticas: Wilcoxon pareado con Holm-Bonferroni y Paired Bootstrap (IC 95%)
"""

import argparse
import asyncio
import json
import math
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import NAMESPACE_DNS, uuid5

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

import numpy as np
from scipy.stats import wilcoxon

backend_path = Path("monorepo/backend").resolve()
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.shared.regions import are_regions_matching
from app.infrastructure.services.bge_reranker_service import BgeRerankerService

# =====================================================================
# Funciones de Normalización y Métricas IR
# =====================================================================

def normalizar_texto(texto: str) -> str:
    """Remueve acentos y caracteres especiales, convirtiendo a minúsculas."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()


def tokenizar_palabras(texto: str) -> Set[str]:
    """Tokeniza extrayendo palabras de al menos 3 caracteres."""
    texto_norm = normalizar_texto(texto)
    return set(re.findall(r"\b[a-z0-9_]{3,}\b", texto_norm))


def calcular_dcg(relevancias: List[int], k: int) -> float:
    dcg = 0.0
    for i, rel in enumerate(relevancias[:k], 1):
        if rel > 0:
            dcg += (2**rel - 1) / math.log2(i + 1)
    return dcg


def calcular_ndcg(relevancias_obtenidas: List[int], relevancias_ideales: List[int], k: int) -> float:
    dcg = calcular_dcg(relevancias_obtenidas, k)
    idcg = calcular_dcg(relevancias_ideales, k)
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def calcular_success_at_1(relevancias: List[int]) -> float:
    return 1.0 if relevancias and relevancias[0] >= 1 else 0.0


def calcular_mrr(relevancias: List[int]) -> float:
    for i, rel in enumerate(relevancias, 1):
        if rel >= 1:
            return 1.0 / i
    return 0.0


def calcular_precision_at_k(relevancias: List[int], k: int) -> float:
    if k == 0:
        return 0.0
    return sum(1 for r in relevancias[:k] if r >= 1) / k


def calcular_recall_at_k(relevancias: List[int], total_positivos: int, k: int) -> float:
    if total_positivos == 0:
        return 0.0
    recuperados = sum(1 for r in relevancias[:k] if r >= 1)
    return min(1.0, recuperados / total_positivos)


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(np.dot(a, b) / (na * nb)) if na > 0 and nb > 0 else 0.0


def calcular_significancia_pareada(series_a: List[float], series_b: List[float]) -> Tuple[float, float, Tuple[float, float]]:
    diffs = np.array(series_b) - np.array(series_a)
    mean_diff = float(np.mean(diffs))

    if np.all(diffs == 0):
        p_val = 1.0
    else:
        try:
            stat, p_val = wilcoxon(diffs, alternative="two-sided")
        except Exception:
            p_val = 1.0

    rng = np.random.default_rng(42)
    n = len(diffs)
    boot_means = [np.mean(rng.choice(diffs, size=n, replace=True)) for _ in range(2000)]
    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))

    return mean_diff, float(p_val), (ci_lower, ci_upper)


def corregir_holm_bonferroni(p_valores: List[float]) -> List[float]:
    n = len(p_valores)
    ordenados = sorted(enumerate(p_valores), key=lambda x: x[1])
    p_adj = [0.0] * n
    max_p = 0.0
    for rank, (orig_idx, p) in enumerate(ordenados):
        adj = p * (n - rank)
        adj = max(adj, max_p)
        adj = min(adj, 1.0)
        max_p = adj
        p_adj[orig_idx] = adj
    return p_adj


# =====================================================================
# Ejecución del Benchmark
# =====================================================================

async def ejecutar_benchmark_riguroso():
    data_dir = Path("spikes/dataset_compra_agil/data")
    archivo_catalogo = data_dir / "catalogo_completo_con_distractores_2250.json"
    archivo_prov = data_dir / "dataset_proveedores_wizard_sin_fuga.json"
    archivo_embeddings = data_dir / "embeddings_bge_m3_2250.json"
    archivo_juicios_pool = data_dir / "juicios_pool_fijo_2250.json"

    with open(archivo_catalogo, "r", encoding="utf-8") as f:
        catalogo = json.load(f)
    with open(archivo_prov, "r", encoding="utf-8") as f:
        proveedores = json.load(f)
    with open(archivo_embeddings, "r", encoding="utf-8") as f:
        embeddings = json.load(f)
    with open(archivo_juicios_pool, "r", encoding="utf-8") as f:
        juicios_pool = json.load(f)

    print("=" * 95)
    print("🚀 BENCHMARK RIGUROSO DE MATCHING (SPIKE 2 - DATOS REALES)")
    print(f"Catálogo abierto: {len(catalogo)} licitaciones (250 Adjudicaciones Reales + 2.000 Distractores)")
    print(f"Población evaluada: {len(proveedores)} proveedores con perfil Wizard (CERO Data Leakage)")
    print(f"Modelo base de embeddings: BAAI/bge-m3 (1.024 dimensiones)")
    print("=" * 95)

    tenders_dict = {t["code"]: t for t in catalogo}
    tenders_vec = {t["code"]: np.array(embeddings[f"tender_{t['code']}"], dtype=np.float32) for t in catalogo}

    # Pre-tokenizar texto de licitaciones (título + descripción + partidas)
    tenders_tokens = {}
    for t in catalogo:
        code = t["code"]
        items_str = " ".join([f"{it.get('nombre', '')} {it.get('descripcion') or ''}" for it in t.get("items", [])])
        full_text = f"{t.get('name', '')} {t.get('description') or ''} {items_str}"
        tenders_tokens[code] = tokenizar_palabras(full_text)

    reranker = BgeRerankerService()

    estrategias = ["A_Embedding_Puro", "B_Hibrido_Lexico", "C_Hibrido_Regional", "D_Produccion_RRF"]
    metricas_dura = {est: {"ndcg_5": [], "ndcg_10": [], "success_1": [], "mrr": [], "p_5": [], "p_10": [], "recall_10": []} for est in estrategias}
    metricas_juez = {est: {"ndcg_5": [], "ndcg_10": [], "success_1": [], "mrr": [], "p_5": [], "p_10": [], "recall_10": []} for est in estrategias}

    for idx, prov in enumerate(proveedores, 1):
        rut = prov["rut"]
        pw = prov["perfil_wizard"]
        positivos_gt = set(prov.get("ids_procesos_positivos", []))
        vec_prov = np.array(embeddings[f"prov_{rut}"], dtype=np.float32)

        # Tokenizar campos del perfil Wizard
        tokens_sectores = set()
        for s in pw.get("sectors", []):
            tokens_sectores.update(tokenizar_palabras(s))

        tokens_keywords = set()
        for kw in pw.get("keywords", []):
            tokens_keywords.update(tokenizar_palabras(kw))

        regiones_prov = list(pw.get("regions", []))

        # Consulta corta para el Reranker: Rubro principal + 6 keywords clave
        consulta_corta = f"Proveedor: {', '.join(pw.get('sectors', []))}. Especialidades: {', '.join(pw.get('keywords', [])[:6])}"

        scores_A = []
        scores_B = []
        scores_C = []

        for code, t in tenders_dict.items():
            sim_cos = cosine_sim(vec_prov, tenders_vec[code])

            # Coincidencia léxica limpia sobre tokens (incluyendo partidas)
            toks_t = tenders_tokens[code]
            match_sec = len(tokens_sectores.intersection(toks_t))
            match_kw = len(tokens_keywords.intersection(toks_t))
            lexical_boost = min(0.35, (match_kw * 0.04) + (match_sec * 0.08))

            # Match regional canónico
            t_reg = t.get("region") or ""
            regional_match = are_regions_matching(t_reg, regiones_prov)

            # Estrategia A: Coseno BGE-M3
            score_a = sim_cos

            # Estrategia B: Híbrido (70% Coseno + 30% Léxico limpio en partidas)
            score_b = (0.70 * sim_cos) + (0.30 * min(1.0, lexical_boost * 3.0))

            # Estrategia C: Híbrido + Boost Regional moderado (+0.05 sin castigo)
            score_c = score_b + (0.05 if regional_match else 0.0)

            scores_A.append((code, score_a))
            scores_B.append((code, score_b))
            scores_C.append((code, score_c))

        scores_A.sort(key=lambda x: x[1], reverse=True)
        scores_B.sort(key=lambda x: x[1], reverse=True)
        scores_C.sort(key=lambda x: x[1], reverse=True)

        top_A = [code for code, _ in scores_A[:10]]
        top_B = [code for code, _ in scores_B[:10]]
        top_C = [code for code, _ in scores_C[:10]]

        # Estrategia D: Primer Estadio Top-20 + BGE Reranker con consulta corta y RRF
        candidatos_top20 = [code for code, _ in scores_B[:20]]
        cand_pairs = [
            (
                uuid5(NAMESPACE_DNS, c),
                f"Partidas: {', '.join([it.get('nombre', '') for it in tenders_dict[c].get('items', [])[:3]])}. "
                f"Licitación: {tenders_dict[c].get('name', '')}. {tenders_dict[c].get('description') or ''}."[:450]
            )
            for c in candidatos_top20
        ]

        rerank_results = await reranker.rerank(query_text=consulta_corta, candidates=cand_pairs, limit=20)
        rank_stage1 = {code: r for r, (code, _) in enumerate(scores_B[:20], 1)}
        rank_rerank = {code: r for r, (uid, _) in enumerate(rerank_results, 1) for code in candidatos_top20 if uuid5(NAMESPACE_DNS, code) == uid}

        scores_D = []
        for c in candidatos_top20:
            r1 = rank_stage1.get(c, 20)
            r2 = rank_rerank.get(c, 20)
            rrf = (1.0 / (60 + r1)) + (1.0 / (60 + r2))
            scores_D.append((c, rrf))

        scores_D.sort(key=lambda x: x[1], reverse=True)
        top_D = [code for code, _ in scores_D[:10]]

        # -------------------------------------------------------------
        # Escala 1: Métricas Duras (Solo Relevancia 2 = Ganadas Reales)
        # -------------------------------------------------------------
        def rel_dura(c: str) -> int:
            return 2 if c in positivos_gt else 0

        ideal_dura = sorted([rel_dura(c) for c in tenders_dict], reverse=True)
        total_gt = len(positivos_gt)  # Siempre 5

        # -------------------------------------------------------------
        # Escala 2: Métricas con Juez LLM (Pool Fijo)
        # -------------------------------------------------------------
        def rel_juez(c: str) -> int:
            if c in positivos_gt:
                return 2
            k = f"{rut}::{c}"
            if k in juicios_pool and juicios_pool[k].get("relevante_para_click"):
                return 1
            return 0

        ideal_juez = sorted([rel_juez(c) for c in tenders_dict], reverse=True)
        total_relevantes_juez = sum(1 for r in ideal_juez if r >= 1)

        estrategias_eval = [
            ("A_Embedding_Puro", top_A),
            ("B_Hibrido_Lexico", top_B),
            ("C_Hibrido_Regional", top_C),
            ("D_Produccion_RRF", top_D),
        ]

        for est_nombre, top_lista in estrategias_eval:
            # 1. Medir Duras
            rd = [rel_dura(c) for c in top_lista]
            metricas_dura[est_nombre]["ndcg_5"].append(calcular_ndcg(rd, ideal_dura, k=5))
            metricas_dura[est_nombre]["ndcg_10"].append(calcular_ndcg(rd, ideal_dura, k=10))
            metricas_dura[est_nombre]["success_1"].append(calcular_success_at_1(rd))
            metricas_dura[est_nombre]["mrr"].append(calcular_mrr(rd))
            metricas_dura[est_nombre]["p_5"].append(calcular_precision_at_k(rd, k=5))
            metricas_dura[est_nombre]["p_10"].append(calcular_precision_at_k(rd, k=10))
            metricas_dura[est_nombre]["recall_10"].append(calcular_recall_at_k(rd, total_gt, k=10))

            # 2. Medir con Juez
            rj = [rel_juez(c) for c in top_lista]
            metricas_juez[est_nombre]["ndcg_5"].append(calcular_ndcg(rj, ideal_juez, k=5))
            metricas_juez[est_nombre]["ndcg_10"].append(calcular_ndcg(rj, ideal_juez, k=10))
            metricas_juez[est_nombre]["success_1"].append(calcular_success_at_1(rj))
            metricas_juez[est_nombre]["mrr"].append(calcular_mrr(rj))
            metricas_juez[est_nombre]["p_5"].append(calcular_precision_at_k(rj, k=5))
            metricas_juez[est_nombre]["p_10"].append(calcular_precision_at_k(rj, k=10))
            metricas_juez[est_nombre]["recall_10"].append(calcular_recall_at_k(rj, total_relevantes_juez, k=10))

        if idx % 10 == 0 or idx == len(proveedores):
            print(f"  Evaluados {idx}/{len(proveedores)} proveedores...")

    # =====================================================================
    # Presentación de Resultados
    # =====================================================================
    header = f"{'Estrategia':<22} | {'NDCG@5':<7} | {'NDCG@10':<7} | {'Succ@1':<7} | {'MRR':<7} | {'P@5':<7} | {'P@10 (Max.5)':<12} | {'Recall@10':<9}"
    
    print("\n" + "=" * 95)
    print("📊 TABLA 1: MÉTRICAS DURAS (SOLO ADJUDICACIONES REALES - GROUND TRUTH, REL = 2)")
    print("Condiciones: Catálogo 2.250 licitaciones (250 GT + 2.000 Distractores) | Cero Data Leakage | BGE-M3")
    print("=" * 95)
    print(header)
    print("-" * len(header))

    res_duras_print = {}
    for est in metricas_dura:
        m = metricas_dura[est]
        res_duras_print[est] = {k: np.mean(v) for k, v in m.items()}
        r = res_duras_print[est]
        print(f"{est:<22} | {r['ndcg_5']:.4f}  | {r['ndcg_10']:.4f}   | {r['success_1']:.4f}  | {r['mrr']:.4f}  | {r['p_5']:.4f}  | {r['p_10']:.4f}       | {r['recall_10']:.4f}")

    print("=" * 95)

    print("\n" + "=" * 95)
    print("📊 TABLA 2: MÉTRICAS CON JUEZ LLM (POOL FIJO CONGELADO)")
    print("⚠️ ADVERTENCIA DE VALIDEZ: Acuerdo inter-anotador del Juez κ = 0.0909 (Acuerdo Pobre / Sesgo Positivo)")
    print("=" * 95)
    print(header)
    print("-" * len(header))

    res_juez_print = {}
    for est in metricas_juez:
        m = metricas_juez[est]
        res_juez_print[est] = {k: np.mean(v) for k, v in m.items()}
        r = res_juez_print[est]
        print(f"{est:<22} | {r['ndcg_5']:.4f}  | {r['ndcg_10']:.4f}   | {r['success_1']:.4f}  | {r['mrr']:.4f}  | {r['p_5']:.4f}  | {r['p_10']:.4f}       | {r['recall_10']:.4f}")

    print("=" * 95)

    # Pruebas de Significancia Estadística
    print("\n📈 PRUEBAS DE SIGNIFICANCIA ESTADÍSTICA (Wilcoxon Pareado + Holm-Bonferroni + Bootstrap IC 95%)")
    print("Variable analizada: NDCG@10 (Métricas Duras sobre Catálogo de 2.250)")
    print("-" * 95)

    comparaciones = [
        ("A_Embedding_Puro", "B_Hibrido_Lexico"),
        ("A_Embedding_Puro", "C_Hibrido_Regional"),
        ("A_Embedding_Puro", "D_Produccion_RRF"),
        ("B_Hibrido_Lexico", "C_Hibrido_Regional"),
        ("B_Hibrido_Lexico", "D_Produccion_RRF"),
    ]

    p_raw_list = []
    diff_stats = []

    for est_a, est_b in comparaciones:
        vals_a = metricas_dura[est_a]["ndcg_10"]
        vals_b = metricas_dura[est_b]["ndcg_10"]
        diff, p_raw, (ci_low, ci_high) = calcular_significancia_pareada(vals_a, vals_b)
        p_raw_list.append(p_raw)
        diff_stats.append((est_a, est_b, diff, p_raw, ci_low, ci_high))

    p_adj_list = corregir_holm_bonferroni(p_raw_list)

    print(f"{'Comparación':<35} | {'Diff Media':<10} | {'p-raw':<8} | {'p-adj (Holm)':<12} | {'Bootstrap 95% CI':<20}")
    print("-" * 95)
    for (est_a, est_b, diff, p_raw, ci_low, ci_high), p_adj in zip(diff_stats, p_adj_list):
        comp_str = f"{est_b} vs {est_a}"
        signif = "*" if p_adj < 0.05 else "ns"
        ci_str = f"[{ci_low:+.4f}, {ci_high:+.4f}]"
        print(f"{comp_str:<35} | {diff:+.4f}     | {p_raw:.4f}   | {p_adj:.4f} ({signif})   | {ci_str:<20}")

    print("-" * 95)
    print("Significancia: * p < 0.05 corregido por Holm | ns = no significativo (p >= 0.05)")

    resultados_finales = {
        "metricas_duras": {est: {k: round(float(v), 4) for k, v in r.items()} for est, r in res_duras_print.items()},
        "metricas_juez": {est: {k: round(float(v), 4) for k, v in r.items()} for est, r in res_juez_print.items()},
        "significancia_ndcg10_duras": [
            {
                "comparacion": f"{est_b} vs {est_a}",
                "diff_media": round(float(diff), 4),
                "p_raw": round(float(p_raw), 4),
                "p_adj_holm": round(float(p_adj), 4),
                "ci_95": [round(float(ci_low), 4), round(float(ci_high), 4)],
                "es_significativo": bool(p_adj < 0.05),
            }
            for (est_a, est_b, diff, p_raw, ci_low, ci_high), p_adj in zip(diff_stats, p_adj_list)
        ],
    }

    salida_json = data_dir / "metricas_benchmark_riguroso_2250.json"
    with open(salida_json, "w", encoding="utf-8") as f:
        json.dump(resultados_finales, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Resultados completos exportados a: {salida_json.resolve()}")

if __name__ == "__main__":
    asyncio.run(ejecutar_benchmark_riguroso())
