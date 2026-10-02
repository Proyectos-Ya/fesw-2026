"""
Antes de cargar el catálogo de producción sobre ChiripaTest SIN borrar el catálogo de prueba:
comprueba que el xlsx exportado no choque con las licitaciones que ya están cargadas.

`load_postgres_robust.py` inserta con ON CONFLICT (id) DO NOTHING, pero `tender.code` tiene un
índice único aparte (ix_tender_code): si el xlsx trae un código que ya existe con OTRO id, el
INSERT falla a mitad de la carga. Este script lo detecta antes y no escribe nada.

Lee data/temporal/catalogo_prueba_ids.csv (id,code de las 1.176 licitaciones de prueba) y la hoja
`tender` de project-data/chiripa_tenders.xlsx.

Uso (desde monorepo/backend, con el .venv activo):
  python ../../spikes/dataset_compra_agil/verificar_choque_con_catalogo_prueba.py
"""

import csv
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PRUEBA = ROOT / "spikes" / "dataset_compra_agil" / "data" / "temporal" / "catalogo_prueba_ids.csv"
XLSX = ROOT / "project-data" / "chiripa_tenders.xlsx"


def main() -> None:
    if not PRUEBA.exists() or not XLSX.exists():
        raise SystemExit(f"Falta {PRUEBA if not PRUEBA.exists() else XLSX}")
    with open(PRUEBA, encoding="utf-8", newline="") as f:
        prueba = {fila["id"]: fila["code"] for fila in csv.DictReader(f)}
    codigos_prueba = {c: i for i, c in prueba.items()}

    xlsx = pd.read_excel(XLSX, "tender")
    ids_xlsx = [str(i).lower() for i in xlsx["id"]]
    codigos_xlsx = [str(c).strip() for c in xlsx["code"]]

    mismo_id = [i for i in ids_xlsx if i in prueba]
    choque_codigo = [
        (i, c) for i, c in zip(ids_xlsx, codigos_xlsx) if c in codigos_prueba and codigos_prueba[c] != i
    ]
    print(f"Catálogo de prueba en ChiripaTest : {len(prueba)} licitaciones")
    print(f"Licitaciones en el xlsx           : {len(xlsx)}")
    print(f"  con el mismo id (se omiten)     : {len(mismo_id)}")
    print(f"  con el mismo código y otro id   : {len(choque_codigo)}")
    if choque_codigo:
        for i, c in choque_codigo[:10]:
            print(f"    código {c}: id xlsx {i}, id en ChiripaTest {codigos_prueba[c]}")
        raise SystemExit("HAY CHOQUES DE CÓDIGO: la carga fallaría. No cargar sin resolverlos.")
    print("Sin choques: se puede cargar sin borrar nada.")


if __name__ == "__main__":
    main()
