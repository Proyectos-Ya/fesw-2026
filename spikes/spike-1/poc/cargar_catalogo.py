"""Lee el catálogo de actividades económicas del SII (.xlsx) y lo deja en JSON.

Por qué con la librería estándar
--------------------------------
Un .xlsx es un zip de XML. Leerlo con `zipfile` + `ElementTree` evita agregar
openpyxl o pandas al PoC para un archivo que se procesa una vez. El resultado es
un JSON plano que el resto del código consume sin depender del formato original.

Estructura del archivo
----------------------
No es una tabla limpia: mezcla datos con cabeceras.

    AGRICULTURA, GANADERÍA, SILVICULTURA Y PESCA     <- título de sección (solo col. A)
    Código | CULTIVO DE PLANTAS NO PERENNES          <- cabecera de grupo
                                                     <- fila en blanco
    11101  | CULTIVO DE TRIGO                        <- dato
    11102  | CULTIVO DE MAÍZ

Se conserva el título de sección y el de grupo de cada código: son contexto
gratis para decidir a qué rubro corresponde, y para revisar el mapeo a mano.

**El código se normaliza a 6 dígitos.** En el archivo aparece como `11101`
—cinco caracteres— porque el cero a la izquierda se pierde. Sin reponerlo, la
división se lee como 11 (bebidas) en vez de 01 (cultivos).

Uso
---
    python cargar_catalogo.py --xlsx ../corpus/"Dicionario codigos.xlsx"
    python cargar_catalogo.py --salida perfilamiento/catalogo_sii.json
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

XLSX_POR_DEFECTO = Path(__file__).resolve().parents[1] / "corpus" / "Dicionario codigos.xlsx"
SALIDA_POR_DEFECTO = Path(__file__).resolve().parent / "perfilamiento" / "catalogo_sii.json"


@dataclass(frozen=True)
class Fila:
    codigo: int
    glosa: str
    seccion_titulo: str
    grupo_titulo: str


def _cadenas_compartidas(zip_: zipfile.ZipFile) -> list[str]:
    """Tabla de strings del xlsx. Las celdas de texto son índices a esta lista."""
    try:
        raiz = ET.fromstring(zip_.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(t.text or "" for t in si.iter(f"{NS}t")) for si in raiz.iter(f"{NS}si")]


def _limpiar(texto: str) -> str:
    """Quita espacios duros y colapsa el resto.

    Excel deja `\\xa0` de relleno en las cabeceras; si no se saca, una glosa
    aparentemente idéntica no coincide con otra al compararla.
    """
    return " ".join(texto.replace("\xa0", " ").split())


def leer(xlsx: Path) -> list[Fila]:
    """Devuelve una fila por código, con su sección y grupo."""
    with zipfile.ZipFile(xlsx) as zip_:
        compartidas = _cadenas_compartidas(zip_)
        hoja = ET.fromstring(zip_.read("xl/worksheets/sheet1.xml"))

    def valor(celda: ET.Element) -> str:
        v = celda.find(f"{NS}v")
        if v is None or v.text is None:
            en_linea = celda.find(f"{NS}is")
            if en_linea is None:
                return ""
            return _limpiar("".join(t.text or "" for t in en_linea.iter(f"{NS}t")))
        if celda.get("t") == "s":
            return _limpiar(compartidas[int(v.text)])
        return _limpiar(v.text)

    filas: list[Fila] = []
    seccion = ""
    grupo = ""

    for fila_xml in hoja.iter(f"{NS}row"):
        celdas = {}
        for celda in fila_xml.iter(f"{NS}c"):
            referencia = celda.get("r") or ""
            columna = "".join(c for c in referencia if c.isalpha())
            celdas[columna] = valor(celda)

        a = celdas.get("A", "")
        b = celdas.get("B", "")

        if a and not b:
            # Título de sección: ocupa la fila sola.
            seccion = a
            continue
        if a == "Código":
            # Cabecera de grupo: el nombre del grupo viene en la columna B.
            grupo = b
            continue
        if not a or not a.isdigit():
            continue

        codigo = a.zfill(6)
        filas.append(
            Fila(
                codigo=int(codigo),
                glosa=b,
                seccion_titulo=seccion,
                grupo_titulo=grupo,
            )
        )

    return filas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--xlsx", type=Path, default=XLSX_POR_DEFECTO)
    parser.add_argument("--salida", type=Path, default=SALIDA_POR_DEFECTO)
    args = parser.parse_args(argv)

    if not args.xlsx.exists():
        print(f"error: no existe {args.xlsx}", file=sys.stderr)
        return 1

    filas = leer(args.xlsx)
    if not filas:
        print("error: no se extrajo ningún código", file=sys.stderr)
        return 1

    repetidos = len(filas) - len({f.codigo for f in filas})
    args.salida.write_text(
        json.dumps([asdict(f) for f in filas], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    print(f"{len(filas)} códigos -> {args.salida}")
    if repetidos:
        print(f"  ojo: {repetidos} códigos repetidos en el archivo")
    secciones = {f.seccion_titulo for f in filas}
    print(f"  {len(secciones)} secciones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
