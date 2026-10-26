"""
Spike 2 - Fase 2: Evaluación del Caso Sin Historial (Cold-Start) e Inferencia Semántica de Categorías.

Evalúa en el catálogo temporal (1.176 licitaciones, 50 proveedores, 100 positivos reales):
  1. La brecha de degradación al no tener historial de compras (Categorías y Productos históricos).
  2. La efectividad de inferir categorías UNSPSC automáticamente a partir de las keywords declaradas en el Wizard.
  3. El impacto de incorporar las categorías inferidas al pipeline de producción (P + L + C_inf).

Estrategias evaluadas:
  - A_Denso: Baseline denso puro.
  - C_Oracle: Híbrido estructural con categorías históricas reales del comprador (techo).
  - C_ColdStart: Híbrido estructural sin categorías históricas (wizard estándar sin inferencia).
  - C_Inferred: Híbrido estructural con categorías inferidas semánticamente desde las keywords.
  - P_Produccion: Pipeline producción actual (Top-50 perfil denso + Top-30 MaxSim partidas + Scorer).
  - P_plus_L_RRF: Producción + canal léxico BM25 fusionado con RRF.
  - P_plus_L_plus_Cinf: Producción + canal léxico BM25 + canal/boost de categorías inferidas.
"""

import json
import math
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import numpy as np
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "monorepo" / "backend"))

from app.shared.regions import are_regions_matching
from app.application.services.compatibility_formula import CompatibilityFormula, CalibrationCoefficients, item_match_signals
from app.infrastructure.services.bge_reranker_service import BgeRerankerService

TEMP = ROOT / "spikes" / "dataset_compra_agil" / "data" / "temporal"
STOP = set("de la el en y a los las del por para con un una al se que o su sus lo como mas mas son sin".split())

FORMULA = CompatibilityFormula(
    relevant=CalibrationCoefficients(
        intercept=-3.88778,
        reranker=0.32806,
        best_match=3.25484,
        coverage=6.02960,
    ),
    exact=CalibrationCoefficients(
        intercept=-5.09583,
        reranker=0.40134,
        best_match=3.53258,
        coverage=5.06198,
    ),
)


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def stem(w: str) -> str:
    for suf in ("ciones", "cion", "mente", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def tokens(t: str) -> List[str]:
    return [stem(w) for w in re.findall(r"[a-z0-9]{3,}", norm(t)) if w not in STOP]


def texto_doc(d: Dict[str, Any]) -> str:
    items = "; ".join(f"{i['nombre']} ({i['descripcion'][:120]})" if i.get("descripcion") else i["nombre"] for i in d.get("items", [])[:8])
    cats = "; ".join(sorted({i["categoria"] for i in d.get("items", []) if i.get("categoria")})[:4])
    return f"Partidas: {items}. {d['name']}. {d['description']}. Categoría: {cats}"[:1800]


def texto_partida(i: Dict[str, Any]) -> str:
    desc = (i.get("descripcion") or "").strip()
    return f"{i['nombre']}: {desc[:200]}" if desc else i["nombre"]


def texto_perfil(p: Dict[str, Any]) -> str:
    pf = p["perfil"]
    return f"Rubros: {', '.join(pf['sectors'])}. {pf['description']} Productos: {', '.join(pf['keywords'])}."


class BM25:
    def __init__(self, docs_tokens: List[List[str]], k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.N = len(docs_tokens)
        self.dl = np.array([len(d) for d in docs_tokens], dtype=np.float32)
        self.avg = float(self.dl.mean()) or 1.0
        self.tf: List[Counter] = [Counter(d) for d in docs_tokens]
        df = Counter()
        for c in self.tf:
            df.update(c.keys())
        self.idf = {w: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for w, n in df.items()}

    def score(self, q_tokens: List[str]) -> np.ndarray:
        s = np.zeros(self.N, dtype=np.float32)
        for w in set(q_tokens):
            idf = self.idf.get(w)
            if idf is None:
                continue
            for i, c in enumerate(self.tf):
                f = c.get(w)
                if f:
                    s[i] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avg))
        return s


def ndcg(rels: List[int], ideal: List[int], k: int) -> float:
    dcg = lambda r: sum((2 ** x - 1) / math.log2(i + 2) for i, x in enumerate(r[:k]) if x > 0)
    idcg = dcg(ideal)
    return dcg(rels) / idcg if idcg else 0.0


def rrf(rank_lists: List[List[int]], n: int, k: int = 60) -> np.ndarray:
    s = np.zeros(n, dtype=np.float32)
    for pos in rank_lists:
        s += 1.0 / (k + pos + 1)
    return s


def posiciones(scores: np.ndarray) -> np.ndarray:
    order = np.argsort(-scores, kind="stable")
    pos = np.empty(len(scores), dtype=np.int64)
    pos[order] = np.arange(len(scores))
    return pos


def boot_pareado(diffs: np.ndarray, reps=5000, seed=42) -> Tuple[float, float]:
    rng = np.random.default_rng(seed)
    m = [rng.choice(diffs, size=len(diffs), replace=True).mean() for _ in range(reps)]
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def holm(ps: List[float]) -> List[float]:
    n = len(ps)
    orden = sorted(range(n), key=lambda i: ps[i])
    adj = [0.0] * n
    mx = 0.0
    for r, i in enumerate(orden):
        mx = max(mx, min(1.0, ps[i] * (n - r)))
        adj[i] = mx
    return adj


def inferir_categorias_desde_keywords(
    kws: List[str],
    cache_mv: Dict[str, List[float]],
    partidas_unicas: List[Dict[str, Any]],
    sim_threshold: float = 0.60,
    top_k: int = 5,
) -> Set[int]:
    """Infiere códigos de categoría UNSPSC buscando las keywords contra las partidas del catálogo."""
    if not kws:
        return set()

    k_vecs = [np.array(cache_mv[k], dtype=np.float32) for k in kws if k in cache_mv]
    if not k_vecs:
        return set()

    K = np.array(k_vecs)
    K /= np.linalg.norm(K, axis=1, keepdims=True)

    # Extraer vectores de partidas únicas
    p_vecs = []
    p_cats = []
    for p in partidas_unicas:
        txt = p["texto"]
        if txt in cache_mv and p.get("codigo_categoria"):
            p_vecs.append(cache_mv[txt])
            p_cats.append(p["codigo_categoria"])

    if not p_vecs:
        return set()

    P = np.array(p_vecs, dtype=np.float32)
    P /= np.linalg.norm(P, axis=1, keepdims=True)

    # Matriz de similitud: (n_kws, n_partidas)
    sims = K @ P.T
    max_sim_por_partida = sims.max(axis=0)

    # Ponderar categorías por similitud sobre el umbral
    cat_weights: Counter = Counter()
    for sim, cat in zip(max_sim_por_partida, p_cats):
        if sim >= sim_threshold:
            cat_weights[cat] += sim

    # Tomar top_k categorías inferidas
    mejores = [cat for cat, _ in cat_weights.most_common(top_k)]
    return set(mejores)


async def main():
    catalogo = json.loads((TEMP / "catalogo_temporal.json").read_text(encoding="utf-8"))
    provs = json.loads((TEMP / "proveedores_temporal.json").read_text(encoding="utf-8"))
    codes = [d["code"] for d in catalogo]
    idx = {c: i for i, c in enumerate(codes)}
    N = len(codes)

    print(f"Catálogo = {N} licitaciones | Proveedores = {len(provs)}")

    # Cargar embeddings cacheados
    emb_path = TEMP / "embeddings_bge_m3_temporal.json"
    cache = json.loads(emb_path.read_text(encoding="utf-8")) if emb_path.exists() else {}

    cache_mv_path = TEMP / "calibracion_embeddings_mv.json"
    cache_mv = json.loads(cache_mv_path.read_text(encoding="utf-8")) if cache_mv_path.exists() else {}

    # Matriz densa de documentos
    M_tenders = np.array([cache[f"doc_{c}"] for c in codes], dtype=np.float32)
    M_tenders /= np.linalg.norm(M_tenders, axis=1, keepdims=True)

    # BM25 sobre licitaciones
    bm25 = BM25([tokens(texto_doc(d)) for d in catalogo])
    cats_doc = [{i["codigo_categoria"] for i in d["items"] if i.get("codigo_categoria")} for d in catalogo]

    # Partidas únicas para inferencia
    partidas_unicas = []
    vistos = set()
    for d in catalogo:
        for it in d.get("items", []):
            txt = texto_partida(it)
            if txt not in vistos and it.get("codigo_categoria"):
                vistos.add(txt)
                partidas_unicas.append({
                    "texto": txt,
                    "codigo_categoria": it.get("codigo_categoria"),
                })

    # Partidas por documento
    partidas_vecs_por_doc = []
    partidas_objs_por_doc = []
    for d in catalogo:
        doc_items = d.get("items", [])
        partidas_objs_por_doc.append(doc_items)
        pts = [texto_partida(it) for it in doc_items]
        v_list = [cache_mv[t] for t in pts if t in cache_mv]
        if v_list:
            mat = np.array(v_list, dtype=np.float32)
            mat /= np.linalg.norm(mat, axis=1, keepdims=True)
            partidas_vecs_por_doc.append(mat)
        else:
            partidas_vecs_por_doc.append(np.empty((0, 1024), dtype=np.float32))

    # Iniciar Reranker
    reranker = BgeRerankerService()
    print("Reranker BGE-M3 listo.")

    estr = [
        "A_Denso",
        "C_Oracle",
        "C_ColdStart",
        "C_Inferred",
        "P_Produccion",
        "P_plus_L_RRF",
        "P_plus_L_plus_Cinf",
    ]
    Ks = (10, 50, 100, 200)
    res = {e: {"ndcg10": [], "mrr": [], "succ1": [], "p10": [], **{f"recall{k}": [] for k in Ks}} for e in estr}

    inferencia_stats = {"overlap_count": [], "jaccard": [], "inferred_count": []}

    print(f"\nEvaluando {len(provs)} proveedores con simulación Cold-Start...")
    for n_p, p in enumerate(provs, 1):
        if n_p % 10 == 0 or n_p == 1:
            print(f"  Progreso: {n_p}/{len(provs)} proveedores evaluados...")
        pos_set = {idx[c] for c in p["ids_positivos"] if c in idx}
        if not pos_set:
            continue

        regiones_prov = p["perfil"]["regions"]
        cats_oracle = set(p["perfil"]["categorias_historicas"])
        kws = p["perfil"]["keywords"]
        sectores = p["perfil"]["sectors"]

        # Inferencia de categorías desde keywords
        cats_inferred = inferir_categorias_desde_keywords(
            kws, cache_mv, partidas_unicas, sim_threshold=0.62, top_k=4
        )
        overlap = len(cats_oracle & cats_inferred)
        union = len(cats_oracle | cats_inferred) or 1
        inferencia_stats["overlap_count"].append(overlap)
        inferencia_stats["jaccard"].append(overlap / union)
        inferencia_stats["inferred_count"].append(len(cats_inferred))

        # 1. Denso
        qv = np.array(cache[f"prov_{p['rut']}"], dtype=np.float32)
        qv /= np.linalg.norm(qv)
        s_dense = M_tenders @ qv

        # 2. BM25 (léxico wizard)
        q_lexica = " ".join(kws + sectores)
        s_bm25_lexica = bm25.score(tokens(q_lexica))

        # BM25 con productos históricos (oráculo del spike original)
        q_tok_oracle = tokens(" ".join(kws + p["perfil"].get("productos_historicos", []) + sectores))
        s_bm25_oracle = bm25.score(q_tok_oracle)

        # 3. MaxSim partidas
        K_prov = np.array([cache_mv[k] for k in kws], dtype=np.float32)
        K_prov /= np.linalg.norm(K_prov, axis=1, keepdims=True)
        s_maxsim = np.zeros(N, dtype=np.float32)
        for i in range(N):
            P_doc = partidas_vecs_por_doc[i]
            if len(P_doc) > 0:
                s_maxsim[i] = float((K_prov @ P_doc.T).max())

        mask_region = np.array([are_regions_matching(catalogo[i].get("region") or "", regiones_prov) for i in range(N)])

        # Estrategia A
        s_A = np.where(mask_region, s_dense, -1e9)
        rankings = {"A_Denso": list(np.argsort(-s_A, kind="stable"))}

        # Boosts estructurales
        pos_d = posiciones(s_dense)
        pos_b_oracle = posiciones(s_bm25_oracle)
        pos_b_wizard = posiciones(s_bm25_lexica)

        boost_reg = np.array([(0.5 if are_regions_matching(catalogo[i].get("region") or "", regiones_prov) else 0.0) for i in range(N)], dtype=np.float32)
        boost_cat_oracle = np.array([(1.0 if cats_doc[i] & cats_oracle else 0.0) for i in range(N)], dtype=np.float32)
        boost_cat_inferred = np.array([(1.0 if cats_doc[i] & cats_inferred else 0.0) for i in range(N)], dtype=np.float32)

        # C_Oracle
        pos_boost_oracle = posiciones(boost_reg + boost_cat_oracle + 1e-6 * s_bm25_oracle)
        s_C_oracle = rrf([pos_d, pos_b_oracle, pos_boost_oracle], N)
        rankings["C_Oracle"] = list(np.argsort(-s_C_oracle, kind="stable"))

        # C_ColdStart (sin categorías históricas)
        pos_boost_cold = posiciones(boost_reg + 1e-6 * s_bm25_lexica)
        s_C_cold = rrf([pos_d, pos_b_wizard, pos_boost_cold], N)
        rankings["C_ColdStart"] = list(np.argsort(-s_C_cold, kind="stable"))

        # C_Inferred (con categorías inferidas semánticamente)
        pos_boost_inferred = posiciones(boost_reg + boost_cat_inferred + 1e-6 * s_bm25_lexica)
        s_C_inferred = rrf([pos_d, pos_b_wizard, pos_boost_inferred], N)
        rankings["C_Inferred"] = list(np.argsort(-s_C_inferred, kind="stable"))

        # Recuperación de Producción
        cand_dense = [i for i in np.argsort(-s_A) if mask_region[i]][:50]
        s_maxsim_reg = np.where(mask_region, s_maxsim, -1e9)
        cand_maxsim = [i for i in np.argsort(-s_maxsim_reg) if mask_region[i]][:30]
        s_bm25_reg = np.where(mask_region, s_bm25_lexica, -1e9)
        cand_lex = [i for i in np.argsort(-s_bm25_reg) if mask_region[i]][:30]

        # Canal de categorías inferidas para Producción (Top-30)
        s_cat_inferred_reg = np.where(mask_region, boost_cat_inferred * (s_dense + 1.0), -1e9)
        cand_cat_inf = [i for i in np.argsort(-s_cat_inferred_reg) if mask_region[i]][:30]

        # P candidatos
        candidatos_P = list(dict.fromkeys(cand_dense + [i for i in cand_maxsim if i not in set(cand_dense)]))

        # P+L candidatos
        pos_dense_map = {cid: pos for pos, cid in enumerate(cand_dense)}
        pos_items_map = {cid: pos for pos, cid in enumerate(cand_maxsim)}
        pos_lex_map = {cid: pos for pos, cid in enumerate(cand_lex)}
        todos_PL = list(dict.fromkeys(cand_dense + cand_maxsim + cand_lex))
        rrf_PL = {
            cid: (
                (1.0 / (60 + pos_dense_map[cid] + 1) if cid in pos_dense_map else 0.0)
                + (1.0 / (60 + pos_items_map[cid] + 1) if cid in pos_items_map else 0.0)
                + (1.0 / (60 + pos_lex_map[cid] + 1) if cid in pos_lex_map else 0.0)
            )
            for cid in todos_PL
        }
        candidatos_PL = sorted(todos_PL, key=lambda c: rrf_PL[c], reverse=True)

        # P+L+Cinf candidatos
        pos_cat_map = {cid: pos for pos, cid in enumerate(cand_cat_inf)}
        todos_PLC = list(dict.fromkeys(cand_dense + cand_maxsim + cand_lex + cand_cat_inf))
        rrf_PLC = {
            cid: (
                (1.0 / (60 + pos_dense_map[cid] + 1) if cid in pos_dense_map else 0.0)
                + (1.0 / (60 + pos_items_map[cid] + 1) if cid in pos_items_map else 0.0)
                + (1.0 / (60 + pos_lex_map[cid] + 1) if cid in pos_lex_map else 0.0)
                + (1.0 / (60 + pos_cat_map[cid] + 1) if cid in pos_cat_map else 0.0)
            )
            for cid in todos_PLC
        }
        candidatos_PLC = sorted(todos_PLC, key=lambda c: rrf_PLC[c], reverse=True)

        # Scorer común para P, P+L y P+L+Cinf
        pool_a_puntuar = list(dict.fromkeys(candidatos_P + candidatos_PL + candidatos_PLC))
        q_rerank = f"{', '.join(sectores)}. Productos: {', '.join(kws[:8])}"
        pares_rerank = [(catalogo[cid]["code"], texto_doc(catalogo[cid])[:450]) for cid in pool_a_puntuar]
        rr_res = await reranker.rerank(query_text=q_rerank, candidates=pares_rerank, limit=len(pares_rerank))
        rr_map = {code: score for code, score in rr_res}

        scores_scorer: Dict[int, float] = {}
        for cid in pool_a_puntuar:
            t_obj = catalogo[cid]
            rr_val = rr_map.get(t_obj["code"], 0.0)
            P_doc = partidas_vecs_por_doc[cid]
            if len(P_doc) > 0:
                sim_mat = K_prov @ P_doc.T
                b = float(sim_mat.max())
                c = float(sim_mat.max(axis=0).mean())
            else:
                b, c = 0.0, 0.0

            scores_scorer[cid] = FORMULA.score(reranker_score=rr_val, best_match=b, coverage=c)

        # P_Produccion
        rank_P_scored = sorted(candidatos_P, key=lambda c: scores_scorer[c], reverse=True)
        resto_P = [i for i in rankings["A_Denso"] if i not in set(rank_P_scored)]
        rankings["P_Produccion"] = rank_P_scored + resto_P

        # P_plus_L_RRF
        pos_scorer_PL = {cid: pos for pos, cid in enumerate(sorted(candidatos_PL, key=lambda c: scores_scorer[c], reverse=True))}
        pos_lex_PL = {cid: pos for pos, cid in enumerate(cand_lex)}
        fus_PL = sorted(
            candidatos_PL,
            key=lambda c: (
                1.0 / (60 + pos_scorer_PL[c] + 1)
                + (1.0 / (60 + pos_lex_PL[c] + 1) if c in pos_lex_PL else 0.0)
            ),
            reverse=True,
        )
        resto_PL = [i for i in rankings["A_Denso"] if i not in set(fus_PL)]
        rankings["P_plus_L_RRF"] = fus_PL + resto_PL

        # P_plus_L_plus_Cinf
        pos_scorer_PLC = {cid: pos for pos, cid in enumerate(sorted(candidatos_PLC, key=lambda c: scores_scorer[c], reverse=True))}
        pos_lex_PLC = {cid: pos for pos, cid in enumerate(cand_lex)}
        pos_cinf_PLC = {cid: pos for pos, cid in enumerate(cand_cat_inf)}
        fus_PLC = sorted(
            candidatos_PLC,
            key=lambda c: (
                1.0 / (60 + pos_scorer_PLC[c] + 1)
                + (1.0 / (60 + pos_lex_PLC[c] + 1) if c in pos_lex_PLC else 0.0)
                + (1.0 / (60 + pos_cinf_PLC[c] + 1) if c in pos_cinf_PLC else 0.0)
            ),
            reverse=True,
        )
        resto_PLC = [i for i in rankings["A_Denso"] if i not in set(fus_PLC)]
        rankings["P_plus_L_plus_Cinf"] = fus_PLC + resto_PLC

        # Métricas para este proveedor
        for e in estr:
            rk = rankings[e]
            rels = [2 if i in pos_set else 0 for i in rk[:200]]
            ideal = sorted([2] * len(pos_set) + [0] * 10, reverse=True)
            res[e]["ndcg10"].append(ndcg(rels, ideal, 10))
            pos_hit = [pos for pos, r in enumerate(rels) if r > 0]
            res[e]["mrr"].append(1.0 / (pos_hit[0] + 1) if pos_hit else 0.0)
            res[e]["succ1"].append(1.0 if rels and rels[0] > 0 else 0.0)
            res[e]["p10"].append(sum(1 for r in rels[:10] if r > 0) / 10.0)
            for k in Ks:
                rec = len({i for i in rk[:k] if i in pos_set}) / len(pos_set)
                res[e][f"recall{k}"].append(rec)

    # Resultados Agregados
    print("\n" + "=" * 95)
    print(f"{'Estrategia':<22} | {'NDCG@10':<8} | {'MRR':<8} | {'Succ@1':<8} | {'R@10':<8} | {'R@50':<8} | {'R@100':<8}")
    print("-" * 95)
    medias = {}
    for e in estr:
        m_ndcg = float(np.mean(res[e]["ndcg10"]))
        m_mrr = float(np.mean(res[e]["mrr"]))
        m_succ1 = float(np.mean(res[e]["succ1"]))
        m_r10 = float(np.mean(res[e]["recall10"]))
        m_r50 = float(np.mean(res[e]["recall50"]))
        m_r100 = float(np.mean(res[e]["recall100"]))
        medias[e] = m_ndcg
        print(f"{e:<22} | {m_ndcg:<8.4f} | {m_mrr:<8.4f} | {m_succ1:<8.4f} | {m_r10:<8.4f} | {m_r50:<8.4f} | {m_r100:<8.4f}")
    print("=" * 95)

    print("\nEstadísticas de Inferencia Semántica de Categorías (Keywords -> UNSPSC):")
    print(f"  Promedio categorías inferidas por proveedor: {np.mean(inferencia_stats['inferred_count']):.1f}")
    print(f"  Solapamiento con categorías históricas reales: {np.mean(inferencia_stats['overlap_count']):.2f}")
    print(f"  Jaccard Index con categorías reales: {np.mean(inferencia_stats['jaccard']):.3f}")

    # Análisis de Brecha Cold-Start y Significancia
    print("\nAnálisis de Brecha y Comparaciones Pareadas (Wilcoxon + Bootstrap 95%):")
    comparaciones = [
        ("Brecha Cold-Start en Híbrido", "C_ColdStart", "C_Oracle"),
        ("Efecto Inferencia en Híbrido", "C_Inferred", "C_ColdStart"),
        ("Inferencia vs Oráculo en Híbrido", "C_Inferred", "C_Oracle"),
        ("Producción + Léxico vs Producción", "P_plus_L_RRF", "P_Produccion"),
        ("Producción + Léxico + Categorías vs P+L", "P_plus_L_plus_Cinf", "P_plus_L_RRF"),
        ("Producción + Léxico + Categorías vs P", "P_plus_L_plus_Cinf", "P_Produccion"),
    ]

    p_raw = []
    deltas = []
    cis = []
    for label, e_test, e_ref in comparaciones:
        diff = np.array(res[e_test]["ndcg10"]) - np.array(res[e_ref]["ndcg10"])
        delta = float(diff.mean())
        ci = boot_pareado(diff)
        try:
            stat, p = wilcoxon(diff, zero_method="pratt")
        except Exception:
            p = 1.0
        p_raw.append(p)
        deltas.append(delta)
        cis.append(ci)

    p_adj = holm(p_raw)
    for (label, e_test, e_ref), delta, ci, p, padj in zip(comparaciones, deltas, cis, p_raw, p_adj):
        sig = "**" if padj < 0.05 else ("*" if p < 0.05 else "ns")
        print(f"  {label:<42}: Δ={delta:+.4f} | IC 95%=[{ci[0]:+.4f}, {ci[1]:+.4f}] | p_adj={padj:.4f} ({sig})")

    # Guardar métricas en JSON
    metricas_path = TEMP / "metricas_benchmark_fase2.json"
    resumen_salida = {
        "medias": {e: {k: float(np.mean(v)) for k, v in res[e].items()} for e in estr},
        "inferencia_stats": {k: float(np.mean(v)) for k, v in inferencia_stats.items()},
        "comparaciones": [
            {
                "comparacion": comp[0],
                "test": comp[1],
                "ref": comp[2],
                "delta_ndcg10": d,
                "ic_95": ci,
                "p_raw": p,
                "p_adj": padj,
            }
            for comp, d, ci, p, padj in zip(comparaciones, deltas, cis, p_raw, p_adj)
        ],
    }
    metricas_path.write_text(json.dumps(resumen_salida, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResultados guardados en {metricas_path}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
