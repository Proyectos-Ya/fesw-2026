import asyncio
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

backend_path = Path("monorepo/backend").resolve()
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.infrastructure.services.bge_m3_embedding_service import BgeM3EmbeddingService

data_dir = Path("spikes/dataset_compra_agil/data")
archivo_catalogo = data_dir / "catalogo_completo_con_distractores_2250.json"
archivo_prov = data_dir / "dataset_proveedores_wizard_sin_fuga.json"
archivo_cache = data_dir / "embeddings_bge_m3_2250.json"

with open(archivo_catalogo, "r", encoding="utf-8") as f:
    catalogo = json.load(f)

with open(archivo_prov, "r", encoding="utf-8") as f:
    proveedores = json.load(f)

print(f"Cargando BgeM3EmbeddingService (BAAI/bge-m3, 1024 dimensiones)...")
svc = BgeM3EmbeddingService()

cache = {}
if archivo_cache.exists():
    try:
        with open(archivo_cache, "r", encoding="utf-8") as f:
            cache = json.load(f)
        print(f"Cargados {len(cache)} embeddings previos desde {archivo_cache.name}")
    except Exception:
        cache = {}

async def main():
    t0 = time.time()
    
    # 1. Vectorizar licitaciones del catálogo (2250)
    pendientes_tenders = [t for t in catalogo if f"tender_{t['code']}" not in cache]
    print(f"Licitaciones pendientes de vectorizar: {len(pendientes_tenders)} de {len(catalogo)}")

    batch_size = 64
    for i in range(0, len(pendientes_tenders), batch_size):
        batch = pendientes_tenders[i:i + batch_size]
        textos = []
        for t in batch:
            items_str = ". ".join([it.get("nombre", "") for it in t.get("items", [])[:4]])
            txt = f"{t.get('name', '')}. {t.get('description', '')}. Partidas: {items_str}"
            textos.append(txt[:1500])

        vectors = await svc.embed(textos)
        for t_obj, v in zip(batch, vectors):
            cache[f"tender_{t_obj['code']}"] = v

        if (i // batch_size + 1) % 5 == 0 or (i + batch_size) >= len(pendientes_tenders):
            elapsed = time.time() - t0
            done = min(i + batch_size, len(pendientes_tenders))
            rate = done / max(elapsed, 0.1)
            print(f"  [Licitaciones] Vectorizados {done}/{len(pendientes_tenders)} ({rate:.1f} items/s)...")
            with open(archivo_cache, "w", encoding="utf-8") as f:
                json.dump(cache, f)

    # 2. Vectorizar los 50 perfiles de proveedores Wizard
    pendientes_prov = [p for p in proveedores if f"prov_{p['rut']}" not in cache]
    print(f"\nProveedores pendientes de vectorizar: {len(pendientes_prov)} de {len(proveedores)}")
    if pendientes_prov:
        textos_prov = []
        for p in pendientes_prov:
            pw = p["perfil_wizard"]
            txt = (
                f"Proveedor: {pw.get('legal_name')}. "
                f"Rubros: {', '.join(pw.get('sectors', []))}. "
                f"Descripción: {pw.get('description', '')}. "
                f"Especialidades comerciales: {', '.join(pw.get('keywords', []))}."
            )
            textos_prov.append(txt[:1500])

        vectors_prov = await svc.embed(textos_prov)
        for p_obj, v in zip(pendientes_prov, vectors_prov):
            cache[f"prov_{p_obj['rut']}"] = v

    with open(archivo_cache, "w", encoding="utf-8") as f:
        json.dump(cache, f)

    total_time = time.time() - t0
    print(f"\n✓ Vectorización BGE-M3 completa en {total_time:.1f}s.")
    print(f"Total vectores guardados en {archivo_cache.name}: {len(cache)}")

if __name__ == "__main__":
    asyncio.run(main())
