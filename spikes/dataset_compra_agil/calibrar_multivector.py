"""
Spike 2 - Calibración con señales multivector (paso 2).

La calibración con los puntajes actuales (calibrar_compatibilidad.py) mostró que R (reranker) y
S (coseno de Qdrant) casi no separan relevante de irrelevante entre las candidatas del top
(AUC ≈ 0,55). Acá se agregan señales de "qué calza con qué" y se reajusta:

  R      reranker actual, ahora puntuado por par (sin la dependencia del lote)
  Rc     reranker con consulta corta: "Rubro: … Productos: …" (keywords) en vez del perfil completo
  S      coseno de Qdrant perfil ↔ licitación (del cálculo anterior; no depende del lote)
  B      mejor calce keyword ↔ partida:  maxⱼ maxᵢ cos(kᵢ, pⱼ)
  C      cobertura: media sobre partidas de maxᵢ cos(kᵢ, pⱼ)   (qué parte de lo pedido cubre)
  K      MaxSim normalizado (lo que devolvería Qdrant multivector): mediaᵢ maxⱼ cos(kᵢ, pⱼ)
  D      mejor calce descripción ↔ partida: maxⱼ cos(desc, pⱼ)

Los cosenos se calculan localmente con los mismos embeddings BGE-M3 que usaría Qdrant; en
producción B/C/K saldrían de un multivector en Qdrant (comparator MAX_SIM) o de pedir con
`with_vectors` las partidas del top-50.

Uso:  python calibrar_multivector.py
"""

import asyncio
import json
import math
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "monorepo" / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

TEMP = ROOT / "spikes" / "dataset_compra_agil" / "data" / "temporal"
FEATS_BASE = TEMP / "calibracion_features.json"
EMB_CACHE = TEMP / "calibracion_embeddings_mv.json"
FEATS_MV = TEMP / "calibracion_features_mv.json"
SALIDA = TEMP / "calibracion_multivector_resultados.json"


def logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def texto_partida(item: dict) -> str:
    desc = (item.get("description") or "").strip()
    return f"{item['name']}: {desc[:200]}" if desc else item["name"]


async def calcular():
    import cargar_catalogo_supabase as carga
    from app.application.services.text_builder import TextBuilder
    from app.bootstrap import MockEmbeddingService, build_embedding_service
    from app.domain.entities.supplier import Supplier
    from app.domain.entities.tender import Tender, TenderItem

    base = json.loads(FEATS_BASE.read_text(encoding="utf-8"))
    provs = {p["rut"]: p for p in json.loads((TEMP / "proveedores_temporal.json").read_text(encoding="utf-8"))}
    regs = {r["code"]: r for r in carga.construir()}
    codes = sorted({f["code"] for f in base})

    # ---- embeddings de keywords, descripciones y partidas (con caché)
    cache = json.loads(EMB_CACHE.read_text(encoding="utf-8")) if EMB_CACHE.exists() else {}
    textos = set()
    for p in provs.values():
        textos.update(p["perfil"]["keywords"])
        textos.add(p["perfil"]["description"])
    for c in codes:
        textos.update(texto_partida(i) for i in regs[c]["items"])
    faltan = sorted(t for t in textos if t not in cache)
    if faltan:
        emb = build_embedding_service()
        if isinstance(emb, MockEmbeddingService):
            raise SystemExit("El modelo de embeddings no cargó (mock).")
        faltan.sort(key=len)
        for i in range(0, len(faltan), 16):
            lote = faltan[i:i + 16]
            for t, v in zip(lote, await emb.embed(lote)):
                cache[t] = v
            if (i // 16) % 20 == 0:
                print(f"  embeddings {i + len(lote)}/{len(faltan)}")
                EMB_CACHE.write_text(json.dumps(cache), encoding="utf-8")
        EMB_CACHE.write_text(json.dumps(cache), encoding="utf-8")
        del emb

    def M(ts):
        a = np.array([cache[t] for t in ts], dtype=np.float32)
        return a / np.linalg.norm(a, axis=1, keepdims=True)

    # ---- reranker por par: perfil completo (como producción) y consulta corta
    from app.infrastructure.services.bge_reranker_service import BgeRerankerService

    rer = BgeRerankerService()
    tb = TextBuilder()
    filas = []
    por_rut: dict[str, list[dict]] = {}
    for f in base:
        por_rut.setdefault(f["rut"], []).append(f)
    for n, (rut, fs) in enumerate(por_rut.items(), 1):
        pf = provs[rut]["perfil"]
        sup = Supplier(rut=rut, legal_name=provs[rut]["nombre"], description=pf["description"],
                       sectors=pf["sectors"], keywords=pf["keywords"], regions=pf["regions"])
        q_larga = tb.build_from_supplier(sup)
        q_corta = f"Rubro: {', '.join(pf['sectors'])}. Productos: {', '.join(pf['keywords'])}."
        K = M(pf["keywords"])
        d = M([pf["description"]])[0]
        for f in fs:
            r = regs[f["code"]]
            t = Tender(id=r["tender_id"], code=f["code"], name=r["name"], description=r["description"], status_id=2,
                       published_at=r["published_at"], closing_at=r["closing_at"], last_change_at=r["now"],
                       buyer_rut=r["buyer_rut"], buyer_unit=r["buyer_unit"])
            t.items = [TenderItem(tender_id=r["tender_id"], product_code=i["product_code"], name=i["name"],
                                  description=i["description"], quantity=i["quantity"], unit_of_measure=i["unit"])
                       for i in r["items"]]
            doc = tb.build_from_tender(tender=t, items=t.items)
            R = (await rer.rerank(q_larga, [(t.id, doc)], 1))[0][1]
            Rc = (await rer.rerank(q_corta, [(t.id, doc)], 1))[0][1]
            partidas = list(dict.fromkeys(texto_partida(i) for i in r["items"]))
            P = M(partidas)
            sim = K @ P.T  # keywords × partidas
            filas.append({**f, "R": R, "Rc": Rc,
                          "B": float(sim.max()), "C": float(sim.max(axis=0).mean()),
                          "K": float(sim.max(axis=1).mean()), "D": float((P @ d).max())})
        print(f"  proveedores {n}/{len(por_rut)}")
    FEATS_MV.write_text(json.dumps(filas, ensure_ascii=False), encoding="utf-8")
    return filas


def main():
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from sklearn.model_selection import GroupKFold

    from calibrar_compatibilidad import ece, tabla_confiabilidad

    filas = json.loads(FEATS_MV.read_text(encoding="utf-8")) if FEATS_MV.exists() else asyncio.run(calcular())
    rel = np.array([f["rel"] for f in filas])
    y1, y2 = (rel >= 1).astype(int), (rel == 2).astype(int)
    g = np.array([f["rut"] for f in filas])
    col = lambda k, tr=(lambda x: x): np.array([tr(f[k]) for f in filas])  # noqa: E731

    print(f"Pares: {len(filas)} | rel 0/1/2 = {np.bincount(rel, minlength=3).tolist()}")
    print("\nAUC de cada señal sola (rel≥1) y media por etiqueta 0/1/2:")
    for k in ("R", "Rc", "S", "B", "C", "K", "D"):
        v = col(k)
        print(f"  {k:<3} AUC={roc_auc_score(y1, v):.3f}   " + " / ".join(f"{v[rel == e].mean():.3f}" for e in (0, 1, 2)))

    feats = {
        "R": [col("R", logit)],
        "Rc": [col("Rc", logit)],
        "B+C": [col("B"), col("C")],
        "Rc+B+C": [col("Rc", logit), col("B"), col("C")],
        "Rc+B+C+S": [col("Rc", logit), col("B"), col("C"), col("S")],
        "Rc+B+C+K+D+S": [col("Rc", logit), col("B"), col("C"), col("K"), col("D"), col("S")],
    }
    gkf = GroupKFold(n_splits=5)

    def oof(X, y):
        p = np.zeros(len(y))
        for tr, te in gkf.split(X, y, g):
            p[te] = LogisticRegression(C=1.0, max_iter=1000).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        return p

    res = {"binario": [], "ordinal": {}}
    print(f"\n{'modelo':<14}| AUC    | Brier  | ECE    | prec≥70% | %≥70% | ordinal 0/1/2 (ideal 0/.5/1) | MAE")
    for nombre, cols in feats.items():
        X = np.column_stack(cols)
        p1 = oof(X, y1)
        p2 = np.minimum(oof(X, y2), p1)
        pct = 0.5 * p1 + 0.5 * p2
        verdes = pct >= 0.70
        fila = {
            "modelo": nombre, "auc": round(float(roc_auc_score(y1, p1)), 4),
            "brier": round(float(brier_score_loss(y1, p1)), 4), "ece": round(ece(p1, y1), 4),
            "prec_verdes_70": round(float(y1[verdes].mean()), 3) if verdes.any() else None,
            "pct_verdes_70": round(float(verdes.mean()), 3),
            "ordinal_media": [round(float(pct[rel == e].mean()), 3) for e in (0, 1, 2)],
            "ordinal_mae": round(float(np.abs(pct - rel / 2).mean()), 4),
        }
        res["binario"].append(fila)
        print(f"{nombre:<14}| {fila['auc']:.4f} | {fila['brier']:.4f} | {fila['ece']:.4f} | {str(fila['prec_verdes_70']):<8} | {fila['pct_verdes_70']:<5} | "
              f"{' / '.join(f'{m:.2f}' for m in fila['ordinal_media']):<28} | {fila['ordinal_mae']}")
        if nombre == "Rc+B+C":
            res["confiabilidad_ordinal_Rc+B+C"] = tabla_confiabilidad(pct, rel / 2)

    for nombre in ("Rc+B+C", "Rc+B+C+S"):
        X = np.column_stack(feats[nombre])
        m1 = LogisticRegression(C=1.0, max_iter=1000).fit(X, y1)
        m2 = LogisticRegression(C=1.0, max_iter=1000).fit(X, y2)
        res.setdefault("coeficientes", {})[nombre] = {
            "entradas": nombre.split("+"),
            "rel_ge1": {"intercepto": float(m1.intercept_[0]), "coef": m1.coef_[0].tolist()},
            "rel_eq2": {"intercepto": float(m2.intercept_[0]), "coef": m2.coef_[0].tolist()},
        }
    print("\nCoeficientes:", json.dumps(res["coeficientes"], indent=1))
    SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Guardado en {SALIDA}")


if __name__ == "__main__":
    main()
