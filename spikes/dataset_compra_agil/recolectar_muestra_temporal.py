"""
Spike 2 - Paso A: Recolección de una muestra temporal de Compras Ágiles (OCs) de Mercado Público.

Motivación: el benchmark anterior mezclaba 250 adjudicaciones con detalle completo y 2.000 distractores
que solo traían el título del listado. Aquí todas las órdenes salen del mismo endpoint de detalle
(mismo formato) y llevan el día en que se listaron, lo que permite un split temporal
(perfil con días anteriores, evaluación con días posteriores).

Reanudable: cada OC se guarda en un JSONL; si se interrumpe, al volver a correr retoma lo pendiente.
"""

import argparse
import asyncio
import json
import os
import random
import sys
from pathlib import Path
from typing import Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
for ep in [ROOT / ".env", ROOT / "monorepo" / ".env", ROOT / "monorepo" / "backend" / ".env"]:
    if ep.exists():
        load_dotenv(ep)

BASE = "https://api.mercadopublico.cl/servicios/v1/publico/ordenesdecompra.json"
DIAS = ["10092026", "11092026", "14092026", "15092026", "16092026", "17092026",
        "21092026", "22092026", "23092026", "24092026", "25092026"]


def es_ag(codigo: str) -> bool:
    c = codigo.upper()
    return "-AG" in c or "-COT" in c


async def get_json(client: httpx.AsyncClient, url: str, intentos: int = 6):
    for i in range(1, intentos + 1):
        try:
            r = await client.get(url, timeout=60.0)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429 or r.status_code >= 500:
                await asyncio.sleep(min(60, 4.0 * i))
                continue
            return None
        except Exception:
            await asyncio.sleep(2.0 * i)
    return None


async def main(por_dia: int, pausa: float, out_dir: Path):
    ticket = os.getenv("MERCADO_PUBLICO_API_KEY")
    if not ticket:
        print("Falta MERCADO_PUBLICO_API_KEY")
        sys.exit(1)
    out_dir.mkdir(parents=True, exist_ok=True)
    listados_path = out_dir / "listados_por_dia.json"
    detalle_path = out_dir / "ocs_detalle.jsonl"

    async with httpx.AsyncClient() as client:
        if listados_path.exists():
            listados: Dict[str, List[str]] = json.loads(listados_path.read_text(encoding="utf-8"))
        else:
            listados = {}
        for dia in DIAS:
            if dia in listados:
                continue
            data = await get_json(client, f"{BASE}?fecha={dia}&ticket={ticket}")
            codigos = [x["Codigo"] for x in (data or {}).get("Listado", []) if es_ag(str(x.get("Codigo", "")))]
            listados[dia] = codigos
            print(f"[listado] {dia}: {len(codigos)} compras ágiles")
            listados_path.write_text(json.dumps(listados), encoding="utf-8")
            await asyncio.sleep(pausa)

        rng = random.Random(42)
        muestra: List[tuple] = []
        for dia in DIAS:
            cods = sorted(listados.get(dia, []))
            rng.shuffle(cods)
            muestra += [(dia, c) for c in cods[:por_dia]]

        hechos = set()
        if detalle_path.exists():
            for line in detalle_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    hechos.add(json.loads(line)["codigo"])
        pendientes = [(d, c) for d, c in muestra if c not in hechos]
        print(f"[detalle] muestra={len(muestra)} ya_descargadas={len(hechos)} pendientes={len(pendientes)}")

        fallidas = 0
        with open(detalle_path, "a", encoding="utf-8") as f:
            for i, (dia, cod) in enumerate(pendientes, 1):
                data = await get_json(client, f"{BASE}?codigo={cod}&ticket={ticket}")
                listado = (data or {}).get("Listado", [])
                if listado:
                    f.write(json.dumps({"codigo": cod, "dia": dia, "oc": listado[0]}, ensure_ascii=False) + "\n")
                    f.flush()
                else:
                    fallidas += 1
                if i % 100 == 0:
                    print(f"  {i}/{len(pendientes)} (fallidas={fallidas})")
                await asyncio.sleep(pausa)
        print(f"[detalle] terminado. fallidas={fallidas}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--por-dia", type=int, default=200)
    ap.add_argument("--pausa", type=float, default=0.8)
    ap.add_argument("--out", type=str, default="spikes/dataset_compra_agil/data/temporal")
    a = ap.parse_args()
    asyncio.run(main(a.por_dia, a.pausa, Path(a.out)))
