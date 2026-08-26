"""Adaptadores para cada alternativa de extracción de texto que se evalúa.

Todos exponen la misma interfaz (`Extractor.extraer`) para que el benchmark no
tenga que saber si detrás hay un parser de PDF, un OCR local o un servicio en la
nube. Agregar un candidato es escribir una subclase y registrarla en
`REGISTRO`.

Las importaciones son perezosas a propósito: la escalera de costo del spike va
de librerías triviales de instalar a modelos de cientos de megas, y hay que
poder correr el benchmark con lo que esté instalado en vez de exigir todo. Un
extractor no disponible se reporta como tal en la tabla — que también es un
resultado: "no lo probamos" y "lo probamos y falló" no son lo mismo.

Nota sobre el orden de la escalera: los tres primeros **no son OCR**. Leen la
capa de texto que el PDF ya trae. Si el documento es digital, ganan siempre —
son exactos, cuestan milisegundos y no tienen dependencias pesadas. Recién
cuando esa capa no existe (un escaneo es una imagen dentro de un PDF) tiene
sentido pagar el costo del OCR.
"""

from __future__ import annotations

import os
import platform
import shutil
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

# Resolución a la que se rasterizan las páginas antes de pasarlas a un OCR.
# 300 DPI es el estándar de facto para documentos de texto: por debajo de 200 la
# tasa de error de Tesseract sube de forma marcada, y por encima de 400 el
# tiempo crece sin ganancia. Se deja como constante para poder barrerla.
DPI_OCR = 300

# Idioma para los motores que lo reciben como parámetro. Sin esto, Tesseract
# asume inglés y destroza los acentos: es el error de configuración más común y
# el que más ensucia una comparación entre motores.
IDIOMA = "spa"


@dataclass(frozen=True)
class Extraccion:
    """Lo que devuelve cualquier extractor sobre un documento."""

    extractor: str
    paginas: list[str]
    segundos: float
    error: str | None = None

    @property
    def texto(self) -> str:
        return "\n".join(self.paginas)

    @property
    def paginas_vacias(self) -> int:
        """Páginas que salieron sin texto útil.

        Es la forma silenciosa de fallar: el extractor no lanza excepción,
        simplemente devuelve nada para esa página. En un RAG eso es un tramo del
        documento que jamás se va a poder citar, y no se nota mirando el total.
        """
        return sum(1 for p in self.paginas if len(p.strip()) < 10)


class Extractor(ABC):
    """Interfaz común. Una subclase por candidato."""

    nombre: str = "sin-nombre"
    # Cómo clasificarlo en el informe: leer la capa de texto, OCR local, o
    # servicio en la nube (que además tiene costo por página).
    familia: str = "texto"
    extensiones: tuple[str, ...] = (".pdf",)

    @abstractmethod
    def disponible(self) -> tuple[bool, str]:
        """¿Se puede correr acá? Devuelve (sí/no, motivo si no)."""

    @abstractmethod
    def _paginas(self, ruta: Path) -> list[str]:
        """Extrae el texto, una entrada por página."""

    def soporta(self, ruta: Path) -> bool:
        return ruta.suffix.lower() in self.extensiones

    def extraer(self, ruta: Path) -> Extraccion:
        """Corre la extracción midiendo el tiempo y sin propagar errores.

        Un extractor que revienta con un documento no debe cortar el benchmark:
        que un motor falle con los escaneados malos es exactamente uno de los
        resultados que se busca, así que se registra y se sigue.
        """
        inicio = time.perf_counter()
        try:
            paginas = self._paginas(ruta)
            error = None
        except Exception as exc:  # noqa: BLE001 - se reporta, no se oculta
            paginas = []
            error = f"{type(exc).__name__}: {exc}"
        return Extraccion(
            extractor=self.nombre,
            paginas=paginas,
            segundos=time.perf_counter() - inicio,
            error=error,
        )


def _falta(modulo: str, paquete: str) -> tuple[bool, str]:
    return False, f"falta el módulo {modulo} (pip install {paquete})"


# --------------------------------------------------------------------------
# Escalón 1 — capa de texto del PDF. Sin OCR, sin modelos, milisegundos.
# --------------------------------------------------------------------------


class PdfplumberExtractor(Extractor):
    """pdfplumber (sobre pdfminer.six). El más cuidadoso con el layout.

    Reconstruye posiciones carácter a carácter, así que respeta mejor columnas y
    tablas que los demás parsers. A cambio es el más lento de los tres — del
    orden de decenas de veces más que PyMuPDF en documentos largos.
    """

    nombre = "pdfplumber"
    familia = "texto"

    def disponible(self) -> tuple[bool, str]:
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            return _falta("pdfplumber", "pdfplumber")
        return True, ""

    def _paginas(self, ruta: Path) -> list[str]:
        import pdfplumber

        with pdfplumber.open(ruta) as pdf:
            return [pagina.extract_text() or "" for pagina in pdf.pages]


class PyMuPDFExtractor(Extractor):
    """PyMuPDF (fitz). El más rápido de la capa de texto.

    Ojo con la licencia: PyMuPDF es AGPL. Para uso interno da lo mismo, pero si
    en algún momento el backend se distribuye, hay que revisarlo o comprar
    licencia comercial. pypdfium2 (abajo) es la alternativa con licencia
    permisiva.
    """

    nombre = "pymupdf"
    familia = "texto"

    def disponible(self) -> tuple[bool, str]:
        try:
            import pymupdf as fitz  # noqa: F401
        except ImportError:
            return _falta("pymupdf", "pymupdf")
        return True, ""

    def _paginas(self, ruta: Path) -> list[str]:
        import pymupdf as fitz

        with fitz.open(ruta) as documento:
            # sort=True ordena los bloques por posición en la página en vez de
            # por orden interno del PDF. Sin esto, un documento a dos columnas
            # sale intercalado y `reading_order` lo delata.
            return [pagina.get_text("text", sort=True) for pagina in documento]


class Pypdfium2Extractor(Extractor):
    """pypdfium2, envoltorio de PDFium (el motor de Chrome).

    Licencia permisiva (BSD/Apache) y binarios livianos. Es la opción sensata si
    la licencia de PyMuPDF llegara a ser un problema.
    """

    nombre = "pypdfium2"
    familia = "texto"

    def disponible(self) -> tuple[bool, str]:
        try:
            import pypdfium2  # noqa: F401
        except ImportError:
            return _falta("pypdfium2", "pypdfium2")
        return True, ""

    def _paginas(self, ruta: Path) -> list[str]:
        import pypdfium2

        documento = pypdfium2.PdfDocument(ruta)
        try:
            return [pagina.get_textpage().get_text_range() for pagina in documento]
        finally:
            documento.close()


class PyMuPDF4LLMExtractor(Extractor):
    """pymupdf4llm: la misma capa de texto, pero emitida como Markdown.

    Es el escalón directamente relevante para RAG. Conserva títulos, listas y
    tablas como estructura en vez de aplanarlas, lo que permite cortar los
    chunks por sección en vez de cada N caracteres. Contra las métricas de texto
    plano puntúa **peor** que PyMuPDF —los `#` y `|` cuentan como tokens de
    ruido— así que hay que leerlo sabiendo eso: lo que aporta es estructura, y
    eso no se ve en el CER.
    """

    nombre = "pymupdf4llm"
    familia = "texto-estructurado"

    def disponible(self) -> tuple[bool, str]:
        try:
            import pymupdf4llm  # noqa: F401
        except ImportError:
            return _falta("pymupdf4llm", "pymupdf4llm")
        return True, ""

    def _paginas(self, ruta: Path) -> list[str]:
        import pymupdf4llm

        trozos = pymupdf4llm.to_markdown(str(ruta), page_chunks=True)
        return [str(trozo["text"]) for trozo in trozos]


class DocxExtractor(Extractor):
    """python-docx, para los adjuntos .docx del corpus.

    No es OCR ni compite con los demás: un .docx trae el texto en claro y la
    extracción es exacta. Está acá porque el corpus real los incluye
    (`ADJUNTO TÉCNICO.docx`) y el pipeline tiene que cubrirlos.
    """

    nombre = "python-docx"
    familia = "texto"
    extensiones = (".docx",)

    def disponible(self) -> tuple[bool, str]:
        try:
            import docx  # noqa: F401
        except ImportError:
            return _falta("docx", "python-docx")
        return True, ""

    def _paginas(self, ruta: Path) -> list[str]:
        import docx

        documento = docx.Document(str(ruta))
        partes = [p.text for p in documento.paragraphs]
        # Las tablas no están en `paragraphs` y en las bases suelen llevar los
        # plazos y montos. Omitirlas sería perder justo lo que más importa.
        for tabla in documento.tables:
            for fila in tabla.rows:
                partes.append(" | ".join(celda.text for celda in fila.cells))
        # Un .docx no tiene páginas hasta que se renderiza: se devuelve como una
        # sola "página" y el conteo de páginas vacías queda en 0 o 1.
        return ["\n".join(partes)]


# --------------------------------------------------------------------------
# Escalón 2 — OCR local. Solo tiene sentido cuando no hay capa de texto.
# --------------------------------------------------------------------------


def rasterizar(ruta: Path, dpi: int = DPI_OCR) -> list[bytes]:
    """Convierte cada página del PDF en un PNG en memoria.

    Los motores de OCR reciben imágenes, no PDFs. Se centraliza acá para que
    todos los motores vean exactamente el mismo insumo: si cada uno rasterizara
    a su manera, la comparación mediría el rasterizador y no el OCR.
    """
    import pymupdf as fitz

    matriz = fitz.Matrix(dpi / 72, dpi / 72)
    with fitz.open(ruta) as documento:
        return [
            pagina.get_pixmap(matrix=matriz).tobytes("png") for pagina in documento
        ]


class TesseractExtractor(Extractor):
    """Tesseract vía pytesseract. El OCR local de referencia.

    Maduro, gratis, offline y empaquetable en la imagen Docker. Su debilidad
    conocida son los documentos torcidos y con ruido — justo la categoría
    `escaneado-malo`, que es donde esta comparación se decide.

    Requiere el binario del sistema **y** el paquete de idioma español, que se
    instala aparte (`brew install tesseract-lang`,
    `apt-get install tesseract-ocr-spa`). Sin `spa` corre igual pero en inglés,
    y ahí el resultado no significa nada.
    """

    nombre = "tesseract"
    familia = "ocr-local"

    def disponible(self) -> tuple[bool, str]:
        try:
            import pytesseract  # noqa: F401
        except ImportError:
            return _falta("pytesseract", "pytesseract")
        if shutil.which("tesseract") is None:
            return False, "falta el binario tesseract (brew install tesseract)"
        try:
            import pytesseract as pt

            if IDIOMA not in pt.get_languages():
                return False, (
                    f"falta el paquete de idioma '{IDIOMA}' "
                    "(brew install tesseract-lang)"
                )
        except Exception as exc:  # noqa: BLE001
            return False, f"no se pudo consultar los idiomas: {exc}"
        return True, ""

    def _paginas(self, ruta: Path) -> list[str]:
        import io

        import pytesseract
        from PIL import Image

        paginas = []
        for png in rasterizar(ruta):
            with Image.open(io.BytesIO(png)) as imagen:
                paginas.append(pytesseract.image_to_string(imagen, lang=IDIOMA))
        return paginas


class OcrmacExtractor(Extractor):
    """Apple Vision (framework del sistema) vía ocrmac. Solo macOS.

    Vale la pena medirlo aunque no sea desplegable: es gratis, offline, muy
    bueno en español y suele superar a Tesseract en escaneos torcidos. Sirve
    como **cota superior de lo local** — si Vision tampoco puede con un
    documento, el problema es el documento y no el motor.

    **No se puede llevar a producción**: la imagen del backend es Linux. Si
    resultara ser el único que alcanza la calidad necesaria, ese hallazgo por sí
    solo empuja hacia OCR en la nube.
    """

    nombre = "apple-vision"
    familia = "ocr-local"

    def disponible(self) -> tuple[bool, str]:
        if platform.system() != "Darwin":
            return False, "solo disponible en macOS"
        try:
            import ocrmac  # noqa: F401
        except ImportError:
            return _falta("ocrmac", "ocrmac")
        return True, ""

    def _paginas(self, ruta: Path) -> list[str]:
        import io

        from ocrmac import ocrmac as motor
        from PIL import Image

        paginas = []
        for png in rasterizar(ruta):
            with Image.open(io.BytesIO(png)) as imagen:
                anotaciones = motor.OCR(
                    imagen, language_preference=["es-ES"]
                ).recognize()
                paginas.append("\n".join(texto for texto, _, _ in anotaciones))
        return paginas


class PaddleOCRExtractor(Extractor):
    """PaddleOCR. Modelo de detección + reconocimiento, mejor con documentos torcidos.

    Es el escalón caro de lo local: instala PaddlePaddle y descarga modelos
    (cientos de megas), y sin GPU es lento. Se justifica solo si Tesseract se
    cae en la categoría `escaneado-malo`, que es exactamente la hipótesis que el
    benchmark pone a prueba. Trae corrección de ángulo integrada, que es la
    diferencia concreta con Tesseract en fotos de celular.
    """

    nombre = "paddleocr"
    familia = "ocr-local"

    def disponible(self) -> tuple[bool, str]:
        try:
            import paddleocr  # noqa: F401
        except ImportError:
            return _falta("paddleocr", "paddleocr (ver requirements-motores-pesados.txt)")
        return True, ""

    def _paginas(self, ruta: Path) -> list[str]:
        import io

        import numpy as np
        from paddleocr import PaddleOCR
        from PIL import Image

        # El modelo se carga una vez por documento, no por página: la carga
        # domina el tiempo y contarla por página inflaría el costo unitario.
        motor = PaddleOCR(use_angle_cls=True, lang="es", show_log=False)
        paginas = []
        for png in rasterizar(ruta):
            with Image.open(io.BytesIO(png)) as imagen:
                arreglo = np.array(imagen.convert("RGB"))
            resultado = motor.ocr(arreglo, cls=True)
            lineas = []
            for bloque in resultado or []:
                for entrada in bloque or []:
                    lineas.append(str(entrada[1][0]))
            paginas.append("\n".join(lineas))
        return paginas


# --------------------------------------------------------------------------
# Escalón 3 — OCR en la nube. Nada de esto llama a una red por su cuenta: solo
# se activa si la variable de entorno correspondiente está seteada. Elegido el
# extractor local (Tesseract), este escalón queda listo para cuando llegue el
# momento de comparar contra un servicio pagado — que el plan del spike deja
# explícitamente para después, no para ahora.
# --------------------------------------------------------------------------


class ExtractorEnLaNube(Extractor):
    """Base común de los proveedores de nube: todos cobran por página y necesitan
    una credencial, así que todos comparten el mismo candado de disponibilidad.

    Agregar un proveedor nuevo es escribir `_paginas_por_documento` (una llamada
    HTTP) y `_VARIABLE_ENDPOINT`/`_VARIABLE_TOKEN`; el resto —detección de
    disponibilidad, medición de tiempo, captura de errores— ya está en
    `Extractor.extraer`. Cambiar de proveedor en el benchmark es solo pasar otro
    nombre en `--extractores`, no tocar el resto del arnés.
    """

    familia = "ocr-nube"

    # Nombres de las variables de entorno que cada subclase debe declarar.
    _VARIABLE_ENDPOINT: str = ""
    _VARIABLE_TOKEN: str = ""

    def disponible(self) -> tuple[bool, str]:
        if not os.environ.get(self._VARIABLE_ENDPOINT):
            return False, (
                f"falta configurar {self._VARIABLE_ENDPOINT} "
                "(no se hace ninguna llamada de red sin esto)"
            )
        if self._VARIABLE_TOKEN and not os.environ.get(self._VARIABLE_TOKEN):
            return False, f"falta configurar {self._VARIABLE_TOKEN}"
        return True, ""

    def _endpoint(self) -> str:
        return os.environ[self._VARIABLE_ENDPOINT]

    def _token(self) -> str | None:
        return os.environ.get(self._VARIABLE_TOKEN) if self._VARIABLE_TOKEN else None


class GeminiExtractor(ExtractorEnLaNube):
    """Gemini multimodal, leyendo la página como imagen.

    Es el candidato de menor fricción: el proyecto ya tiene cliente y
    credencial para Gemini (`gemini_deep_analysis_service.py`), así que no hay
    integración nueva que mantener. Su riesgo propio es la **alucinación**:
    puede devolver texto plausible que no está en la página. Por eso conviene
    mirar `token_precision` con más atención en este extractor que en los
    demás — es la métrica que la delata.
    """

    nombre = "gemini"
    _VARIABLE_ENDPOINT = "GEMINI_OCR_URL"
    _VARIABLE_TOKEN = "GEMINI_API_KEY"

    def _paginas(self, ruta: Path) -> list[str]:
        raise NotImplementedError(
            "llamada a Gemini pendiente de implementar: ver "
            "gemini_deep_analysis_service.py para el cliente ya existente en "
            "el backend. No se implementa hasta decidir consultarlo de verdad."
        )


class DocumentAIExtractor(ExtractorEnLaNube):
    """Google Document AI. Cobra por página; fuerte en formularios y tablas."""

    nombre = "document-ai"
    _VARIABLE_ENDPOINT = "DOCUMENT_AI_URL"
    _VARIABLE_TOKEN = "DOCUMENT_AI_TOKEN"

    def _paginas(self, ruta: Path) -> list[str]:
        raise NotImplementedError("llamada a Document AI pendiente de implementar.")


class MistralOCRExtractor(ExtractorEnLaNube):
    """Mistral OCR. Cobra por página; salida pensada para RAG (Markdown)."""

    nombre = "mistral-ocr"
    _VARIABLE_ENDPOINT = "MISTRAL_OCR_URL"
    _VARIABLE_TOKEN = "MISTRAL_API_KEY"

    def _paginas(self, ruta: Path) -> list[str]:
        raise NotImplementedError("llamada a Mistral OCR pendiente de implementar.")


REGISTRO: dict[str, Extractor] = {
    extractor.nombre: extractor
    for extractor in (
        PdfplumberExtractor(),
        PyMuPDFExtractor(),
        Pypdfium2Extractor(),
        PyMuPDF4LLMExtractor(),
        DocxExtractor(),
        TesseractExtractor(),
        OcrmacExtractor(),
        PaddleOCRExtractor(),
        GeminiExtractor(),
        DocumentAIExtractor(),
        MistralOCRExtractor(),
    )
}


def disponibles() -> dict[str, str]:
    """Diagnóstico: qué extractor está listo y por qué no lo está el resto."""
    return {
        nombre: "" if ok else motivo
        for nombre, extractor in REGISTRO.items()
        for ok, motivo in [extractor.disponible()]
    }
