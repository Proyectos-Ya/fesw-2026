"""
Spike 2 - Paso C: Benchmark con split temporal y catálogo natural.

Estrategias (todas sobre el mismo catálogo y las mismas consultas):
  A  Denso BGE-M3 (baseline producción).
  B  Híbrido: denso + BM25 (tokenizado, sin tildes, stemming ligero) fusionados por RRF (sin pesos ad hoc).
  C  B + boost estructural: región canónica (are_regions_matching) y categoría UNSPSC vista en el historial.
  E  Multi-consulta: una consulta densa por producto histórico + una por el perfil; puntaje = máximo (fusionado con B por RRF).
  D  Etapa 2: reranker BGE sobre el top-100 de C (recall del primer estadio es su techo), fusión RRF.

Métricas:
  * Recall@K por etapa (10/50/100/200) sobre relevancia 2: techo de lo que puede lograr cualquier reranker.
  * NDCG@10, MRR, Success@1, P@10 (techo = nº de positivos/10) con relevancia 2 (adjudicaciones posteriores).
  * Significancia: Wilcoxon pareado + Holm + bootstrap pareado sobre la diferencia por consulta.
"""

import argparse
import asyncio
import json
import math
import re
import sys
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
from app.shared.regions import are_regions_matching  # noqa: E402

TEMP = ROOT / "spikes" / "dataset_compra_agil" / "data" / "temporal"
STOP = set("de la el en y a los las del por para con un una al se que o su sus lo como mas mas son sin".split())


# ---------------------------------------------------------------- texto
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
    items = "; ".join(f"{i['nombre']} ({i['descripcion'][:120]})" if i["descripcion"] else i["nombre"] for i in d["items"][:8])
    cats = "; ".join(sorted({i["categoria"] for i in d["items"] if i["categoria"]})[:4])
    return f"Partidas: {items}. {d['name']}. {d['description']}. Categoría: {cats}"[:1800]


def texto_perfil(p: Dict[str, Any]) -> str:
    pf = p["perfil"]
    return f"Rubros: {', '.join(pf['sectors'])}. {pf['description']} Productos: {', '.join(pf['keywords'])}."


# ---------------------------------------------------------------- BM25
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


# ---------------------------------------------------------------- métricas
def ndcg(rels: List[int], ideal: List[int], k: int) -> float:
    dcg = lambda r: sum((2 ** x - 1) / math.log2(i + 2) for i, x in enumerate(r[:k]) if x > 0)
    idcg = dcg(ideal)
    return dcg(rels) / idcg if idcg else 0.0


def rrf(rank_lists: List[List[int]], n: int, k: int = 60) -> np.ndarray:
    """rank_lists: por lista, posiciones (0-based) de cada doc en el orden; devuelve puntaje RRF por doc."""
    s = np.zeros(n, dtype=np.float32)
    for pos in rank_lists:
        s += 1.0 / (k + pos + 1)
    return s


def posiciones(scores: np.ndarray) -> np.ndarray:
    order = np.argsort(-scores, kind="stable")
    pos = np.empty(len(scores), dtype=np.int64)
    pos[order] = np.arange(len(scores))
    return pos


# ---------------------------------------------------------------- estadística
def boot_pareado(diffs: np.ndarray, reps=5000, seed=42) -> Tuple[float, float]:
    rng = np.random.default_rng(seed)
    m = [rng.choice(diffs, size=len(diffs), replace=True).mean() for _ in range(reps)]
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def holm(ps: List[float]) -> List[float]:
    n = len(ps); orden = sorted(range(n), key=lambda i: ps[i]); adj = [0.0] * n; mx = 0.0
    for r, i in enumerate(orden):
        mx = max(mx, min(1.0, ps[i] * (n - r))); adj[i] = mx
    return adj


# ---------------------------------------------------------------- main
async def main(usar_reranker: bool, cand_rerank: int):
    catalogo = json.loads((TEMP / "catalogo_temporal.json").read_text(encoding="utf-8"))
    provs = json.loads((TEMP / "proveedores_temporal.json").read_text(encoding="utf-8"))
    codes = [d["code"] for d in catalogo]
    idx = {c: i for i, c in enumerate(codes)}
    N = len(codes)
    print(f"Catálogo={N} | proveedores={len(provs)} | positivos={sum(len(p['ids_positivos']) for p in provs)}")

    # Embeddings BGE-M3 locales (cache en disco)
    emb_path = TEMP / "embeddings_bge_m3_temporal.json"
    cache = json.loads(emb_path.read_text(encoding="utf-8")) if emb_path.exists() else {}
    svc = None  # se carga solo si faltan embeddings (evita tener BGE-M3 y el reranker en memoria a la vez)

    async def asegurar(clave_texto: List[Tuple[str, str]]):
        nonlocal svc
        faltan = [(k, t) for k, t in clave_texto if k not in cache]
        if faltan and svc is None:
            from app.infrastructure.services.bge_m3_embedding_service import BgeM3EmbeddingService
            svc = BgeM3EmbeddingService()
        for i in range(0, len(faltan), 32):
            lote = faltan[i:i + 32]
            vecs = await svc.embed([t for _, t in lote])
            for (k, _), v in zip(lote, vecs):
                cache[k] = v
            print(f"  embeddings {min(i + 32, len(faltan))}/{len(faltan)}")
        if faltan:
            emb_path.write_text(json.dumps(cache), encoding="utf-8")

    pedidos = [(f"doc_{d['code']}", texto_doc(d)) for d in catalogo]
    pedidos += [(f"prov_{p['rut']}", texto_perfil(p)) for p in provs]
    for p in provs:
        for j, prod in enumerate(dict.fromkeys(p["perfil"]["productos_historicos"])):
            pedidos.append((f"prod_{p['rut']}_{j}", prod))
    await asegurar(pedidos)

    M = np.array([cache[f"doc_{c}"] for c in codes], dtype=np.float32)
    M /= np.linalg.norm(M, axis=1, keepdims=True)
    bm25 = BM25([tokens(texto_doc(d)) for d in catalogo])
    cats_doc = [{i["codigo_categoria"] for i in d["items"] if i.get("codigo_categoria")} for d in catalogo]

    reranker = None
    if usar_reranker:
        from app.infrastructure.services.bge_reranker_service import BgeRerankerService
        reranker = BgeRerankerService()

    estr = ["A_Denso", "B_Hibrido_BM25_RRF", "C_Hibrido_Estructural", "E_MultiConsulta"] + (["D_Reranker_Top%d" % cand_rerank] if reranker else [])
    Ks = (10, 50, 100, 200)
    res = {e: {"ndcg10": [], "mrr": [], "succ1": [], "p10": [], **{f"recall{k}": [] for k in Ks}} for e in estr}
    top_export: Dict[str, Dict[str, List[str]]] = {}  # rut -> estrategia -> top-20 (para armar el pool de juicios)

    for n_p, p in enumerate(provs, 1):
        pos_set = {idx[c] for c in p["ids_positivos"] if c in idx}
        if not pos_set:
            continue
        qv = np.array(cache[f"prov_{p['rut']}"], dtype=np.float32); qv /= np.linalg.norm(qv)
        s_dense = M @ qv
        q_tok = tokens(" ".join(p["perfil"]["keywords"] + p["perfil"]["productos_historicos"] + p["perfil"]["sectors"]))
        s_bm25 = bm25.score(q_tok)
        pos_d, pos_b = posiciones(s_dense), posiciones(s_bm25)
        s_B = rrf([pos_d, pos_b], N)

        reg = p["perfil"]["regions"]
        cats_p = set(p["perfil"]["categorias_historicas"])
        boost = np.array([
            (0.5 if are_regions_matching(catalogo[i].get("region") or "", reg) else 0.0)
            + (1.0 if cats_doc[i] & cats_p else 0.0)
            for i in range(N)
        ], dtype=np.float32)
        pos_boost = posiciones(boost + 1e-6 * s_B)  # desempata por B
        s_C = rrf([pos_d, pos_b, pos_boost], N)

        vecs_prod = [np.array(cache[k], dtype=np.float32) for k in (f"prod_{p['rut']}_{j}" for j in range(len(dict.fromkeys(p["perfil"]["productos_historicos"]))))]
        if vecs_prod:
            Q = np.array(vecs_prod); Q /= np.linalg.norm(Q, axis=1, keepdims=True)
            s_multi = (M @ Q.T).max(axis=1)
        else:
            s_multi = s_dense
        s_E = rrf([pos_d, pos_b, posiciones(s_multi)], N)

        scores = {"A_Denso": s_dense, "B_Hibrido_BM25_RRF": s_B, "C_Hibrido_Estructural": s_C, "E_MultiConsulta": s_E}
        rankings = {e: list(np.argsort(-s, kind="stable")) for e, s in scores.items()}

        if reranker:
            top = rankings["C_Hibrido_Estructural"][:cand_rerank]
            q_corta = f"{', '.join(p['perfil']['sectors'])}. Productos: {', '.join(p['perfil']['keywords'][:8])}"
            pares = [(uuid5(NAMESPACE_DNS, codes[i]), texto_doc(catalogo[i])[:450]) for i in top]
            rr = await reranker.rerank(query_text=q_corta, candidates=pares, limit=len(pares))
            pos_rr = {uid: r for r, (uid, _) in enumerate(rr)}
            pos_c = {i: r for r, i in enumerate(top)}
            fus = sorted(top, key=lambda i: -(1 / (60 + pos_c[i] + 1) + 1 / (60 + pos_rr[uuid5(NAMESPACE_DNS, codes[i])] + 1)))
            rankings[estr[-1]] = fus + [i for i in rankings["C_Hibrido_Estructural"] if i not in set(top)]

        top_export[p["rut"]] = {e: [codes[i] for i in rankings[e][:20]] for e in estr}
        for e in estr:
            rk = rankings[e]
            rels = [2 if i in pos_set else 0 for i in rk[:200]]
            ideal = sorted([2] * len(pos_set) + [0] * 10, reverse=True)
            res[e]["ndcg10"].append(ndcg(rels, ideal, 10))
            first = next((r for r, x in enumerate(rels, 1) if x), None)
            res[e]["mrr"].append(1 / first if first else 0.0)
            res[e]["succ1"].append(1.0 if rels[0] else 0.0)
            res[e]["p10"].append(sum(1 for x in rels[:10] if x) / 10)
            for k in Ks:
                res[e][f"recall{k}"].append(sum(1 for x in rels[:k] if x) / len(pos_set))
        if n_p % 10 == 0:
            print(f"  consultas {n_p}/{len(provs)}")

    filas = {e: {k: float(np.mean(v)) for k, v in m.items()} for e, m in res.items()}
    techo_p10 = float(np.mean([min(len(p["ids_positivos"]), 10) / 10 for p in provs]))
    print("\n" + "=" * 110)
    print(f"MÉTRICAS DURAS (rel=2: adjudicaciones posteriores al historial) | N={len(provs)} | catálogo={N} | techo P@10={techo_p10:.2f}")
    print(f"{'Estrategia':<26}| NDCG@10 | MRR    | Succ@1 | P@10   | R@10   | R@50   | R@100  | R@200")
    for e, r in filas.items():
        print(f"{e:<26}| {r['ndcg10']:.4f}  | {r['mrr']:.4f} | {r['succ1']:.4f} | {r['p10']:.4f} | {r['recall10']:.4f} | {r['recall50']:.4f} | {r['recall100']:.4f} | {r['recall200']:.4f}")

    comps = [(a, b) for a in estr for b in estr if estr.index(a) < estr.index(b) and a == "A_Denso"] + [("B_Hibrido_BM25_RRF", "C_Hibrido_Estructural")]
    raws, det = [], []
    for a, b in comps:
        d = np.array(res[b]["ndcg10"]) - np.array(res[a]["ndcg10"])
        try:
            pval = 1.0 if np.all(d == 0) else float(wilcoxon(d).pvalue)
        except Exception:
            pval = 1.0
        raws.append(pval); det.append((a, b, float(d.mean()), *boot_pareado(d)))
    adj = holm(raws)
    print("\nSIGNIFICANCIA (NDCG@10, Wilcoxon pareado + Holm, bootstrap pareado 95% sobre la diferencia por consulta)")
    for (a, b, m, lo, hi), pr, pa in zip(det, raws, adj):
        print(f"  {b} vs {a}: Δ={m:+.4f}  IC95=[{lo:+.4f},{hi:+.4f}]  p={pr:.4f}  p_holm={pa:.4f}  {'*' if pa < 0.05 else 'ns'}")

    out = {
        "n_consultas": len(provs), "n_catalogo": N, "techo_p10": techo_p10,
        "metricas": {e: {k: round(v, 4) for k, v in r.items()} for e, r in filas.items()},
        "significancia": [{"comparacion": f"{b} vs {a}", "delta": round(m, 4), "ci95": [round(lo, 4), round(hi, 4)], "p": round(pr, 4), "p_holm": round(pa, 4)} for (a, b, m, lo, hi), pr, pa in zip(det, raws, adj)],
        "rankings_top20": top_export,
        "por_consulta_ndcg10": {e: [round(x, 4) for x in res[e]["ndcg10"]] for e in estr},
    }
    (TEMP / "metricas_benchmark_temporal.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGuardado en {TEMP / 'metricas_benchmark_temporal.json'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-reranker", action="store_true")
    ap.add_argument("--cand-rerank", type=int, default=100)
    a = ap.parse_args()
    asyncio.run(main(not a.sin_reranker, a.cand_rerank))
