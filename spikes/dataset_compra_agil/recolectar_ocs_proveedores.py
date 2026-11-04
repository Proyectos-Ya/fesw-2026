"""
Spike 2 - Paso A2: Re-descarga el detalle de las 250 OCs ganadas por los 50 proveedores del benchmark.

El dataset original no guardó la fecha (viene anidada en `Fechas.FechaEnvio`), lo que impedía el split
temporal. Aquí se guarda el detalle crudo completo (fechas, categoría UNSPSC, región, ítems).
Reanudable mediante JSONL.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
for ep in [ROOT / ".env", ROOT / "monorepo" / ".env", ROOT / "monorepo" / "backend" / ".env"]:
    if ep.exists():
        load_dotenv(ep)

BASE = "https://api.mercadopublico.cl/servicios/v1/publico/ordenesdecompra.json"
DATA = ROOT / "spikes" / "dataset_compra_agil" / "data"


async def main():
    ticket = os.getenv("MERCADO_PUBLICO_API_KEY")
    provs = json.loads((DATA / "dataset_compra_agil_proveedores.json").read_text(encoding="utf-8"))
    pares = [(p["rut"], o["codigo_oc"]) for p in provs for o in p["ordenes_compra_adjudicadas"]]
    out = DATA / "temporal" / "ocs_proveedores_detalle.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    hechos = set()
    if out.exists():
        hechos = {json.loads(l)["codigo"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()}
    pendientes = [(r, c) for r, c in pares if c not in hechos]
    print(f"OCs de proveedores: {len(pares)} | pendientes: {len(pendientes)}")
    fallidas = 0
    async with httpx.AsyncClient() as client:
        with open(out, "a", encoding="utf-8") as f:
            for i, (rut, cod) in enumerate(pendientes, 1):
                listado = []
                for intento in range(1, 7):
                    try:
                        r = await client.get(f"{BASE}?codigo={cod}&ticket={ticket}", timeout=60.0)
                        if r.status_code == 200:
                            listado = r.json().get("Listado", [])
                            break
                        if r.status_code == 429 or r.status_code >= 500:
                            await asyncio.sleep(min(60, 4.0 * intento))
                            continue
                        break
                    except Exception:
                        await asyncio.sleep(2.0 * intento)
                if listado:
                    f.write(json.dumps({"codigo": cod, "rut_proveedor_dataset": rut, "oc": listado[0]}, ensure_ascii=False) + "\n")
                    f.flush()
                else:
                    fallidas += 1
                if i % 50 == 0:
                    print(f"  {i}/{len(pendientes)} (fallidas={fallidas})")
                await asyncio.sleep(1.0)
    print(f"Terminado. fallidas={fallidas}")


if __name__ == "__main__":
    asyncio.run(main())
