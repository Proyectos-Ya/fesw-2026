"""
Spike 2 - Paso D (alternativa sin cuota de Gemini): juez LLM ejecutado por subagentes de Claude.

  python juez_claude_lotes.py exportar   -> escribe data/temporal/juez_claude/entrada_*.json (pool común, por lotes)
  python juez_claude_lotes.py muestra    -> escribe entrada_val_*.json (150 pares para un segundo juez independiente)
  python juez_claude_lotes.py integrar   -> une salida_*.json en juicios_pool_temporal.json y calcula el acuerdo entre jueces

El pool es el mismo que arma juzgar_pool_temporal.py (unión del top-10 de todas las estrategias + adjudicaciones).
El juez NO recibe qué órdenes son las adjudicaciones ganadas ni en qué posición quedó cada estrategia.
"""

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TEMP = ROOT / "spikes" / "dataset_compra_agil" / "data" / "temporal"
OUT = TEMP / "juez_claude"
TOP_POOL = 10
PROV_POR_LOTE = 10
RUBRICA = (
    "2 = la empresa vende exactamente lo que se pide (mismo tipo de producto o servicio en las partidas). "
    "1 = misma familia de productos: podría cotizarlo con su catálogo actual sin cambiar de rubro. "
    "0 = otro rubro, o solo comparte una palabra suelta o un uso genérico. "
    "Sé estricto: ante la duda elige el valor menor. No consideres precio, tamaño ni región."
)


def cargar():
    cat = {d["code"]: d for d in json.loads((TEMP / "catalogo_temporal.json").read_text(encoding="utf-8"))}
    provs = {p["rut"]: p for p in json.loads((TEMP / "proveedores_temporal.json").read_text(encoding="utf-8"))}
    tops = json.loads((TEMP / "metricas_benchmark_temporal.json").read_text(encoding="utf-8"))["rankings_top20"]
    return cat, provs, tops


def construir_pool(provs, tops):
    pool = {}
    for rut, por_estr in tops.items():
        cods = set(provs[rut]["ids_positivos"])
        for lista in por_estr.values():
            cods.update(lista[:TOP_POOL])
        pool[rut] = sorted(cods)
    return pool


def doc_compacto(d):
    partidas = [f"{i['nombre']} ({i['descripcion'][:80]})" if i["descripcion"] else i["nombre"] for i in d["items"][:6]]
    return {"codigo": d["code"], "titulo": d["name"], "partidas": partidas}


def registro(p, cods, cat):
    pf = p["perfil"]
    return {
        "rut": p["rut"],
        "empresa": p["nombre"],
        "rubros": pf["sectors"],
        "descripcion": pf["description"],
        "productos_que_ofrece": pf["keywords"],
        "oportunidades": [doc_compacto(cat[c]) for c in cods],
    }


def escribir_lotes(registros, prefijo, por_lote):
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for i in range(0, len(registros), por_lote):
        n += 1
        (OUT / f"entrada_{prefijo}{n:02d}.json").write_text(
            json.dumps({"rubrica": RUBRICA, "empresas": registros[i:i + por_lote]}, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return n


def exportar():
    cat, provs, tops = cargar()
    pool = construir_pool(provs, tops)
    regs = [registro(provs[rut], cods, cat) for rut, cods in pool.items()]
    n = escribir_lotes(regs, "", PROV_POR_LOTE)
    print(f"{sum(len(v) for v in pool.values())} pares en {n} lotes -> {OUT}")


def muestra():
    cat, provs, tops = cargar()
    pool = construir_pool(provs, tops)
    claves = sorted(f"{rut}::{c}" for rut, cods in pool.items() for c in cods)
    rng = np.random.default_rng(42)
    elegidas = sorted(rng.choice(claves, size=150, replace=False))
    por_rut = {}
    for k in elegidas:
        rut, c = k.split("::")
        por_rut.setdefault(rut, []).append(c)
    regs = [registro(provs[rut], cods, cat) for rut, cods in por_rut.items()]
    n = escribir_lotes(regs, "val_", max(1, len(regs) // 3 + 1))
    print(f"muestra de {len(elegidas)} pares de {len(regs)} empresas en {n} lotes de validación")


def leer_salidas(prefijo):
    out = {}
    for f in sorted(OUT.glob(f"salida_{prefijo}*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for e in d["empresas"]:
            for j in e["juicios"]:
                out[f"{e['rut']}::{j['codigo']}"] = {"rel": max(0, min(2, int(j["relevancia"]))), "motivo": j.get("motivo", "")}
    return out


def integrar():
    cat, provs, tops = cargar()
    pool = construir_pool(provs, tops)
    todas = {f"{rut}::{c}" for rut, cods in pool.items() for c in cods}

    a = leer_salidas("0")  # salida_01.. (pool completo)
    a = {k: {**v, "modelo": "claude-subagente-juez"} for k, v in a.items() if k in todas}
    faltan = sorted(todas - a.keys())
    print(f"Pares juzgados: {len(a)}/{len(todas)} | sin juicio: {len(faltan)}")
    if faltan[:5]:
        print("  ejemplos sin juicio:", faltan[:5])

    dist = np.bincount([v["rel"] for v in a.values()], minlength=3).tolist()
    gt = [a[f"{rut}::{c}"]["rel"] for rut, p in provs.items() for c in p["ids_positivos"] if f"{rut}::{c}" in a]
    print(f"Distribución del juez (0/1/2): {dist}")
    print(f"Adjudicaciones reales juzgadas a ciegas ({len(gt)}): rel 0/1/2 = {np.bincount(gt, minlength=3).tolist()}")

    (TEMP / "juicios_pool_temporal.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")

    b = leer_salidas("val_")
    comunes = sorted(set(b) & set(a))
    if comunes:
        from sklearn.metrics import cohen_kappa_score
        x = [a[k]["rel"] for k in comunes]
        y = [b[k]["rel"] for k in comunes]
        rep = {
            "pares_comparados": len(comunes),
            "kappa_ponderado_cuadratico": round(float(cohen_kappa_score(x, y, weights="quadratic")), 4),
            "kappa_binario_rel_ge1": round(float(cohen_kappa_score([int(v >= 1) for v in x], [int(v >= 1) for v in y])), 4),
            "acuerdo_exacto": round(float(np.mean(np.array(x) == np.array(y))), 4),
            "distribucion_juez_principal_en_muestra": np.bincount(x, minlength=3).tolist(),
            "distribucion_segundo_juez": np.bincount(y, minlength=3).tolist(),
            "nota": "Acuerdo entre dos jueces LLM independientes (subagentes de Claude), no contra humanos.",
        }
        (TEMP / "validacion_juez_temporal.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Acuerdo entre jueces:", json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    {"exportar": exportar, "muestra": muestra, "integrar": integrar}[sys.argv[1]]()
