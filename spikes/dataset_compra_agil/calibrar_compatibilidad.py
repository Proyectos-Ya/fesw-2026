"""
Spike 2 - Calibración del porcentaje de compatibilidad.

Pregunta: ¿se puede construir un porcentaje que signifique algo a partir de los puntajes que el
pipeline de producción YA calcula (similitud coseno de Qdrant y reranker), sin vectores nuevos?

Datos: los 1.146 pares (proveedor, licitación) del pool común juzgados a ciegas en escala 0/1/2
(juicios_pool_temporal.json; acuerdo entre dos jueces LLM κ=0,82, no validado contra humanos).
Es la población correcta para calibrar: son las candidatas que el ranking muestra arriba.

Para cada par se calculan, igual que en producción:
  S  = similitud coseno que devuelve Qdrant entre el vector del proveedor (_build_supplier_text,
       BGE-M3) y el de la licitación (ya indexado en Qdrant).
  R  = puntaje del reranker BgeRerankerService (query = TextBuilder.build_from_supplier,
       doc = TextBuilder.build_from_tender), con su Platt actual (T=1,5, b=1,5).
  P0 = puntaje final actual: FieldWeightingService (0,5·R + 0,25·rubro + 0,25·keywords).
  Lx = parte léxica de P0: (P0 − 0,5·R) / 0,5  ∈ [0, 1].

Modelos comparados con validación cruzada agrupada por proveedor (GroupKFold, 5 pliegues):
  actual : P0 tal cual.
  R      : σ(a + b·logit(R))               ← equivale a recalibrar T y b del reranker
  R+S    : σ(a + b·logit(R) + c·S)
  R+S+Lx : σ(a + b·logit(R) + c·S + d·Lx)

Porcentaje ordinal (exacto vs afín): % = 50·P(rel≥1) + 50·P(rel=2), dos logísticas con las mismas
entradas. Así un calce exacto tiende a 100%, uno afín a ~50% y uno ajeno a 0%.

Uso (Qdrant local levantado con las 1.176 licitaciones indexadas):
  python calibrar_compatibilidad.py
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
CACHE = TEMP / "calibracion_features.json"
SALIDA = TEMP / "calibracion_resultados.json"


def logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


# --------------------------------------------------------------------------- features
async def calcular_features() -> list[dict]:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import FieldCondition, Filter, HasIdCondition  # noqa: F401

    import cargar_catalogo_supabase as carga
    from app.application.services.text_builder import TextBuilder
    from app.application.use_cases.supplier.create_supplier import _build_supplier_text
    from app.bootstrap import MockEmbeddingService, build_embedding_service
    from app.config import settings
    from app.domain.entities.supplier import Supplier
    from app.domain.entities.tender import Tender, TenderItem
    from app.infrastructure.services.field_weighting_service import FieldWeightingService

    provs = {p["rut"]: p for p in json.loads((TEMP / "proveedores_temporal.json").read_text(encoding="utf-8"))}
    juicios = json.loads((TEMP / "juicios_pool_temporal.json").read_text(encoding="utf-8"))
    regs = {r["code"]: r for r in carga.construir()}

    # Entidades de dominio, como las ve producción
    suppliers = {}
    for rut, p in provs.items():
        pf = p["perfil"]
        suppliers[rut] = Supplier(
            rut=rut, legal_name=p["nombre"], description=pf["description"],
            regions=pf["regions"], sectors=pf["sectors"], keywords=pf["keywords"],
        )
    tenders = {}
    for code, r in regs.items():
        t = Tender(
            id=r["tender_id"], code=code, name=r["name"], description=r["description"], status_id=2,
            status_code="publicada", published_at=r["published_at"], closing_at=r["closing_at"],
            last_change_at=r["now"], buyer_rut=r["buyer_rut"], buyer_unit=r["buyer_unit"],
        )
        t.items = [TenderItem(tender_id=r["tender_id"], product_code=i["product_code"], name=i["name"],
                              description=i["description"], quantity=i["quantity"], unit_of_measure=i["unit"])
                   for i in r["items"]]
        tenders[code] = t

    pares: dict[str, list[str]] = {}
    for k in juicios:
        rut, code = k.split("::")
        pares.setdefault(rut, []).append(code)

    # S: vector del proveedor (BGE-M3, mismo constructor que la API) y puntaje que devuelve Qdrant
    emb = build_embedding_service()
    if isinstance(emb, MockEmbeddingService):
        raise SystemExit("El modelo de embeddings no cargó (mock).")
    ruts = list(pares)
    vecs = await emb.embed([_build_supplier_text(suppliers[r]) for r in ruts])
    qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    S: dict[str, float] = {}
    for rut, v in zip(ruts, vecs):
        ids = [str(tenders[c].id) for c in pares[rut]]
        res = await qdrant.query_points(
            collection_name="tenders", query=v, using="tender",
            query_filter=Filter(must=[HasIdCondition(has_id=ids)]), limit=len(ids), with_payload=False,
        )
        por_id = {str(p.id): p.score for p in res.points}
        for c in pares[rut]:
            S[f"{rut}::{c}"] = por_id[str(tenders[c].id)]
    del emb

    # R y P0: reranker y ponderación de producción
    from app.infrastructure.services.bge_reranker_service import BgeRerankerService

    rer = BgeRerankerService()
    tb = TextBuilder()
    fw = FieldWeightingService()
    filas = []
    for n, (rut, codes) in enumerate(pares.items(), 1):
        sup = suppliers[rut]
        cands = [(tenders[c].id, tb.build_from_tender(tender=tenders[c], items=tenders[c].items)) for c in codes]
        R = {}
        for i in range(0, len(cands), 8):
            for tid, score in await rer.rerank(query_text=tb.build_from_supplier(sup), candidates=cands[i:i + 8], limit=8):
                R[tid] = score
        P0 = dict(fw.calculate_scores([(tenders[c], R[tenders[c].id]) for c in codes], sup))
        for c in codes:
            k = f"{rut}::{c}"
            r_, p0 = R[tenders[c].id], P0[tenders[c].id]
            filas.append({
                "rut": rut, "code": c, "rel": juicios[k]["rel"], "S": S[k], "R": r_, "P0": p0,
                "Lx": max(0.0, min(1.0, (p0 - 0.5 * r_) / 0.5)),
                "es_positivo_real": c in provs[rut]["ids_positivos"],
            })
        if n % 10 == 0:
            print(f"  proveedores {n}/{len(pares)}")
    CACHE.write_text(json.dumps(filas, ensure_ascii=False), encoding="utf-8")
    return filas


# --------------------------------------------------------------------------- métricas
def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(p[idx == b].mean() - y[idx == b].mean()) * (idx == b).mean() for b in range(bins) if (idx == b).any()))


def resumen(nombre: str, p: np.ndarray, y: np.ndarray) -> dict:
    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

    pc = np.clip(p, 1e-6, 1 - 1e-6)
    verdes = p >= 0.70
    return {
        "modelo": nombre, "auc": round(float(roc_auc_score(y, p)), 4), "brier": round(float(brier_score_loss(y, pc)), 4),
        "logloss": round(float(log_loss(y, pc)), 4), "ece": round(ece(p, y), 4),
        "precision_verdes_70": round(float(y[verdes].mean()), 3) if verdes.any() else None,
        "pct_verdes_70": round(float(verdes.mean()), 3),
    }


def tabla_confiabilidad(p: np.ndarray, y: np.ndarray, bins=(0, .1, .3, .5, .7, .9, 1.0001)) -> list:
    out = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (p >= lo) & (p < hi)
        if m.any():
            out.append({"rango": f"{int(lo*100)}–{min(100, int(hi*100))}%", "n": int(m.sum()),
                        "predicho": round(float(p[m].mean()), 3), "observado": round(float(y[m].mean()), 3)})
    return out


def main():
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold

    filas = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else asyncio.run(calcular_features())
    rel = np.array([f["rel"] for f in filas])
    y1, y2 = (rel >= 1).astype(int), (rel == 2).astype(int)
    grupos = np.array([f["rut"] for f in filas])
    feats = {
        "R": np.array([[logit(f["R"])] for f in filas]),
        "R+S": np.array([[logit(f["R"]), f["S"]] for f in filas]),
        "R+S+Lx": np.array([[logit(f["R"]), f["S"], f["Lx"]] for f in filas]),
    }
    P0 = np.array([f["P0"] for f in filas])
    print(f"Pares: {len(filas)} | rel 0/1/2 = {np.bincount(rel, minlength=3).tolist()} | proveedores: {len(set(grupos))}")
    print("Separación por etiqueta (media):")
    for g in (0, 1, 2):
        m = rel == g
        print(f"  rel={g}: S={np.mean([f['S'] for f, k in zip(filas, m) if k]):.3f}  R={np.mean([f['R'] for f, k in zip(filas, m) if k]):.3f}  P0={P0[m].mean():.3f}")

    gkf = GroupKFold(n_splits=5)

    def oof(X, y):
        p = np.zeros(len(y))
        for tr, te in gkf.split(X, y, grupos):
            p[te] = LogisticRegression(C=1.0).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        return p

    resultados = {"binario_rel_ge1": [resumen("actual (P0)", P0, y1)]}
    oofs = {}
    for nombre, X in feats.items():
        oofs[nombre] = oof(X, y1)
        resultados["binario_rel_ge1"].append(resumen(nombre, oofs[nombre], y1))

    print("\nCalibración de P(relevante ≥ 1), validación cruzada por proveedor:")
    print(f"{'modelo':<13}| AUC    | Brier  | LogLoss | ECE    | precisión ≥70% | % pares ≥70%")
    for r in resultados["binario_rel_ge1"]:
        print(f"{r['modelo']:<13}| {r['auc']:.4f} | {r['brier']:.4f} | {r['logloss']:.4f}  | {r['ece']:.4f} | {str(r['precision_verdes_70']):<14} | {r['pct_verdes_70']}")

    # Ordinal con el mejor conjunto parsimonioso (se elige abajo, se reporta para R y R+S)
    ordinal = {}
    for nombre in ("R", "R+S"):
        X = feats[nombre]
        p1, p2 = oof(X, y1), oof(X, y2)
        p2 = np.minimum(p2, p1)
        pct = 0.5 * p1 + 0.5 * p2
        ordinal[nombre] = {
            "media_por_rel": {str(g): round(float(pct[rel == g].mean()), 3) for g in (0, 1, 2)},
            "mae_vs_rel_sobre_2": round(float(np.abs(pct - rel / 2).mean()), 4),
            "mae_actual_P0": round(float(np.abs(P0 - rel / 2).mean()), 4),
        }
    resultados["ordinal"] = ordinal
    print("\nPorcentaje ordinal = 50·P(rel≥1) + 50·P(rel=2)  (media por etiqueta; ideal: 0 / 0,5 / 1)")
    print(f"  actual P0 : " + " / ".join(f"{P0[rel == g].mean():.2f}" for g in (0, 1, 2)))
    for nombre, o in ordinal.items():
        print(f"  {nombre:<9} : " + " / ".join(f"{o['media_por_rel'][str(g)]:.2f}" for g in (0, 1, 2)) + f"   MAE={o['mae_vs_rel_sobre_2']} (actual {o['mae_actual_P0']})")

    # Coeficientes finales (ajuste con todos los datos) para los modelos candidatos
    coefs = {}
    for nombre in ("R", "R+S"):
        X = feats[nombre]
        m1, m2 = LogisticRegression(C=1.0).fit(X, y1), LogisticRegression(C=1.0).fit(X, y2)
        coefs[nombre] = {
            "rel_ge1": {"intercepto": float(m1.intercept_[0]), "coef": m1.coef_[0].tolist()},
            "rel_eq2": {"intercepto": float(m2.intercept_[0]), "coef": m2.coef_[0].tolist()},
        }
    resultados["coeficientes"] = coefs
    resultados["confiabilidad_R_rel_ge1"] = tabla_confiabilidad(oofs["R"], y1)
    resultados["confiabilidad_actual_rel_ge1"] = tabla_confiabilidad(P0, y1)

    print("\nConfiabilidad (predicho vs observado, rel≥1):")
    print("  actual:", resultados["confiabilidad_actual_rel_ge1"])
    print("  R     :", resultados["confiabilidad_R_rel_ge1"])
    print("\nCoeficientes (todos los datos):", json.dumps(coefs, indent=1))
    SALIDA.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGuardado en {SALIDA}")


if __name__ == "__main__":
    main()
