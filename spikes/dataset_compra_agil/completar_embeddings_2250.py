import asyncio
import json
import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

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

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

data_dir = Path("spikes/dataset_compra_agil/data")
archivo_catalogo = data_dir / "catalogo_completo_con_distractores_2250.json"
archivo_prov = data_dir / "dataset_proveedores_wizard_sin_fuga.json"
archivo_cache = data_dir / "embeddings_cache_2250.json"

with open(archivo_catalogo, "r", encoding="utf-8") as f:
    catalogo = json.load(f)

with open(archivo_prov, "r", encoding="utf-8") as f:
    proveedores = json.load(f)

cache = {}
if archivo_cache.exists():
    with open(archivo_cache, "r", encoding="utf-8") as f:
        cache = json.load(f)

print(f"Embeddings actualmente en caché: {len(cache)} de {len(catalogo) + len(proveedores)}")

async def embed_batch_safe(textos):
    for intento in range(1, 8):
        try:
            res = client.models.embed_content(
                model="gemini-embedding-001",
                contents=textos,
            )
            return [e.values for e in res.embeddings]
        except Exception as e:
            err_str = str(e)
            espera = 22.0 if "429" in err_str else (3.0 * intento)
            print(f"    [429 Quota Rate Limit] Esperando {espera:.1f}s antes de reintentar...")
            await asyncio.sleep(espera)
    return None

async def main():
    # 1. Completar licitaciones faltantes
    pendientes = [t for t in catalogo if f"tender_{t['code']}" not in cache]
    print(f"Licitaciones pendientes: {len(pendientes)}")

    batch_size = 50
    for i in range(0, len(pendientes), batch_size):
        batch = pendientes[i:i + batch_size]
        textos = [f"{t.get('name', '')}. {t.get('description', '')}"[:1800] for t in batch]
        
        vectors = await embed_batch_safe(textos)
        if vectors:
            for t_obj, v in zip(batch, vectors):
                cache[f"tender_{t_obj['code']}"] = v
            print(f"  Guardado batch {i//batch_size + 1}/{(len(pendientes) + batch_size - 1)//batch_size}. Total en caché: {len(cache)}")
            with open(archivo_cache, "w", encoding="utf-8") as f:
                json.dump(cache, f)
        
        # Pequeña pausa para mantenerse dentro de 100 req/min
        await asyncio.sleep(1.0)

    # 2. Vectorizar los 50 perfiles de proveedores Wizard
    prov_pendientes = [p for p in proveedores if f"prov_{p['rut']}" not in cache]
    print(f"Proveedores pendientes de vectorizar: {len(prov_pendientes)}")
    if prov_pendientes:
        textos_prov = []
        for p in prov_pendientes:
            pw = p["perfil_wizard"]
            txt = f"Proveedor: {pw.get('legal_name')}. Rubros: {', '.join(pw.get('sectors', []))}. Descripción: {pw.get('description', '')}. Especialidades: {', '.join(pw.get('keywords', []))}."
            textos_prov.append(txt[:1800])
        
        vectors = await embed_batch_safe(textos_prov)
        if vectors:
            for p_obj, v in zip(prov_pendientes, vectors):
                cache[f"prov_{p_obj['rut']}"] = v
            with open(archivo_cache, "w", encoding="utf-8") as f:
                json.dump(cache, f)

    print(f"\n✓ Proceso finalizado. Total embeddings persistidos en {archivo_cache.name}: {len(cache)}")

if __name__ == "__main__":
    asyncio.run(main())
