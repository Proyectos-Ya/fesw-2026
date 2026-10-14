"""
Spike 2 - Paso E: Métricas graduadas con el juez sobre el pool común (Tabla 2).

Relevancia usada: max(juicio del LLM, 2 si la OC es una adjudicación posterior real).
El ideal para NDCG se calcula sobre el pool juzgado (todo lo que alguna estrategia puso en su top-10 + adjudicaciones).
Se reportan dos umbrales de precisión: rel >= 1 (familia de producto) y rel = 2 (producto exacto).
"""

import json
import math
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import numpy as np
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[2]
TEMP = ROOT / "spikes" / "dataset_compra_agil" / "data" / "temporal"


def ndcg(rels, ideal, k):
    dcg = lambda r: sum((2 ** x - 1) / math.log2(i + 2) for i, x in enumerate(r[:k]) if x > 0)
    idcg = dcg(ideal)
    return dcg(rels) / idcg if idcg else 0.0


def holm(ps):
    n = len(ps); orden = sorted(range(n), key=lambda i: ps[i]); adj = [0.0] * n; mx = 0.0
    for r, i in enumerate(orden):
        mx = max(mx, min(1.0, ps[i] * (n - r))); adj[i] = mx
    return adj


def main():
    provs = {p["rut"]: p for p in json.loads((TEMP / "proveedores_temporal.json").read_text(encoding="utf-8"))}
    met = json.loads((TEMP / "metricas_benchmark_temporal.json").read_text(encoding="utf-8"))
    juicios = json.loads((TEMP / "juicios_pool_temporal.json").read_text(encoding="utf-8"))
    tops = met["rankings_top20"]
    estr = list(next(iter(tops.values())).keys())

    res = {e: {"ndcg10": [], "p10_ge1": [], "p10_eq2": [], "succ1_ge1": [], "cobertura": []} for e in estr}
    for rut, por_estr in tops.items():
        gt = set(provs[rut]["ids_positivos"])

        def rel(c):
            if c in gt:
                return 2
            j = juicios.get(f"{rut}::{c}")
            return j["rel"] if j else 0

        pool = {c for lista in por_estr.values() for c in lista[:10]} | gt
        ideal = sorted((rel(c) for c in pool), reverse=True)
        for e, lista in por_estr.items():
            r = [rel(c) for c in lista[:10]]
            res[e]["ndcg10"].append(ndcg(r, ideal, 10))
            res[e]["p10_ge1"].append(sum(1 for x in r if x >= 1) / 10)
            res[e]["p10_eq2"].append(sum(1 for x in r if x == 2) / 10)
            res[e]["succ1_ge1"].append(1.0 if r and r[0] >= 1 else 0.0)
            res[e]["cobertura"].append(sum(1 for c in lista[:10] if c in gt or f"{rut}::{c}" in juicios) / 10)

    filas = {e: {k: float(np.mean(v)) for k, v in m.items()} for e, m in res.items()}
    print(f"MÉTRICAS CON JUEZ (pool común, N={len(tops)})")
    print(f"{'Estrategia':<26}| NDCG@10 | P@10(rel>=1) | P@10(rel=2) | Succ@1(rel>=1) | cobertura de juicios")
    for e, r in filas.items():
        print(f"{e:<26}| {r['ndcg10']:.4f}  | {r['p10_ge1']:.4f}       | {r['p10_eq2']:.4f}      | {r['succ1_ge1']:.4f}         | {r['cobertura']:.3f}")

    comps = [(estr[0], b) for b in estr[1:]] + [("B_Hibrido_BM25_RRF", "C_Hibrido_Estructural")]
    raws, det = [], []
    rng = np.random.default_rng(42)
    for a, b in comps:
        d = np.array(res[b]["ndcg10"]) - np.array(res[a]["ndcg10"])
        try:
            p = 1.0 if np.all(d == 0) else float(wilcoxon(d).pvalue)
        except Exception:
            p = 1.0
        boots = [rng.choice(d, size=len(d), replace=True).mean() for _ in range(5000)]
        raws.append(p); det.append((a, b, float(d.mean()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))))
    adj = holm(raws)
    print("\nSIGNIFICANCIA (NDCG@10 con juez)")
    sig = []
    for (a, b, m, lo, hi), p, pa in zip(det, raws, adj):
        print(f"  {b} vs {a}: Δ={m:+.4f} IC95=[{lo:+.4f},{hi:+.4f}] p={p:.4f} p_holm={pa:.4f} {'*' if pa < 0.05 else 'ns'}")
        sig.append({"comparacion": f"{b} vs {a}", "delta": round(m, 4), "ci95": [round(lo, 4), round(hi, 4)], "p": round(p, 4), "p_holm": round(pa, 4)})

    (TEMP / "metricas_con_juez_temporal.json").write_text(
        json.dumps({"metricas": {e: {k: round(v, 4) for k, v in r.items()} for e, r in filas.items()}, "significancia": sig}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
