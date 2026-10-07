"""
Spike 2 - Fase 0: Medición del Pipeline Real de Producción vs Canal Léxico Sparse (BM25).

Compara en el catálogo temporal (1.176 licitaciones, 50 proveedores, 100 positivos reales):
  A: Baseline Denso Puro (Coseno perfil, top-10)
  C: Híbrido Estructural (Denso + BM25 + Región + Categoría con RRF k=60)
  P: Pipeline Producción Real (Top-50 perfil denso + Top-30 MaxSim keywords-partidas, ordenado por CompatibilityFormula Rc+B+C)
  P+L_Scorer: Producción + Canal Léxico BM25 (Top-30 léxico en recuperación, ordenado por CompatibilityFormula)
  P+L_RRF: Producción + Canal Léxico BM25 (Top-30 léxico, fusión RRF entre posición del Scorer y posición léxica)

Objetivo de la Fase 0:
  Determinar empíricamente si sumar el canal léxico al pipeline actual de producción (P -> P+L)
  produce una mejora estadísticamente significativa (IC 95% > 0) antes de construir la colección en Qdrant.
"""

import argparse
import asyncio
import json
import math
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple
from uuid import NAMESPACE_DNS, uuid5

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

# Coeficientes oficiales calibrados en producción (compat-calib-v1)
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


async def main():
    print("=" * 95)
    print("🚀 SPIKE 2 - FASE 0: EVALUACIÓN DEL PIPELINE REAL vs CANAL LÉXICO (SPARSE BM25)")
    print("=" * 95)

    catalogo = json.loads((TEMP / "catalogo_temporal.json").read_text(encoding="utf-8"))
    provs = json.loads((TEMP / "proveedores_temporal.json").read_text(encoding="utf-8"))
    codes = [d["code"] for d in catalogo]
    idx = {c: i for i, c in enumerate(codes)}
    N = len(codes)
    print(f"Catálogo = {N} licitaciones | Proveedores = {len(provs)} | Positivos Ground Truth = {sum(len(p['ids_positivos']) for p in provs)}")

    # 1. Cargar / asegurar embeddings densos
    emb_path = TEMP / "embeddings_bge_m3_temporal.json"
    cache = json.loads(emb_path.read_text(encoding="utf-8")) if emb_path.exists() else {}

    # Embeddings para multivector (partidas y keywords)
    emb_mv_path = TEMP / "calibracion_embeddings_mv.json"
    cache_mv = json.loads(emb_mv_path.read_text(encoding="utf-8")) if emb_mv_path.exists() else {}

    partidas_catalogo = []
    textos_partidas_necesarios = set()
    for d in catalogo:
        pts = [texto_partida(it) for it in d.get("items", [])]
        partidas_catalogo.append(pts)
        textos_partidas_necesarios.update(pts)

    keywords_necesarias = set()
    for p in provs:
        keywords_necesarias.update(p["perfil"]["keywords"])

    faltan_mv = [t for t in (textos_partidas_necesarios | keywords_necesarias) if t not in cache_mv]
    if faltan_mv:
        print(f"Generando {len(faltan_mv)} embeddings faltantes para partidas/keywords...")
        from app.bootstrap import build_embedding_service, MockEmbeddingService
        emb_svc = build_embedding_service()
        if isinstance(emb_svc, MockEmbeddingService):
            raise SystemExit("El modelo de embeddings cargó como mock.")
        for i in range(0, len(faltan_mv), 32):
            lote = faltan_mv[i:i + 32]
            vecs = await emb_svc.embed(lote)
            for t, v in zip(lote, vecs):
                cache_mv[t] = v
            if (i // 32) % 10 == 0:
                print(f"  progreso partidas/keywords: {min(i + 32, len(faltan_mv))}/{len(faltan_mv)}")
        emb_mv_path.write_text(json.dumps(cache_mv), encoding="utf-8")
        print("Embeddings multivector guardados en caché.")

    # Matriz densa de licitaciones
    M_tenders = np.array([cache[f"doc_{c}"] for c in codes], dtype=np.float32)
    M_tenders /= np.linalg.norm(M_tenders, axis=1, keepdims=True)

    # Índice BM25 sobre licitaciones
    bm25 = BM25([tokens(texto_doc(d)) for d in catalogo])
    cats_doc = [{i["codigo_categoria"] for i in d.get("items", []) if i.get("codigo_categoria")} for d in catalogo]

    # Pre-calcular matrices normalizadas de partidas por licitación
    partidas_vecs_por_doc = []
    for pts in partidas_catalogo:
        if pts:
            v = np.array([cache_mv[t] for t in pts], dtype=np.float32)
            v /= np.linalg.norm(v, axis=1, keepdims=True)
            partidas_vecs_por_doc.append(v)
        else:
            partidas_vecs_por_doc.append(np.empty((0, 1024), dtype=np.float32))

    # Cargar Reranker BGE-M3 ONNX
    reranker = BgeRerankerService()
    print("Reranker BGE-M3 inicializado correctamente.")

    estr = [
        "A_Denso",
        "C_Hibrido_Estructural",
        "P_Produccion",
        "P_plus_L_Scorer",
        "P_plus_L_RRF",
    ]
    Ks = (10, 50, 100, 200)
    res = {e: {"ndcg10": [], "mrr": [], "succ1": [], "p10": [], **{f"recall{k}": [] for k in Ks}} for e in estr}
    latencias = {e: [] for e in estr}

    print("\nEvaluando consultas para los 50 proveedores...")
    for n_p, p in enumerate(provs, 1):
        pos_set = {idx[c] for c in p["ids_positivos"] if c in idx}
        if not pos_set:
            continue

        regiones_prov = p["perfil"]["regions"]
        cats_p = set(p["perfil"]["categorias_historicas"])
        kws = p["perfil"]["keywords"]

        # 1. Vector del perfil
        qv = np.array(cache[f"prov_{p['rut']}"], dtype=np.float32)
        qv /= np.linalg.norm(qv)
        s_dense = M_tenders @ qv

        # 2. BM25 con keywords + sectores (consulta léxica de producción)
        q_lexica = " ".join(kws + p["perfil"]["sectors"])
        s_bm25_lexica = bm25.score(tokens(q_lexica))

        # BM25 spike original (incluía productos históricos)
        q_tok_full = tokens(" ".join(kws + p["perfil"]["productos_historicos"] + p["perfil"]["sectors"]))
        s_bm25_spike = bm25.score(q_tok_full)

        # 3. Matriz de keywords del proveedor normalizada
        K_prov = np.array([cache_mv[k] for k in kws], dtype=np.float32)
        K_prov /= np.linalg.norm(K_prov, axis=1, keepdims=True)

        # 4. MaxSim keywords -> partidas para todo el catálogo (Canal 2 de producción)
        s_maxsim = np.zeros(N, dtype=np.float32)
        for i in range(N):
            P_doc = partidas_vecs_por_doc[i]
            if len(P_doc) > 0:
                sim_matrix = K_prov @ P_doc.T  # (n_kws, n_items)
                s_maxsim[i] = float(sim_matrix.max())

        # Máscara regional estricta (como en producción: filtra dentro de Qdrant)
        mask_region = np.array([are_regions_matching(catalogo[i].get("region") or "", regiones_prov) for i in range(N)])

        # Estrategia A (Denso baseline)
        s_A = np.where(mask_region, s_dense, -1e9)
        rk_A = list(np.argsort(-s_A, kind="stable"))

        # Estrategia C (Híbrido estructural del Spike 2)
        pos_d = posiciones(s_dense)
        pos_b = posiciones(s_bm25_spike)
        boost = np.array([
            (0.5 if are_regions_matching(catalogo[i].get("region") or "", regiones_prov) else 0.0)
            + (1.0 if cats_doc[i] & cats_p else 0.0)
            for i in range(N)
        ], dtype=np.float32)
        pos_boost = posiciones(boost + 1e-6 * s_bm25_spike)
        s_C = rrf([pos_d, pos_b, pos_boost], N)
        rk_C = list(np.argsort(-s_C, kind="stable"))

        # ------------------------------------------------------------------
        # Recuperación de Candidatas para Producción (P y P+L)
        # ------------------------------------------------------------------
        # Canal 1: Top-50 perfil denso con filtro de región
        cand_dense = [i for i in np.argsort(-s_A) if mask_region[i]][:50]

        # Canal 2: Top-30 MaxSim keywords con filtro de región
        s_maxsim_reg = np.where(mask_region, s_maxsim, -1e9)
        cand_maxsim = [i for i in np.argsort(-s_maxsim_reg) if mask_region[i]][:30]

        # Canal 3 (Nuevo): Top-30 BM25 léxico con filtro de región
        s_bm25_reg = np.where(mask_region, s_bm25_lexica, -1e9)
        cand_lexical = [i for i in np.argsort(-s_bm25_reg) if mask_region[i]][:30]

        # Unión deduplicada para P: Canal 1 + Canal 2
        candidatos_P = list(dict.fromkeys(cand_dense + cand_maxsim))

        # Unión deduplicada para P+L: Canal 1 + Canal 2 + Canal 3
        candidatos_PL = list(dict.fromkeys(cand_dense + cand_maxsim + cand_lexical))

        # ------------------------------------------------------------------
        # Scoring con CompatibilityScorer (Rc + B + C)
        # ------------------------------------------------------------------
        q_corta = f"Rubro: {', '.join(p['perfil']['sectors'])}. Productos: {', '.join(kws[:8])}."

        async def puntuar_candidatas(cands: List[int]) -> List[Tuple[int, float]]:
            if not cands:
                return []
            pares = [(uuid5(NAMESPACE_DNS, codes[i]), texto_doc(catalogo[i])[:450]) for i in cands]
            rr_res = await reranker.rerank(query_text=q_corta, candidates=pares, limit=len(pares))
            score_map = {uid: r_score for uid, r_score in rr_res}

            resultados = []
            for i in cands:
                uid = uuid5(NAMESPACE_DNS, codes[i])
                rc = score_map.get(uid, 0.5)

                P_doc = partidas_vecs_por_doc[i]
                if len(P_doc) > 0:
                    sim_mat = K_prov @ P_doc.T
                    b = float(sim_mat.max())
                    c = float(sim_mat.max(axis=0).mean())
                else:
                    b, c = 0.0, 0.0

                final_p = FORMULA.score(reranker_score=rc, best_match=b, coverage=c)
                resultados.append((i, final_p))

            resultados.sort(key=lambda x: x[1], reverse=True)
            return resultados

        # Puntuar P
        t0 = time.perf_counter()
        scored_P = await puntuar_candidatas(candidatos_P)
        lat_P = time.perf_counter() - t0
        rk_P = [i for i, _ in scored_P] + [i for i in range(N) if i not in set(candidatos_P)]

        # Puntuar P+L
        t0 = time.perf_counter()
        scored_PL = await puntuar_candidatas(candidatos_PL)
        lat_PL = time.perf_counter() - t0

        # Variante P+L_Scorer: orden por el score final
        rk_PL_scorer = [i for i, _ in scored_PL] + [i for i in range(N) if i not in set(candidatos_PL)]

        # Variante P+L_RRF: fusión RRF entre posición Scorer y posición léxica BM25
        pos_scorer_PL = {i: rank for rank, (i, _) in enumerate(scored_PL)}
        # ranking BM25 entre los candidatos
        cand_PL_sorted_bm25 = sorted(candidatos_PL, key=lambda i: -s_bm25_lexica[i])
        pos_bm25_PL = {i: rank for rank, i in enumerate(cand_PL_sorted_bm25)}

        fus_PL = sorted(
            candidatos_PL,
            key=lambda i: -(1.0 / (60 + pos_scorer_PL[i] + 1) + 1.0 / (60 + pos_bm25_PL[i] + 1))
        )
        rk_PL_rrf = fus_PL + [i for i in range(N) if i not in set(candidatos_PL)]

        # Guardar latencias
        latencias["P_Produccion"].append(lat_P)
        latencias["P_plus_L_Scorer"].append(lat_PL)
        latencias["P_plus_L_RRF"].append(lat_PL)

        # Evaluar métricas para cada ranking
        rankings = {
            "A_Denso": rk_A,
            "C_Hibrido_Estructural": rk_C,
            "P_Produccion": rk_P,
            "P_plus_L_Scorer": rk_PL_scorer,
            "P_plus_L_RRF": rk_PL_rrf,
        }

        ideal = sorted([2] * len(pos_set) + [0] * 10, reverse=True)
        for e in estr:
            rk = rankings[e]
            rels = [2 if i in pos_set else 0 for i in rk[:200]]
            res[e]["ndcg10"].append(ndcg(rels, ideal, 10))
            first = next((r for r, x in enumerate(rels, 1) if x), None)
            res[e]["mrr"].append(1 / first if first else 0.0)
            res[e]["succ1"].append(1.0 if rels[0] else 0.0)
            res[e]["p10"].append(sum(1 for x in rels[:10] if x) / 10)
            for k in Ks:
                res[e][f"recall{k}"].append(sum(1 for x in rels[:k] if x) / len(pos_set))

        if n_p % 10 == 0:
            print(f"  consultas procesadas: {n_p}/{len(provs)}")

    # ------------------------------------------------------------------
    # Resultados y Significancia
    # ------------------------------------------------------------------
    filas = {e: {k: float(np.mean(v)) for k, v in m.items()} for e, m in res.items()}
    techo_p10 = float(np.mean([min(len(p["ids_positivos"]), 10) / 10 for p in provs]))

    print("\n" + "=" * 115)
    print(f"TABLA COMPARATIVA FASE 0: PRODUCCIÓN REAL vs CANAL LÉXICO (N={len(provs)} | catálogo={N} | techo P@10={techo_p10:.2f})")
    print("=" * 115)
    print(f"{'Estrategia':<24}| NDCG@10 | MRR    | Succ@1 | P@10   | R@10   | R@50   | R@100  | R@200  | Latencia Scorer")
    for e, r in filas.items():
        lat_str = f"{np.mean(latencias[e]):.2f}s" if latencias[e] else "—"
        print(f"{e:<24}| {r['ndcg10']:.4f}  | {r['mrr']:.4f} | {r['succ1']:.4f} | {r['p10']:.4f} | {r['recall10']:.4f} | {r['recall50']:.4f} | {r['recall100']:.4f} | {r['recall200']:.4f} | {lat_str}")

    # Comparaciones estadísticas
    comps = [
        ("A_Denso", "P_Produccion"),
        ("P_Produccion", "P_plus_L_Scorer"),
        ("P_Produccion", "P_plus_L_RRF"),
        ("P_Produccion", "C_Hibrido_Estructural"),
    ]
    raws, det = [], []
    for a, b in comps:
        d = np.array(res[b]["ndcg10"]) - np.array(res[a]["ndcg10"])
        try:
            pval = 1.0 if np.all(d == 0) else float(wilcoxon(d).pvalue)
        except Exception:
            pval = 1.0
        raws.append(pval)
        det.append((a, b, float(d.mean()), *boot_pareado(d)))
    adj = holm(raws)

    print("\n" + "=" * 115)
    print("SIGNIFICANCIA ESTADÍSTICA (NDCG@10 - Wilcoxon pareado + Holm-Bonferroni, Bootstrap 95% IC)")
    print("=" * 115)
    sig_out = []
    for (a, b, m, lo, hi), pr, pa in zip(det, raws, adj):
        es_sig = pa < 0.05 and lo > 0
        marca = "★ MEJORA SIGNIFICATIVA" if es_sig else ("ns" if pa >= 0.05 else "neutral")
        print(f"  {b} vs {a}:")
        print(f"    Δ = {m:+.4f} | IC 95% = [{lo:+.4f}, {hi:+.4f}] | p = {pr:.4f} | p_holm = {pa:.4f}  [{marca}]")
        sig_out.append({
            "comparacion": f"{b} vs {a}",
            "delta": round(m, 4),
            "ci95": [round(lo, 4), round(hi, 4)],
            "p": round(pr, 4),
            "p_holm": round(pa, 4),
            "es_significativo": es_sig,
        })

    # Decisión de Fase 0
    mejora_scorer = next(s for s in sig_out if s["comparacion"] == "P_plus_L_Scorer vs P_Produccion")
    mejora_rrf = next(s for s in sig_out if s["comparacion"] == "P_plus_L_RRF vs P_Produccion")

    print("\n" + "=" * 115)
    print("CONCLUSIÓN DE LA FASE 0:")
    if mejora_scorer["ci95"][0] > 0 or mejora_rrf["ci95"][0] > 0:
        print("  -> APROBADO: El canal léxico produce una ganancia estadísticamente positiva (IC95 > 0).")
        print("     Se justifica continuar a la Fase 1 (construir colección Qdrant tender_lexical).")
    else:
        print(f"  -> RESULTADO: Δ = {mejora_scorer['delta']:+.4f} (Scorer) / {mejora_rrf['delta']:+.4f} (RRF).")
        print("     Revisar si el canal léxico aporta en Recall o si la precisión actual de P ya absorbe la señal.")
    print("=" * 115)

    out = {
        "n_consultas": len(provs),
        "n_catalogo": N,
        "metricas": {e: {k: round(v, 4) for k, v in r.items()} for e, r in filas.items()},
        "latencias_segundos": {e: round(float(np.mean(latencias[e])), 3) for e in latencias if latencias[e]},
        "significancia": sig_out,
    }
    salida_path = TEMP / "metricas_benchmark_fase0.json"
    salida_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResultados guardados en {salida_path}")


if __name__ == "__main__":
    asyncio.run(main())
