"""
Spike 2 - Paso B: Construcción del benchmark con split temporal y catálogo natural.

Qué corrige respecto del benchmark anterior:
  * Fuga de datos: el perfil de cada proveedor se genera SOLO con sus 3 OCs más antiguas (historial);
    la relevancia 2 son sus OCs posteriores (las que el sistema debería haberle recomendado).
  * Catálogo homogéneo: los distractores salen del mismo endpoint de detalle que las adjudicaciones
    (mismo formato, con partidas, categoría UNSPSC y región real), en vez de solo el título del listado.
  * No se filtra el nombre del proveedor: se elimina la línea "dirigida a <PROVEEDOR>" de la descripción.
  * Los distractores excluyen cualquier OC de los 50 proveedores evaluados.

Salidas (data/temporal/):
  catalogo_temporal.json          documentos del catálogo (positivos + distractores), formato uniforme
  proveedores_temporal.json       50 proveedores con perfil-desde-historial y positivos (OCs posteriores)
"""

import asyncio
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from dotenv import load_dotenv
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
for ep in [ROOT / ".env", ROOT / "monorepo" / ".env", ROOT / "monorepo" / "backend" / ".env"]:
    if ep.exists():
        load_dotenv(ep)

DATA = ROOT / "spikes" / "dataset_compra_agil" / "data"
TEMP = DATA / "temporal"

CANONICAL_SECTORS = [
    "Obras de Construcción e Infraestructura", "Mantención y Reparación", "Arquitectura e Ingeniería",
    "Tecnología y Telecomunicaciones", "Desarrollo de Software", "Consultoría y Asesoría Técnica",
    "Salud y Equipamiento Médico", "Educación y Capacitación", "Transporte y Logística",
    "Alimentación y Gastronomía", "Limpieza y Aseo Industrial", "Seguridad y Vigilancia",
    "Medio Ambiente y Sustentabilidad", "Energía y Electricidad", "Servicios de Imprenta y Diseño",
    "Jardinería y Paisajismo", "Equipos e Insumos Industriales", "Recursos Humanos", "Contabilidad y Auditoría",
]

N_HISTORIAL = 3  # OCs más antiguas → perfil ; las restantes → relevancia 2


def limpiar_nombre(nombre: str) -> str:
    # "MATERIAL FERRETERIA por invitación a compra ágil: 4488-157-COT26" → "MATERIAL FERRETERIA"
    n = re.sub(r"\s*por invitaci[oó]n a compra [aá]gil:.*$", "", nombre or "", flags=re.I).strip()
    return n


def limpiar_descripcion(desc: str) -> str:
    if not desc:
        return ""
    lineas = []
    for ln in re.split(r"[\r\n]+", desc):
        low = ln.lower()
        if "dirigida a" in low or low.startswith("justificaci"):
            continue  # nombre del proveedor y justificación de selección: no describen lo comprado
        lineas.append(ln.strip())
    return " ".join(l for l in lineas if l)


def parsear_oc(oc: Dict[str, Any], dia: Optional[str] = None) -> Dict[str, Any]:
    fechas = oc.get("Fechas") or {}
    fecha = (fechas.get("FechaEnvio") or fechas.get("FechaCreacion") or "")[:19]
    comprador = oc.get("Comprador") or {}
    items_raw = (oc.get("Items") or {}).get("Listado") or []
    if isinstance(items_raw, dict):
        items_raw = [items_raw]
    items = [
        {
            "nombre": (it.get("Producto") or "").strip(),
            "descripcion": (it.get("EspecificacionComprador") or "").strip(),
            "categoria": (it.get("Categoria") or "").strip(),
            "codigo_categoria": it.get("CodigoCategoria"),
            "codigo_producto": it.get("CodigoProducto"),
        }
        for it in items_raw
    ]
    prov = oc.get("Proveedor") or {}
    return {
        "code": str(oc.get("Codigo")),
        "fecha": fecha,
        "name": limpiar_nombre(oc.get("Nombre") or ""),
        "description": limpiar_descripcion(oc.get("Descripcion") or ""),
        "region": (comprador.get("RegionUnidad") or "").strip(),
        "buyer_name": (comprador.get("NombreOrganismo") or "").strip(),
        "items": items,
        "_rut_proveedor": str(prov.get("RutSucursal") or prov.get("Rut") or "").strip(),
    }


def leer_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


class PerfilHistorial(BaseModel):
    sectors: List[str] = Field(description="1 a 3 sectores canónicos exactos de la lista permitida")
    description: str = Field(description="Presentación comercial general de la empresa, 30 a 80 palabras")
    keywords: List[str] = Field(description="8 a 12 productos o servicios que ofrece la empresa")


class PerfilLote(PerfilHistorial):
    rut: str


class LotePerfiles(BaseModel):
    perfiles: List[PerfilLote]


MODELOS_PERFIL = ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.8-flash",
                  "gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash-lite"]


def perfiles_en_lote(client, lote: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Genera varios perfiles en una sola llamada (el nivel gratuito limita las llamadas por día y modelo).
    lote: [{rut, nombre, hist: [docs]}]. Rota de modelo si el actual agotó su cuota diaria."""
    import time
    from google.genai import types

    bloques = []
    for it in lote:
        lineas = [
            f"  - {d['name']}: " + "; ".join(f"{i['nombre']} [{i['categoria']}]" for i in d["items"][:6]) for d in it["hist"]
        ]
        bloques.append(f"EMPRESA rut={it['rut']} nombre=\"{it['nombre']}\"\n  Historial de ventas:\n" + "\n".join(lineas))
    prompt = f"""
Eres el asistente del Wizard de Onboarding de ProyectosYA. Para CADA empresa, configura su perfil a partir de lo que
HA VENDIDO hasta ahora (historial). Devuelve un perfil por empresa, con el mismo rut.

SECTORES CANÓNICOS (elige 1 a 3 exactos por empresa): {json.dumps(CANONICAL_SECTORS, ensure_ascii=False)}

Reglas: describe a la empresa de forma general como lo haría su dueño (rubro y tipo de productos), 30 a 80 palabras,
sin códigos ni fechas y sin copiar textos literales de las órdenes. Las keywords (8 a 12) son productos o servicios que ofrece.

{chr(10).join(bloques)}
"""
    for modelo in MODELOS_PERFIL:
        for intento in range(1, 3):
            try:
                r = client.models.generate_content(
                    model=modelo, contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=LotePerfiles, temperature=0.2),
                )
                d = json.loads(r.text)
                out = {}
                for pf in d.get("perfiles", []):
                    sectors = [s for s in pf.get("sectors", []) if s in CANONICAL_SECTORS] or ["Equipos e Insumos Industriales"]
                    out[pf["rut"]] = {"sectors": sectors, "description": pf.get("description", ""), "keywords": pf.get("keywords", []), "_modelo": modelo}
                if out:
                    return out
            except Exception as e:
                msg = str(e)
                print(f"    [perfil-lote] {modelo} intento {intento}: {msg[:120]}")
                if "PerDay" in msg or "limit: 0" in msg:
                    break  # cuota diaria agotada: pasar al siguiente modelo
                time.sleep(5.0 * intento)
    return {}


def perfil_desde_historial(client, nombre: str, docs_hist: List[Dict[str, Any]]) -> Dict[str, Any]:
    from google.genai import types

    resumen = []
    for d in docs_hist:
        prods = "; ".join(f"{it['nombre']} [{it['categoria']}]" for it in d["items"][:6])
        resumen.append(f"- {d['name']}: {prods}")
    prompt = f"""
Eres el asistente del Wizard de Onboarding de ProyectosYA. Configura el perfil de la empresa "{nombre}"
a partir de lo que HA VENDIDO hasta ahora (historial de ventas):
{chr(10).join(resumen)}

SECTORES CANÓNICOS (elige 1 a 3 exactos): {json.dumps(CANONICAL_SECTORS, ensure_ascii=False)}

Reglas: describe a la empresa de forma general como lo haría su dueño (rubro y tipo de productos), sin códigos,
sin fechas y sin copiar textos literales de las órdenes. Las keywords son productos o servicios que ofrece.
"""
    for intento in range(1, 4):
        try:
            r = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=PerfilHistorial, temperature=0.2
                ),
            )
            d = json.loads(r.text)
            sectors = [s for s in d.get("sectors", []) if s in CANONICAL_SECTORS] or ["Equipos e Insumos Industriales"]
            return {"sectors": sectors, "description": d.get("description", ""), "keywords": d.get("keywords", [])}
        except Exception as e:
            print(f"    [perfil] reintento {intento} ({nombre}): {e}")
            import time
            time.sleep(2.0 * intento)
    return {"sectors": ["Equipos e Insumos Industriales"], "description": f"{nombre}, proveedor de bienes y servicios.", "keywords": [], "_fallback": True}


def main():
    from google import genai

    provs = json.loads((DATA / "dataset_compra_agil_proveedores.json").read_text(encoding="utf-8"))
    ocs_prov = {r["codigo"]: r for r in leer_jsonl(TEMP / "ocs_proveedores_detalle.jsonl")}
    ocs_muestra = leer_jsonl(TEMP / "ocs_detalle.jsonl")
    print(f"OCs de proveedores con detalle: {len(ocs_prov)} | OCs de muestra: {len(ocs_muestra)}")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    ruts_eval = {p["rut"] for p in provs}
    codigos_prov = {o["codigo_oc"] for p in provs for o in p["ordenes_compra_adjudicadas"]}

    plan = []
    proveedores_out = []
    positivos_docs: Dict[str, Dict[str, Any]] = {}
    hist_codes = set()
    sin_fecha = descartados = 0

    for p in provs:
        docs = []
        for o in p["ordenes_compra_adjudicadas"]:
            row = ocs_prov.get(o["codigo_oc"])
            if row:
                docs.append(parsear_oc(row["oc"]))
        docs = [d for d in docs if d["fecha"]]
        if len(docs) < 5:
            sin_fecha += 1
        docs.sort(key=lambda d: (d["fecha"], d["code"]))
        # Historial de 3 OCs; si no queda ninguna OC estrictamente posterior, se prueba con 2.
        hist, test = [], []
        for n_hist in (N_HISTORIAL, N_HISTORIAL - 1):
            if len(docs) < n_hist + 1:
                continue
            h, t = docs[:n_hist], docs[n_hist:]
            # Solo se aceptan positivos estrictamente posteriores al historial
            t = [d for d in t if d["fecha"] > h[-1]["fecha"]]
            if t:
                hist, test = h, t
                break
        if not test:
            descartados += 1
            continue
        plan.append((p, hist, test))

    # Perfiles generados a partir del historial, en lotes, con caché en disco (solo se guardan los válidos)
    cache_perf_path = TEMP / "perfiles_historial_cache.json"
    cache_perf = json.loads(cache_perf_path.read_text(encoding="utf-8")) if cache_perf_path.exists() else {}
    faltan = [{"rut": p["rut"], "nombre": p["nombre"], "hist": hist} for p, hist, _ in plan if p["rut"] not in cache_perf]
    for i in range(0, len(faltan), 10):
        lote = faltan[i:i + 10]
        got = perfiles_en_lote(client, lote)
        cache_perf.update(got)
        cache_perf_path.write_text(json.dumps(cache_perf, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  perfiles generados {len(got)}/{len(lote)} en lote {i // 10 + 1}")

    for p, hist, test in plan:
        perfil = dict(cache_perf.get(p["rut"]) or {"sectors": [], "description": "", "keywords": [], "_fallback": True})
        regiones = sorted({d["region"] for d in hist if d["region"]})
        cats = Counter(it["codigo_categoria"] for d in hist for it in d["items"] if it.get("codigo_categoria"))
        perfil.update({
            "regions": regiones,
            "categorias_historicas": [c for c, _ in cats.most_common(8)],
            "productos_historicos": [it["nombre"] for d in hist for it in d["items"] if it["nombre"]][:15],
        })
        proveedores_out.append({
            "rut": p["rut"], "nombre": p["nombre"], "perfil": perfil,
            "ids_historial": [d["code"] for d in hist],
            "ids_positivos": [d["code"] for d in test],
            "fechas_historial": [d["fecha"] for d in hist],
            "fechas_positivos": [d["fecha"] for d in test],
        })
        for d in test:
            positivos_docs[d["code"]] = d
        hist_codes.update(d["code"] for d in hist)
    n_fb = sum(1 for pv in proveedores_out if pv["perfil"].get("_fallback"))
    print(f"Perfiles con fallback (sin LLM): {n_fb}/{len(proveedores_out)}")

    # Distractores: OCs de la muestra que no son de los proveedores evaluados
    distractores = {}
    for r in ocs_muestra:
        d = parsear_oc(r["oc"], r.get("dia"))
        if d["_rut_proveedor"] in ruts_eval or d["code"] in codigos_prov or d["code"] in hist_codes:
            continue
        distractores[d["code"]] = d

    catalogo = []
    for d in positivos_docs.values():
        d = dict(d); d["es_distractor"] = False; catalogo.append(d)
    for d in distractores.values():
        d = dict(d); d["es_distractor"] = True; catalogo.append(d)
    for d in catalogo:
        d.pop("_rut_proveedor", None)

    (TEMP / "catalogo_temporal.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")
    (TEMP / "proveedores_temporal.json").write_text(json.dumps(proveedores_out, ensure_ascii=False, indent=1), encoding="utf-8")
    n_pos = sum(len(p["ids_positivos"]) for p in proveedores_out)
    print(f"\nProveedores válidos: {len(proveedores_out)} (descartados={descartados}, con <5 OCs con fecha={sin_fecha})")
    print(f"Catálogo: {len(catalogo)} docs = {n_pos} positivos + {len(distractores)} distractores")


if __name__ == "__main__":
    main()
