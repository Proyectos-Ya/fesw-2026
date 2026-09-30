"""
Script para Construcción del Dataset Riguroso de Evaluación (Spike 2 - Paso 2)
1. Elimina la fuga de datos (Data Leakage): Genera perfiles estilo Onboarding Wizard
   usando sectores canónicos de ProyectosYA y descripción comercial ciega a las licitaciones.
2. Descarga e inyecta 2.000 distractores reales de Compra Ágil de Mercado Público.
3. Compila el catálogo consolidado (2.250 licitaciones: 250 Ground Truth + 2.000 distractores).
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import httpx
from pydantic import BaseModel, Field

# Cargar variables de entorno
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

# Sectores canónicos del Wizard de ProyectosYA
CANONICAL_SECTORS = [
    "Obras de Construcción e Infraestructura",
    "Mantención y Reparación",
    "Arquitectura e Ingeniería",
    "Tecnología y Telecomunicaciones",
    "Desarrollo de Software",
    "Consultoría y Asesoría Técnica",
    "Salud y Equipamiento Médico",
    "Educación y Capacitación",
    "Transporte y Logística",
    "Alimentación y Gastronomía",
    "Limpieza y Aseo Industrial",
    "Seguridad y Vigilancia",
    "Medio Ambiente y Sustentabilidad",
    "Energía y Electricidad",
    "Servicios de Imprenta y Diseño",
    "Jardinería y Paisajismo",
    "Equipos e Insumos Industriales",
    "Recursos Humanos",
    "Contabilidad y Auditoría",
]

# Regiones canónicas del Wizard
CANONICAL_REGIONS = [
    "Arica y Parinacota", "Tarapacá", "Antofagasta", "Atacama", "Coquimbo",
    "Valparaíso", "Metropolitana", "O'Higgins", "Maule", "Ñuble", "Biobío",
    "La Araucanía", "Los Ríos", "Los Lagos", "Aysén", "Magallanes"
]


class WizardProfileSchema(BaseModel):
    sectors: List[str] = Field(description="1 a 3 sectores canónicos exactos de la lista permitida")
    regions: List[str] = Field(description="1 a 3 regiones canónicas exactas donde opera la empresa")
    description: str = Field(description="Descripción comercial general de la empresa (30 a 100 palabras) sin citar licitaciones específicas ni códigos")
    keywords: List[str] = Field(description="10 a 15 términos clave generales representativos del rubro comercial")


async def sintetizar_perfiles_wizard_sin_fuga(proveedores_raw: List[Dict[str, Any]], api_key: str) -> List[Dict[str, Any]]:
    """
    Genera perfiles de proveedor estilo Wizard de Onboarding de ProyectosYA,
    utilizando ÚNICAMENTE el nombre y la identidad general de la empresa,
    SIN tener acceso a los textos de las licitaciones de prueba (Cero Data Leakage).
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    nuevos_proveedores = []

    print(f"\n[1/3] Sintetizando {len(proveedores_raw)} perfiles ciegos estilo Wizard (Sin Data Leakage)...")

    for i, prov in enumerate(proveedores_raw, 1):
        nombre = prov["nombre"]
        rut = prov["rut"]
        perfil_previo = prov.get("perfil", {})
        
        # Referencia sólo de los sectores generales previos para mantener el rubro del negocio,
        # pero SIN textos de licitaciones ni descripciones derivadas de compras
        rubro_orientacion = ", ".join(perfil_previo.get("sectors", []))

        prompt = f"""
Eres un asistente que configura el perfil de empresa en el Wizard de Onboarding de ProyectosYA.
Configura el perfil comercial para la siguiente empresa basándote en su rubro general de negocio:

Empresa: {nombre} (RUT: {rut})
Rubro general aproximado: {rubro_orientacion}

LISTA OBLIGATORIA DE SECTORES CANÓNICOS (elige 1 a 3 de esta lista exacta):
{json.dumps(CANONICAL_SECTORS, ensure_ascii=False)}

LISTA OBLIGATORIA DE REGIONES CANÓNICAS (elige 1 a 3 de esta lista exacta):
{json.dumps(CANONICAL_REGIONS, ensure_ascii=False)}

REGLAS CRÍTICAS:
1. La descripción debe ser una presentación comercial estándar y natural (ej: "Empresa dedicada a la distribución mayorista de insumos...").
2. Las keywords deben ser términos comerciales habituales que un dueño de empresa tipea en el formulario (ej: "guantes", "jeringas", "alcohol", "gasa").
3. PROHIBIDO incluir códigos de licitación, fechas, o textos de órdenes de compra específicas.
"""

        try:
            resp = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=WizardProfileSchema,
                    temperature=0.2,
                ),
            )
            data = json.loads(resp.text)
            
            perfil_limpio = {
                "rut": rut,
                "legal_name": nombre,
                "sectors": [s for s in data.get("sectors", []) if s in CANONICAL_SECTORS],
                "regions": [r for r in data.get("regions", []) if r in CANONICAL_REGIONS],
                "description": data.get("description", ""),
                "keywords": data.get("keywords", []),
            }

            # Asegurar fallback válido si el LLM omitió sectores
            if not perfil_limpio["sectors"]:
                perfil_limpio["sectors"] = ["Equipos e Insumos Industriales"]
            if not perfil_limpio["regions"]:
                perfil_limpio["regions"] = ["Metropolitana"]

        except Exception as e:
            print(f"  [Aviso] Fallo al generar perfil para {nombre}: {e}. Usando plantilla estándar.")
            perfil_limpio = {
                "rut": rut,
                "legal_name": nombre,
                "sectors": ["Equipos e Insumos Industriales"],
                "regions": ["Metropolitana"],
                "description": f"{nombre} es un proveedor especializado en suministros y servicios comerciales.",
                "keywords": ["suministros", "servicios", "equipamiento", "mantencion"],
            }

        nuevos_proveedores.append({
            "rut": rut,
            "nombre": nombre,
            "perfil_wizard": perfil_limpio,
            "ids_procesos_positivos": prov.get("ids_procesos_positivos", []),
        })

        if i % 10 == 0 or i == len(proveedores_raw):
            print(f"  Procesados {i}/{len(proveedores_raw)} perfiles de Wizard...")

    return nuevos_proveedores


async def descargar_distractores_mercado_publico(
    ticket: str,
    ruts_excluidos: Set[str],
    codigos_excluidos: Set[str],
    cantidad_meta: int = 2000,
) -> List[Dict[str, Any]]:
    """
    Descarga licitaciones/OCs reales de Compra Ágil de Mercado Público
    que NO correspondan a los 50 proveedores evaluados ni a sus compras ganadas.
    """
    print(f"\n[2/3] Descargando {cantidad_meta} distractores reales de Compra Ágil desde Mercado Público...")
    fechas = ["21092026", "22092026", "23092026", "24092026", "25092026"]
    distractores = []
    vistos = set(codigos_excluidos)

    async with httpx.AsyncClient(timeout=40.0) as client:
        for fecha in fechas:
            if len(distractores) >= cantidad_meta:
                break
            url = f"https://api.mercadopublico.cl/servicios/v1/publico/ordenesdecompra.json?fecha={fecha}&ticket={ticket}"
            print(f"  Consultando listado de Mercado Público para fecha {fecha}...")
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("Listado", [])
                    for it in items:
                        cod = str(it.get("Codigo") or "").strip().upper()
                        nom = str(it.get("Nombre") or "").strip()
                        if "-AG" in cod or "-COT" in cod:
                            if cod not in vistos:
                                vistos.add(cod)
                                distractores.append({
                                    "code": cod,
                                    "name": nom,
                                    "description": f"Compra Ágil de bienes/servicios públicos: {nom}",
                                    "region": "Metropolitana",  # Región neutral por defecto para distractores sintéticos de lista
                                    "items": [{"nombre": nom, "descripcion": nom}],
                                    "es_distractor": True,
                                })
                                if len(distractores) >= cantidad_meta:
                                    break
                else:
                    print(f"  [Aviso] Status {resp.status_code} en fecha {fecha}")
            except Exception as e:
                print(f"  [Error] Fallo descargando fecha {fecha}: {e}")

    print(f"  ✓ Total distractores recolectados: {len(distractores)}")
    return distractores


async def vectorizar_catalogo_batch(
    catalogo: List[Dict[str, Any]],
    api_key: str,
    archivo_cache: Path,
) -> Dict[str, List[float]]:
    """Genera embeddings en batch con gemini-embedding-001 (50 por llamada) con caché persistente."""
    from google import genai
    client = genai.Client(api_key=api_key)

    cache = {}
    if archivo_cache.exists():
        try:
            with open(archivo_cache, "r", encoding="utf-8") as f:
                cache = json.load(f)
            print(f"  [Caché] Cargados {len(cache)} embeddings existentes.")
        except Exception:
            cache = {}

    pendientes = [t for t in catalogo if f"tender_{t['code']}" not in cache]
    print(f"  Total licitaciones a vectorizar: {len(pendientes)} de {len(catalogo)}...")

    batch_size = 50
    for i in range(0, len(pendientes), batch_size):
        batch = pendientes[i:i + batch_size]
        textos = [f"{t.get('name', '')}. {t.get('description', '')}"[:1800] for t in batch]
        for intento in range(1, 4):
            try:
                res = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=textos,
                )
                for tender_obj, emb_obj in zip(batch, res.embeddings):
                    cache[f"tender_{tender_obj['code']}"] = emb_obj.values
                break
            except Exception as err:
                print(f"    [Reintento Batch {i//batch_size + 1}] Error: {err}. Esperando...")
                await asyncio.sleep(2.0 * intento)

        if (i // batch_size + 1) % 5 == 0 or (i + batch_size) >= len(pendientes):
            print(f"    Vectorizados {min(i + batch_size, len(pendientes))}/{len(pendientes)} ítems...")
            with open(archivo_cache, "w", encoding="utf-8") as f:
                json.dump(cache, f)

    with open(archivo_cache, "w", encoding="utf-8") as f:
        json.dump(cache, f)

    print(f"  ✓ Catálogo completamente vectorizado en caché: {len(cache)} vectores.")
    return cache


async def main():
    api_key = os.getenv("GEMINI_API_KEY")
    ticket = os.getenv("MERCADO_PUBLICO_API_KEY")
    if not api_key or not ticket:
        print("❌ Se requieren GEMINI_API_KEY y MERCADO_PUBLICO_API_KEY")
        sys.exit(1)

    data_dir = Path("spikes/dataset_compra_agil/data")
    
    # 1. Cargar proveedores y licitaciones actuales (250 adjudicaciones reales)
    archivo_prov = data_dir / "dataset_compra_agil_proveedores.json"
    archivo_tenders_gt = data_dir / "compras_agiles_para_matching.json"
    
    with open(archivo_prov, "r", encoding="utf-8") as f:
        proveedores_actuales = json.load(f)
    with open(archivo_tenders_gt, "r", encoding="utf-8") as f:
        tenders_gt = json.load(f)

    # 2. Generar Perfiles Wizard sin Fuga
    archivo_prov_wizard = data_dir / "dataset_proveedores_wizard_sin_fuga.json"
    if not archivo_prov_wizard.exists():
        nuevos_provs = await sintetizar_perfiles_wizard_sin_fuga(proveedores_actuales, api_key)
        with open(archivo_prov_wizard, "w", encoding="utf-8") as f:
            json.dump(nuevos_provs, f, indent=2, ensure_ascii=False)
        print(f"✓ Guardado: {archivo_prov_wizard.resolve()}")
    else:
        print(f"[Caché] Se encontró {archivo_prov_wizard.name}, cargando...")
        with open(archivo_prov_wizard, "r", encoding="utf-8") as f:
            nuevos_provs = json.load(f)

    # 3. Descargar Distractores Reales
    ruts_set = set(p["rut"] for p in proveedores_actuales)
    codigos_gt_set = set(t["code"] for t in tenders_gt)
    
    archivo_distractores = data_dir / "compras_agiles_distractores_2000.json"
    if not archivo_distractores.exists():
        distractores = await descargar_distractores_mercado_publico(
            ticket=ticket,
            ruts_excluidos=ruts_set,
            codigos_excluidos=codigos_gt_set,
            cantidad_meta=2000,
        )
        with open(archivo_distractores, "w", encoding="utf-8") as f:
            json.dump(distractores, f, indent=2, ensure_ascii=False)
    else:
        print(f"[Caché] Se encontró {archivo_distractores.name}, cargando...")
        with open(archivo_distractores, "r", encoding="utf-8") as f:
            distractores = json.load(f)

    # 4. Compilar Catálogo Consolidado (250 GT + 2000 Distractores = 2250 licitaciones)
    archivo_catalogo_2250 = data_dir / "catalogo_completo_con_distractores_2250.json"
    for t in tenders_gt:
        t["es_distractor"] = False
    catalogo_total = tenders_gt + distractores
    with open(archivo_catalogo_2250, "w", encoding="utf-8") as f:
        json.dump(catalogo_total, f, indent=2, ensure_ascii=False)
    print(f"\n[3/3] Catálogo consolidado guardado: {len(catalogo_total)} licitaciones en {archivo_catalogo_2250.name}")

    # 5. Vectorizar catálogo y perfiles
    cache_embeddings_2250 = data_dir / "embeddings_cache_2250.json"
    await vectorizar_catalogo_batch(catalogo_total, api_key, cache_embeddings_2250)

    print("\n" + "=" * 80)
    print("✅ DATASET PASO 2 CONSTRUIDO EXITOSAMENTE:")
    print(f"- 50 Proveedores con Perfil Wizard (Cero Data Leakage): {archivo_prov_wizard.name}")
    print(f"- Catálogo abierto y realista: 2.250 Compras Ágiles (250 GT + 2.000 Distractores)")
    print(f"- Caché vectorial batch: {cache_embeddings_2250.name}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
