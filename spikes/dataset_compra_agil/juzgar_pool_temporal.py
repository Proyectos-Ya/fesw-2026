"""
Spike 2 - Paso D: Juez LLM estricto sobre un POOL COMÚN (unión del top-10 de TODAS las estrategias).

Corrige dos fallas del benchmark anterior:
  * El pool salía solo del ranking de una estrategia (A): lo que B/C/D traían fuera quedaba como "irrelevante" sin juicio.
    Aquí se juzga la unión de los top-10 de todas las estrategias (+ las adjudicaciones reales), una sola vez.
  * El juez era laxo ("afinidad complementaria" → 74 % de positivos). Aquí la escala es 0/1/2 con criterios explícitos:
        2 = la empresa vende exactamente ese producto/servicio (el mismo tipo de partida)
        1 = misma familia de producto: podría cotizarlo con su catálogo actual
        0 = otro rubro
    El juez ve el perfil construido desde el historial, NO sabe cuál OC fue la ganada.

Validación del juez: NO hay anotación humana. Se mide el acuerdo entre DOS modelos distintos sobre una muestra
(kappa ponderado cuadrático entre los dos jueces) y se exporta un CSV para que una persona etiquete una muestra.
Ese acuerdo entre modelos es una medida de consistencia, no de validez frente a humanos.

Salidas (data/temporal/): juicios_pool_temporal.json, validacion_juez_temporal.json, muestra_para_etiquetar.csv
"""

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import numpy as np
from dotenv import load_dotenv
from pydantic import BaseModel
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[2]
for ep in [ROOT / ".env", ROOT / "monorepo" / ".env", ROOT / "monorepo" / "backend" / ".env"]:
    if ep.exists():
        load_dotenv(ep)

TEMP = ROOT / "spikes" / "dataset_compra_agil" / "data" / "temporal"
MODELOS_JUEZ_A = ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.8-flash"]
MODELOS_JUEZ_B = ["gemini-2.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]
TOP_POOL = 10


class Juicio(BaseModel):
    tender_code: str
    relevancia: int  # 0, 1 o 2
    motivo: str


class LoteJuicios(BaseModel):
    juicios: List[Juicio]


def prompt_juez(perfil: Dict[str, Any], nombre: str, docs: List[Dict[str, Any]]) -> str:
    lic = []
    for d in docs:
        items = "; ".join(f"{i['nombre']} ({i['descripcion'][:80]})" if i["descripcion"] else i["nombre"] for i in d["items"][:6])
        lic.append(f"- Código: {d['code']}\n  Título: {d['name']}\n  Partidas: {items}\n  Región: {d['region']}")
    return f"""
Eres un experto en compras públicas chilenas. Evalúa qué tan bien calza cada oportunidad de compra con la empresa.

EMPRESA: {nombre}
Rubros: {', '.join(perfil['sectors'])}
Descripción: {perfil['description']}
Productos que ofrece: {', '.join(perfil['keywords'])}
Regiones donde ha vendido: {', '.join(perfil['regions'])}

ESCALA (sé estricto; ante la duda, elige el valor menor):
  2 = la empresa vende exactamente lo que se pide (mismo tipo de producto o servicio en las partidas).
  1 = misma familia de productos: podría cotizarlo con su catálogo actual sin cambiar de rubro.
  0 = otro rubro, o solo comparte una palabra suelta o un uso genérico.
No consideres el precio, el tamaño ni la región para el valor 0/1/2.

OPORTUNIDADES:
{chr(10).join(lic)}

Devuelve un juicio por cada oportunidad, con su código exacto.
"""


def juzgar(client, modelos: List[str], prompt: str) -> Dict[str, Dict[str, Any]]:
    from google.genai import types

    for modelo in modelos:
        for intento in range(1, 3):
            try:
                r = client.models.generate_content(
                    model=modelo, contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=LoteJuicios, temperature=0.0),
                )
                d = json.loads(r.text)
                out = {j["tender_code"]: {"rel": max(0, min(2, int(j["relevancia"]))), "motivo": j.get("motivo", ""), "modelo": modelo} for j in d.get("juicios", [])}
                if out:
                    return out
            except Exception as e:
                msg = str(e)
                print(f"    [juez] {modelo} intento {intento}: {msg[:100]}")
                if "PerDay" in msg or "limit: 0" in msg:
                    break
                time.sleep(5.0 * intento)
    return {}


def exportar_csv_etiquetado(pool: Dict[str, List[str]], provs: Dict[str, Any], catalogo: Dict[str, Dict[str, Any]], n: int = 150) -> None:
    """CSV para etiquetado humano: muestra del POOL (no solo de lo ya juzgado), sin mostrar el juicio del LLM."""
    rng = np.random.default_rng(7)
    claves = sorted(f"{rut}::{c}" for rut, cods in pool.items() for c in cods)
    muestra = list(rng.choice(claves, size=min(n, len(claves)), replace=False))
    with open(TEMP / "muestra_para_etiquetar.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["proveedor", "productos_del_perfil", "codigo", "titulo", "partidas", "etiqueta_humana(0/1/2)"])
        for k in muestra:
            rut, c = k.split("::")
            d, p = catalogo[c], provs[rut]
            w.writerow([p["nombre"], "; ".join(p["perfil"]["keywords"][:8]), c, d["name"], "; ".join(i["nombre"] for i in d["items"][:5]), ""])
    print(f"CSV para etiquetado humano: muestra_para_etiquetar.csv ({len(muestra)} pares)")


def construir_pool(provs, tops):
    pool = {}
    for rut, por_estr in tops.items():
        cods = []
        for lista in por_estr.values():
            cods += lista[:TOP_POOL]
        cods += provs[rut]["ids_positivos"]
        pool[rut] = sorted(set(cods))
    return pool


def main():
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    catalogo = {d["code"]: d for d in json.loads((TEMP / "catalogo_temporal.json").read_text(encoding="utf-8"))}
    provs = {p["rut"]: p for p in json.loads((TEMP / "proveedores_temporal.json").read_text(encoding="utf-8"))}
    met = json.loads((TEMP / "metricas_benchmark_temporal.json").read_text(encoding="utf-8"))
    tops = met["rankings_top20"]

    pool: Dict[str, List[str]] = {}
    for rut, por_estr in tops.items():
        cods = []
        for lista in por_estr.values():
            cods += lista[:TOP_POOL]
        cods += provs[rut]["ids_positivos"]
        pool[rut] = sorted(set(cods))
    total = sum(len(v) for v in pool.values())
    print(f"Pool común: {total} pares (media {total / len(pool):.1f} por proveedor)")

    out_path = TEMP / "juicios_pool_temporal.json"
    juicios: Dict[str, Dict[str, Any]] = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}

    for i, (rut, cods) in enumerate(pool.items(), 1):
        faltan = [c for c in cods if f"{rut}::{c}" not in juicios]
        if not faltan:
            continue
        p = provs[rut]
        got = juzgar(client, MODELOS_JUEZ_A, prompt_juez(p["perfil"], p["nombre"], [catalogo[c] for c in faltan]))
        for c, j in got.items():
            juicios[f"{rut}::{c}"] = j
        out_path.write_text(json.dumps(juicios, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {i}/{len(pool)} {p['nombre'][:30]:<30} juzgados {len(got)}/{len(faltan)}")

    sin_juicio = [k for rut, cods in pool.items() for c in cods for k in [f"{rut}::{c}"] if k not in juicios]
    print(f"Pares sin juicio: {len(sin_juicio)} de {total}")

    # Distribución de etiquetas y relación con las adjudicaciones reales
    dist = np.bincount([j["rel"] for j in juicios.values()], minlength=3)
    gt_keys = [f"{rut}::{c}" for rut, p in provs.items() for c in p["ids_positivos"]]
    gt_rel = [juicios[k]["rel"] for k in gt_keys if k in juicios]
    print(f"Distribución del juez (0/1/2): {dist.tolist()} | adjudicaciones reales juzgadas {len(gt_rel)}: {np.bincount(gt_rel, minlength=3).tolist()}")

    # Validación por acuerdo entre dos modelos (muestra estratificada de 150 pares)
    rng = np.random.default_rng(42)
    claves = sorted(juicios.keys())
    muestra = list(rng.choice(claves, size=min(150, len(claves)), replace=False))
    val_path = TEMP / "juicios_modelo_b.json"
    juicios_b: Dict[str, Dict[str, Any]] = json.loads(val_path.read_text(encoding="utf-8")) if val_path.exists() else {}
    por_prov: Dict[str, List[str]] = {}
    for k in muestra:
        rut, c = k.split("::")
        if k not in juicios_b:
            por_prov.setdefault(rut, []).append(c)
    for rut, cods in por_prov.items():
        p = provs[rut]
        got = juzgar(client, MODELOS_JUEZ_B, prompt_juez(p["perfil"], p["nombre"], [catalogo[c] for c in cods]))
        for c, j in got.items():
            juicios_b[f"{rut}::{c}"] = j
        val_path.write_text(json.dumps(juicios_b, ensure_ascii=False, indent=1), encoding="utf-8")
    comunes = [k for k in muestra if k in juicios_b]
    if len(comunes) >= 30:
        a = [juicios[k]["rel"] for k in comunes]
        b = [juicios_b[k]["rel"] for k in comunes]
        kw = float(cohen_kappa_score(a, b, weights="quadratic"))
        acc = float(np.mean(np.array(a) == np.array(b)))
        rep = {"pares_comparados": len(comunes), "kappa_ponderado_entre_modelos": round(kw, 4), "acuerdo_exacto": round(acc, 4),
               "modelos_a": sorted({j['modelo'] for j in juicios.values()}), "modelos_b": sorted({j['modelo'] for j in juicios_b.values()}),
               "distribucion_a": dist.tolist(), "nota": "Acuerdo entre dos modelos, no contra humanos."}
        (TEMP / "validacion_juez_temporal.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Acuerdo entre jueces: kappa ponderado={kw:.3f} | acuerdo exacto={acc:.3f} (n={len(comunes)})")

    exportar_csv_etiquetado(pool, provs, catalogo)

if __name__ == "__main__":
    main()
