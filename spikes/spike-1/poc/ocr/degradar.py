"""Genera un corpus degradado —y con ground truth exacto— a partir de PDFs digitales.

Por qué existe
--------------
El benchmark necesita dos cosas caras de conseguir: documentos de mala calidad y
el texto correcto de cada uno. Este script resuelve las dos de una vez.

De un PDF digital se extrae su capa de texto, que es **exacta** (no es una
estimación: es literalmente el texto que el generador del PDF escribió). Ese
texto queda como `.gt.txt`. Después la página se rasteriza, se maltrata —se
rota, se baja la resolución, se agrega ruido y compresión— y se vuelve a
empaquetar como PDF **sin capa de texto**. El resultado es un documento que solo
se puede leer con OCR, y del que se conoce la respuesta correcta carácter por
carácter.

Eso permite medir la curva completa —digital, escaneado limpio, escaneado
malo— sin conseguir ni etiquetar un solo escaneo a mano.

Lo que esto **no** es
---------------------
Una degradación sintética no reproduce un escaneo real: no tiene textura de
papel, ni tóner disparejo, ni el desenfoque irregular de una foto tomada a
pulso, ni grapas o dobleces. Sirve para **comparar motores entre sí bajo la
misma presión** y para encontrar el punto donde cada uno se quiebra. No sirve
para prometer una tasa de éxito en producción; para eso hacen falta escaneos
reales, aunque sean pocos.

Uso
---
    python degradar.py --entrada ../corpus/digital
    python degradar.py --entrada ../corpus/digital --perfiles malo --dpi 100
    python degradar.py --entrada ../corpus/digital --salida /tmp/corpus-sintetico
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass, replace
from pathlib import Path

# `poc/ocr/degradar.py` -> `poc/ocr/` -> `poc/` -> `spike-1/` -> `corpus/`
CORPUS_POR_DEFECTO = Path(__file__).resolve().parents[2] / "corpus"

# Mínimo de caracteres para considerar que un PDF trae capa de texto usable. Un
# escaneado suele devolver 0 y un digital, miles; el umbral solo evita generar
# un ground truth vacío a partir de un PDF que no era digital.
MIN_CARACTERES = 200


@dataclass(frozen=True)
class Perfil:
    """Una receta de degradación.

    Cada parámetro imita un defecto concreto de un documento real:

    - `dpi`: resolución del escaneo. Es la variable que más pesa; bajo 200 DPI
      la tasa de error de cualquier OCR sube de golpe.
    - `angulo`: hojas puestas torcidas en el escáner o fotos a pulso. Los
      motores sin corrección de ángulo se caen acá.
    - `desenfoque`: cámara mal enfocada.
    - `ruido`: grano del sensor y polvo del vidrio.
    - `calidad_jpeg`: artefactos de compresión, que es como llegan casi todos
      los documentos enviados por correo o WhatsApp.
    - `sombra`: gradiente de iluminación, la firma de una foto de celular.
    """

    nombre: str
    carpeta: str
    dpi: int
    angulo: float = 0.0
    desenfoque: float = 0.0
    ruido: float = 0.0
    calidad_jpeg: int = 90
    sombra: float = 0.0


PERFILES: dict[str, Perfil] = {
    "limpio": Perfil(
        nombre="limpio",
        carpeta="escaneado-limpio",
        dpi=300,
        ruido=2.0,
        calidad_jpeg=85,
    ),
    "malo": Perfil(
        nombre="malo",
        carpeta="escaneado-malo",
        dpi=120,
        angulo=1.8,
        desenfoque=0.8,
        ruido=12.0,
        calidad_jpeg=40,
        sombra=0.35,
    ),
}


def texto_de_referencia(ruta: Path) -> str:
    """Devuelve la capa de texto del PDF, que hace de ground truth."""
    import pymupdf as fitz

    with fitz.open(ruta) as documento:
        return "\n".join(pagina.get_text("text", sort=True) for pagina in documento)


def _degradar_imagen(imagen, perfil: Perfil, rng):
    """Aplica el perfil a una página ya rasterizada."""
    import numpy as np
    from PIL import Image, ImageFilter

    # Escala de grises: es como escanea cualquier equipo de oficina en el modo
    # por defecto, y le quita al OCR una ayuda que en la práctica no tendría.
    imagen = imagen.convert("L")

    if perfil.angulo:
        # `expand=False` recorta las esquinas, igual que un documento que se
        # sale del área útil del escáner. `fillcolor=255` deja fondo blanco.
        imagen = imagen.rotate(
            perfil.angulo, resample=Image.BICUBIC, expand=False, fillcolor=255
        )

    if perfil.desenfoque:
        imagen = imagen.filter(ImageFilter.GaussianBlur(perfil.desenfoque))

    arreglo = np.asarray(imagen).astype(np.float32)

    if perfil.sombra:
        # Gradiente horizontal: un lado de la hoja más oscuro, como cuando el
        # celular tapa la luz. Va de 1.0 a (1 - sombra) de izquierda a derecha.
        ancho = arreglo.shape[1]
        gradiente = np.linspace(1.0, 1.0 - perfil.sombra, ancho, dtype=np.float32)
        arreglo *= gradiente[np.newaxis, :]

    if perfil.ruido:
        arreglo += rng.normal(0.0, perfil.ruido, arreglo.shape).astype(np.float32)

    arreglo = np.clip(arreglo, 0, 255).astype("uint8")
    return Image.fromarray(arreglo, mode="L")


def degradar_pdf(origen: Path, destino: Path, perfil: Perfil, semilla: int) -> int:
    """Escribe en `destino` una versión solo-imagen y degradada de `origen`.

    Devuelve la cantidad de páginas escritas.
    """
    import io

    import pymupdf as fitz
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(semilla)
    matriz = fitz.Matrix(perfil.dpi / 72, perfil.dpi / 72)

    salida = fitz.open()
    try:
        with fitz.open(origen) as documento:
            for pagina in documento:
                png = pagina.get_pixmap(matrix=matriz).tobytes("png")
                with Image.open(io.BytesIO(png)) as imagen:
                    degradada = _degradar_imagen(imagen, perfil, rng)

                # Se pasa por JPEG a propósito: la pérdida de la compresión es
                # parte de la degradación, no un detalle de implementación.
                buffer = io.BytesIO()
                degradada.save(buffer, format="JPEG", quality=perfil.calidad_jpeg)

                nueva = salida.new_page(width=pagina.rect.width, height=pagina.rect.height)
                nueva.insert_image(nueva.rect, stream=buffer.getvalue())

        destino.parent.mkdir(parents=True, exist_ok=True)
        # Sin metadatos: PyMuPDF estampa fecha de creación, y eso hace que dos
        # corridas idénticas produzcan archivos distintos byte a byte. El
        # contenido sí es reproducible (el ruido va con semilla fija).
        salida.set_metadata({})
        salida.save(destino)
        return salida.page_count
    finally:
        salida.close()


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Genera versiones escaneadas sintéticas, con ground truth "
        "exacto, a partir de PDFs digitales.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--entrada",
        type=Path,
        default=CORPUS_POR_DEFECTO / "digital",
        help="Carpeta con los PDFs digitales de origen.",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=CORPUS_POR_DEFECTO,
        help="Raíz del corpus donde se escriben las carpetas degradadas.",
    )
    parser.add_argument(
        "--perfiles",
        nargs="+",
        choices=sorted(PERFILES),
        default=sorted(PERFILES),
        help="Perfiles de degradación a generar.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        help="Sobrescribe el DPI del perfil (útil para barrer el punto de quiebre).",
    )
    parser.add_argument(
        "--semilla",
        type=int,
        default=20260825,
        help="Semilla del ruido. Fija por defecto: dos corridas deben dar el "
        "mismo corpus, o las cifras no se pueden reproducir.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    if not args.entrada.is_dir():
        print(f"error: no existe la carpeta {args.entrada}", file=sys.stderr)
        return 1

    origenes = sorted(args.entrada.glob("*.pdf"))
    if not origenes:
        print(f"error: no hay PDFs en {args.entrada}", file=sys.stderr)
        return 1

    generados = 0
    for indice, origen in enumerate(origenes):
        referencia = texto_de_referencia(origen)
        if len(referencia.strip()) < MIN_CARACTERES:
            print(
                f"omitido {origen.name}: solo {len(referencia.strip())} caracteres "
                "de capa de texto. Sin ground truth confiable no sirve como origen "
                "(¿es un escaneado que quedó en la carpeta 'digital'?).",
                file=sys.stderr,
            )
            continue

        # El ground truth del propio digital también se escribe: sin él, la fila
        # 'digital' de la tabla queda sin CER y no hay contra qué comparar.
        origen.with_suffix(".gt.txt").write_text(referencia, encoding="utf-8")

        for nombre_perfil in args.perfiles:
            perfil = PERFILES[nombre_perfil]
            if args.dpi:
                perfil = replace(perfil, dpi=args.dpi)

            destino = args.salida / perfil.carpeta / f"{origen.stem}__{perfil.nombre}.pdf"
            paginas = degradar_pdf(origen, destino, perfil, args.semilla + indice)

            # El ground truth viaja con la copia: es el mismo texto, porque lo
            # único que cambió es cómo se ve la página.
            destino.with_suffix(".gt.txt").write_text(referencia, encoding="utf-8")
            campos = origen.with_suffix(".gt.json")
            if campos.exists():
                shutil.copyfile(campos, destino.with_suffix(".gt.json"))

            generados += 1
            print(f"{destino.relative_to(args.salida)}  ({paginas} pág, {perfil.dpi} dpi)")

    if not generados:
        print("error: no se generó ningún documento.", file=sys.stderr)
        return 1

    print(f"\n{generados} documentos degradados a partir de {len(origenes)} originales.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
