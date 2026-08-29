"""Benchmark de extracción de texto sobre el corpus del Spike 1.

Contexto
--------
El Spike 1 tiene que decidir con qué se leen los documentos del producto: las
bases de una licitación (#157) y el E-RUT o certificado de vigencia de una
empresa (#156). La decisión no se puede tomar por reputación de las librerías;
se toma con cifras sobre documentos reales, separadas por calidad del documento.

Lo que se mide **no es solo si aparece el RUT**. El uso más exigente del texto
es el RAG de las HdU 04 y 05.x —un asistente que responde citando las bases—, y
ahí el insumo es el documento entero. Un extractor puede acertar todos los
campos y aun así entregar un texto que no sirve para indexar: sin acentos, con
las columnas intercaladas o con basura entre las palabras. Ver `ocr_bench/metrics.py`.

Uso
---
    python benchmark.py --listar                      # qué extractores hay instalados
    python benchmark.py                               # todo el corpus, todos los extractores
    python benchmark.py --extractores pdfplumber gemini
    python benchmark.py --categorias escaneado-malo   # dónde se rompen
    python benchmark.py --json resultados.json --md tablas.md

Salida: tablas Markdown por extractor y categoría de calidad, listas para pegar
en `1.2-ocr-alternativas.md`. Con `--json` queda además el detalle documento a
documento, que es lo que permite reproducir una cifra en vez de creerle.

Código de salida: 0 si corrió, 1 si el corpus está vacío o ningún extractor
estaba disponible (una tabla vacía no es un resultado).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# `puente_backend.py` vive en `poc/`, un nivel arriba de este script (que está
# en `poc/ocr/`). Sin esto, `ocr_bench.dominio` no lo encuentra: al correr
# `python benchmark.py`, Python solo agrega al `sys.path` la carpeta del
# script que se ejecuta, no la de sus padres.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

# Credenciales de Gemini/Unstructured/LlamaParse (ver `.env.example`). Mismo
# mecanismo que `perfilamiento/`: sin esto habría que exportar variables a
# mano en la terminal, lo que no funciona bien si se corre desde un editor.
load_dotenv(Path(__file__).resolve().parent / ".env")

from ocr_bench.corpus import cargar_corpus
from ocr_bench.extractors import REGISTRO, disponibles
from ocr_bench.report import (
    advertencias,
    agregar,
    tabla_campos,
    tabla_corpus,
    tabla_disponibilidad,
    tabla_errores,
    tabla_texto,
)
from ocr_bench.runner import correr

# `poc/ocr/benchmark.py` -> `poc/ocr/` -> `poc/` -> `spike-1/` -> `corpus/`
CORPUS_POR_DEFECTO = Path(__file__).resolve().parents[2] / "corpus"


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mide la calidad de extracción de texto por librería y por "
        "calidad de documento.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=CORPUS_POR_DEFECTO,
        help=f"Carpeta del corpus (por defecto: {CORPUS_POR_DEFECTO})",
    )
    parser.add_argument(
        "--extractores",
        nargs="+",
        choices=sorted(REGISTRO),
        help="Extractores a probar. Por defecto, todos los instalados.",
    )
    parser.add_argument(
        "--categorias",
        nargs="+",
        help="Limitar a estas categorías de calidad (nombres de carpeta).",
    )
    parser.add_argument(
        "--tipos",
        nargs="+",
        help="Limitar a estos tipos de documento (campo 'tipo' del .gt.json).",
    )
    parser.add_argument(
        "--listar",
        action="store_true",
        help="Mostrar qué extractores están disponibles y salir.",
    )
    parser.add_argument("--json", type=Path, help="Guardar el detalle por documento.")
    parser.add_argument("--md", type=Path, help="Guardar las tablas en un archivo.")
    return parser


def _informe(documentos, resultado) -> str:
    agregados = agregar(resultado.filas)
    partes = [
        "## Corpus",
        "",
        tabla_corpus(documentos),
        "",
        "## Calidad de extracción de texto (lo que alimenta el RAG)",
        "",
        "CER y WER: menos es mejor. El resto: más es mejor.",
        "",
        tabla_texto(agregados),
        "",
        "## Extracción de campos (#156 onboarding, #157 validación)",
        "",
        tabla_campos(agregados),
        "",
        "## Errores",
        "",
        tabla_errores(resultado.filas),
    ]

    if resultado.omitidos:
        partes += [
            "",
            "## No probados",
            "",
            "Distinguir esto de un mal resultado: acá no hubo medición.",
            "",
            *[f"- {motivo}" for motivo in resultado.omitidos],
        ]

    avisos = advertencias(documentos, resultado.filas)
    if avisos:
        partes += ["", "## Cómo leer estas cifras", "", *[f"- {a}" for a in avisos]]

    return "\n".join(partes)


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    if args.listar:
        print(tabla_disponibilidad(disponibles()))
        return 0

    try:
        documentos = cargar_corpus(args.corpus)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.categorias:
        documentos = [d for d in documentos if d.categoria in args.categorias]
    if args.tipos:
        documentos = [d for d in documentos if d.tipo in args.tipos]

    if not documentos:
        print(
            f"error: no hay documentos que medir en {args.corpus}.\n"
            "Los archivos del corpus no se versionan (ver corpus/.gitignore): hay "
            "que conseguirlos, o generar una muestra controlada degradando PDFs "
            "digitales con `python degradar.py`.",
            file=sys.stderr,
        )
        return 1

    resultado = correr(documentos, args.extractores)

    if not resultado.filas:
        print("error: ningún extractor disponible pudo correr.", file=sys.stderr)
        for motivo in resultado.omitidos:
            print(f"  - {motivo}", file=sys.stderr)
        return 1

    informe = _informe(documentos, resultado)
    print(informe)

    if args.md:
        args.md.write_text(informe + "\n", encoding="utf-8")
        print(f"\n[tablas guardadas en {args.md}]", file=sys.stderr)

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "filas": [f.as_dict() for f in resultado.filas],
                    "omitidos": resultado.omitidos,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[detalle guardado en {args.json}]", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
