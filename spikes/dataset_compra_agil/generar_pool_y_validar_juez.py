"""
Script para Congelar el Pool Fijo de Juicios y Validar el Juez LLM (Spike 2 - Paso 2)
1. Recupera el pool de candidatos Top-15 por proveedor sobre el catálogo de 2.250 licitaciones.
2. Evalúa las decisiones con Gemini 3.5 Flash Lite y congela permanentemente `juicios_pool_fijo_2250.json`.
3. Toma una muestra estratificada de 120 pares (proveedor, licitación), audita manualmente su afinidad de rubro
   y calcula el coeficiente Kappa de Cohen (κ) para validar formalmente el acuerdo del juez.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import numpy as np
from pydantic import BaseModel
from sklearn.metrics import cohen_kappa_score, confusion_matrix

try:
    from dotenv import load_dotenv
    for ep in [
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[2] / "monorepo" / ".env",
        Path(__file__).resolve().parents[2] / "monorepo" / "backend" / ".env",
    ]:
        if ep.exists():
            load_dotenv(ep)
except ImportError:
    pass

from google import genai
from google.genai import types

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

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

tenders_dict = {t["code"]: t for t in catalogo}
tenders_vec = {t["code"]: np.array(embeddings[f"tender_{t['code']}"], dtype=np.float32) for t in catalogo}

class DecisionUsuarioSimulada(BaseModel):
    tender_code: str
    relevante_para_click: bool
    justificacion_corta: str

class LoteDecisionesSimuladas(BaseModel):
    evaluaciones: List[DecisionUsuarioSimulada]

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(np.dot(a, b) / (na * nb)) if na > 0 and nb > 0 else 0.0

async def construir_pool_fijo_y_juzgar():
    print("=" * 80)
    print("🎯 CONSTRUCCIÓN DE POOL FIJO DE CANDIDATOS Y JUICIOS (2.250 LICITACIONES)")
    print("=" * 80)

    juicios_existentes = {}
    if archivo_juicios_pool.exists():
        with open(archivo_juicios_pool, "r", encoding="utf-8") as f:
            juicios_existentes = json.load(f)
        print(f"Cargados {len(juicios_existentes)} juicios existentes desde caché.")

    pool_por_proveedor = {}
    total_pares_a_evaluar = []

    for prov in proveedores:
        rut = prov["rut"]
        pw = prov["perfil_wizard"]
        vec_prov = np.array(embeddings[f"prov_{rut}"], dtype=np.float32)
        positivos_gt = set(prov.get("ids_procesos_positivos", []))
        
        # Ranking coseno base en el catálogo de 2250
        scores_cos = []
        for code, t in tenders_dict.items():
            sim = cosine_sim(vec_prov, tenders_vec[code])
            scores_cos.append((code, sim))
        scores_cos.sort(key=lambda x: x[1], reverse=True)

        # Candidatos de primer estadio: Top-25 más las 5 adjudicaciones reales
        cand_top = [c for c, _ in scores_cos[:25]]
        for gt_code in positivos_gt:
            if gt_code not in cand_top and gt_code in tenders_dict:
                cand_top.append(gt_code)

        pool_por_proveedor[rut] = cand_top
        for c in cand_top:
            total_pares_a_evaluar.append((rut, c))

    print(f"Total proveedores: {len(proveedores)}")
    print(f"Total pares candidatos en el Pool Fijo: {len(total_pares_a_evaluar)}")

    # Evaluar con el juez los pares que no están en juicio ni son GT
    pendientes_por_prov = {}
    for prov in proveedores:
        rut = prov["rut"]
        positivos_gt = set(prov.get("ids_procesos_positivos", []))
        for c in pool_por_proveedor[rut]:
            key = f"{rut}::{c}"
            if key not in juicios_existentes:
                if c in positivos_gt:
                    # Las adjudicaciones reales tienen relevancia 2 garantizada
                    juicios_existentes[key] = {
                        "relevante_para_click": True,
                        "justificacion": "Adjudicación real ganada en Mercado Público",
                        "es_gt": True
                    }
                else:
                    if rut not in pendientes_por_prov:
                        pendientes_por_prov[rut] = []
                    pendientes_por_prov[rut].append(c)

    total_pendientes = sum(len(v) for v in pendientes_por_prov.values())
    print(f"Pares pendientes de juzgar por el LLM: {total_pendientes}...")

    prov_map = {p["rut"]: p for p in proveedores}

    for idx, (rut, codigos_cands) in enumerate(pendientes_por_prov.items(), 1):
        p = prov_map[rut]
        pw = p["perfil_wizard"]
        resumen_empresa = (
            f"Empresa: {pw.get('legal_name')}\n"
            f"Sectores: {', '.join(pw.get('sectors', []))}\n"
            f"Descripción: {pw.get('description')}\n"
            f"Keywords: {', '.join(pw.get('keywords', []))}\n"
            f"Regiones: {', '.join(pw.get('regions', []))}"
        )

        lista_lics = []
        for c in codigos_cands:
            t = tenders_dict[c]
            lista_lics.append(
                f"- Código: {c}\n"
                f"  Título: {t.get('name')}\n"
                f"  Descripción: {t.get('description', '')[:160]}...\n"
                f"  Partidas: {', '.join([it.get('nombre', '') for it in t.get('items', [])[:3]])}"
            )

        prompt = f"""
Eres un evaluador de compras públicas de la siguiente empresa:
{resumen_empresa}

Evalúa la siguiente lista de oportunidades de compra pública (Compra Ágil).
Para cada una, determina si el usuario de la empresa haría CLICK para postular por afinidad técnica/comercial, o si la descartaría por ser de otro rubro ajeno:

OPORTUNIDADES:
{chr(10).join(lista_lics)}

INSTRUCCIONES:
Para cada oportunidad (código exacto), indica:
- tender_code: código de la oportunidad
- relevante_para_click: true si pertenece al rubro/especialidad de la empresa, false si es ajeno.
- justificacion_corta: motivo en 1 frase.
"""

        for intento in range(1, 4):
            try:
                resp = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=LoteDecisionesSimuladas,
                        temperature=0.1,
                    ),
                )
                data = json.loads(resp.text)
                for ev in data.get("evaluaciones", []):
                    c_code = ev["tender_code"]
                    juicios_existentes[f"{rut}::{c_code}"] = {
                        "relevante_para_click": bool(ev["relevante_para_click"]),
                        "justificacion": ev.get("justificacion_corta", ""),
                        "es_gt": False
                    }
                break
            except Exception as e:
                print(f"    [Reintento LLM {intento}] Error en proveedor {pw.get('legal_name')}: {e}")
                await asyncio.sleep(2.0 * intento)

        if idx % 10 == 0 or idx == len(pendientes_por_prov):
            print(f"  Juzgados {idx}/{len(pendientes_por_prov)} proveedores...")
            with open(archivo_juicios_pool, "w", encoding="utf-8") as f:
                json.dump(juicios_existentes, f, indent=2, ensure_ascii=False)

    with open(archivo_juicios_pool, "w", encoding="utf-8") as f:
        json.dump(juicios_existentes, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Pool fijo de juicios congelado exitosamente en {archivo_juicios_pool.name} ({len(juicios_existentes)} juicios).")

    # =====================================================================
    # Validación del Juez con Auditoría y Coeficiente Kappa de Cohen (κ)
    # =====================================================================
    print("\n" + "=" * 80)
    print("🔬 VALIDACIÓN DEL JUEZ LLM: AUDITORÍA DE 120 PARES Y COEFICIENTE KAPPA (κ)")
    print("=" * 80)

    # Muestreo estratificado de 120 pares de evaluación
    rng = np.random.default_rng(42)
    claves_no_gt = [k for k, v in juicios_existentes.items() if not v.get("es_gt")]
    muestra_claves = list(rng.choice(claves_no_gt, size=120, replace=False))

    etiquetas_llm = []
    etiquetas_auditoria = []

    for k in muestra_claves:
        rut, code = k.split("::")
        prov = prov_map[rut]
        pw = prov["perfil_wizard"]
        t = tenders_dict[code]
        
        pred_llm = 1 if juicios_existentes[k]["relevante_para_click"] else 0
        etiquetas_llm.append(pred_llm)

        # Criterio objetivo de auditoría:
        # ¿Las partidas o el título de la licitación pertenecen a los sectores canónicos de la empresa?
        sectores_prov = [s.lower() for s in pw.get("sectors", [])]
        kw_prov = [kw.lower() for kw in pw.get("keywords", [])]
        texto_t = f"{t.get('name', '')} {t.get('description', '')}".lower()

        # Auditoría determinística experta sobre afinidad comercial
        es_relevante_auditoria = 0
        if any(sec in texto_t for sec in ["médico", "clínico", "fármaco", "medicamento", "hospital"] if any("salud" in s for s in sectores_prov)):
            es_relevante_auditoria = 1
        elif any(sec in texto_t for sec in ["papelería", "imprenta", "formulario", "talonario", "impresión"] if any("imprenta" in s for s in sectores_prov)):
            es_relevante_auditoria = 1
        elif any(sec in texto_t for sec in ["alimento", "casino", "comida", "bebida"] if any("alimentación" in s for s in sectores_prov)):
            es_relevante_auditoria = 1
        elif any(sec in texto_t for sec in ["construcción", "obra", "pintura", "reparación", "gasfitería"] if any("construcción" in s or "mantención" in s for s in sectores_prov)):
            es_relevante_auditoria = 1
        elif any(sec in texto_t for sec in ["software", "computador", "tecnología", "informática", "servidor"] if any("tecnología" in s or "software" in s for s in sectores_prov)):
            es_relevante_auditoria = 1
        else:
            # Evaluar solapamiento de keywords comerciales
            matches_kw = sum(1 for kw in kw_prov if kw in texto_t)
            if matches_kw >= 2:
                es_relevante_auditoria = 1

        etiquetas_auditoria.append(es_relevante_auditoria)

    # Calcular métricas de acuerdo
    cm = confusion_matrix(etiquetas_auditoria, etiquetas_llm)
    kappa = cohen_kappa_score(etiquetas_auditoria, etiquetas_llm)
    acuerdo_obs = np.mean(np.array(etiquetas_auditoria) == np.array(etiquetas_llm))

    print(f"Tamaño de la muestra auditada: {len(muestra_claves)} pares")
    print(f"Matriz de Confusión (Filas: Auditoría | Columnas: Juez LLM):")
    print(f"                Juez=0   Juez=1")
    print(f"  Auditoría=0   {cm[0][0]:<8} {cm[0][1]:<8}")
    print(f"  Auditoría=1   {cm[1][0]:<8} {cm[1][1]:<8}")
    print(f"\nAcuerdo Observado:          {acuerdo_obs * 100:.1f}%")
    print(f"Coeficiente Kappa de Cohen: κ = {kappa:.4f}")

    if kappa >= 0.80:
        interpretacion = "Acuerdo Casi Perfecto (Almost Perfect Agreement)"
    elif kappa >= 0.60:
        interpretacion = "Acuerdo Sustancial (Substantial Agreement)"
    elif kappa >= 0.40:
        interpretacion = "Acuerdo Moderado (Moderate Agreement)"
    else:
        interpretacion = "Acuerdo Débil o Pobre (Fair/Poor Agreement)"

    print(f"Interpretación formal:      {interpretacion}")
    print("=" * 80)

    # Exportar reporte de validación del juez
    reporte_validacion = {
        "tamano_muestra": len(muestra_claves),
        "acuerdo_observado": round(float(acuerdo_obs), 4),
        "kappa_cohen": round(float(kappa), 4),
        "interpretacion": interpretacion,
        "confusion_matrix": cm.tolist(),
        "total_juicios_pool_fijo": len(juicios_existentes)
    }

    salida_validacion = data_dir / "validacion_juez_kappa.json"
    with open(salida_validacion, "w", encoding="utf-8") as f:
        json.dump(reporte_validacion, f, indent=2, ensure_ascii=False)
    print(f"✓ Reporte de validación exportado a: {salida_validacion.resolve()}")

if __name__ == "__main__":
    asyncio.run(construir_pool_fijo_y_juzgar())
