"""Métricas de calidad de extracción de texto, orientadas a RAG.

Por qué no basta con "¿salió el RUT?"
-------------------------------------
El spike original medía extracción de campos (RUT, razón social, fechas). Eso
sirve para el onboarding, pero el uso más caro del texto es otro: las HdU 04 y
05.x quieren un asistente que responda **citando las bases**. Eso es RAG, y en
RAG el texto entero es el insumo. Un extractor puede acertar el RUT y aun así
producir un índice inservible si mezcla columnas, se come los acentos o mete
basura entre las palabras.

Por eso acá se mide el texto completo, con métricas que atacan cada forma
concreta en que un extractor arruina un RAG:

| Métrica | Qué falla si baja |
|---|---|
| `cer` / `wer` | fidelidad general carácter a carácter y palabra a palabra |
| `token_recall` | contenido que **se perdió**: si la respuesta no está en el chunk, el asistente no la puede citar |
| `token_precision` | basura **agregada**: ruido que contamina el índice y genera citas falsas |
| `diacritic_recall` | acentos y ñ. En español degradan el embedding y rompen la búsqueda literal |
| `digit_recall` | montos, plazos, RUTs y fechas. Es el error más caro del dominio |
| `reading_order` | orden de lectura. Un PDF a dos columnas mal leído entrega frases intercaladas |
| `empty_page_rate` | páginas que salieron vacías: pérdida silenciosa de documento |

Todas las tasas van en [0, 1]. En `cer`/`wer`, **menos es mejor**; en el resto,
más es mejor.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Sequence

try:  # pragma: no cover - depende del entorno
    from rapidfuzz.distance import Levenshtein as _Levenshtein

    _HAS_RAPIDFUZZ = True
except ImportError:  # pragma: no cover
    _Levenshtein = None
    _HAS_RAPIDFUZZ = False


# Caracteres que en español distinguen palabras y que el OCR pierde con más
# frecuencia. Se miden aparte porque un 2% de CER concentrado acá pesa mucho
# más que un 2% repartido: "mas" y "más" son palabras distintas para el
# embedding y para una búsqueda literal.
DIACRITICOS = set("áéíóúüñÁÉÍÓÚÜÑ")

_ESPACIOS = re.compile(r"\s+")
_NO_PALABRA = re.compile(r"[^0-9a-záéíóúüñ]+")
_DIGITOS = re.compile(r"\d+")


def normalizar_espacios(texto: str) -> str:
    """Colapsa cualquier corrida de espacios en blanco a uno solo.

    Los saltos de línea y la sangría dependen del extractor, no del documento:
    penalizarlos mediría formato en vez de contenido.
    """
    return _ESPACIOS.sub(" ", texto).strip()


def normalizar_para_cer(texto: str) -> str:
    """Normaliza el texto antes de comparar carácter a carácter.

    Baja a minúsculas y unifica la forma Unicode (NFC): un acento puede venir
    como un solo punto de código o como letra + combinante, y esa diferencia es
    invisible para una persona pero cuenta como error para una distancia de
    edición. Las tildes **sí** se conservan; perderlas es un error real.
    """
    return normalizar_espacios(unicodedata.normalize("NFC", texto)).lower()


def tokenizar(texto: str) -> list[str]:
    """Parte el texto en tokens comparables, conservando tildes y dígitos."""
    plano = normalizar_para_cer(texto)
    return [t for t in _NO_PALABRA.split(plano) if t]


def _sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def distancia_edicion(a: Sequence[str], b: Sequence[str]) -> int:
    """Distancia de Levenshtein entre dos secuencias.

    Usa rapidfuzz cuando está disponible (implementación en C, obligatoria en
    documentos largos: la versión en Python puro sobre dos textos de 100 mil
    caracteres es cuadrática y no termina en un tiempo razonable).
    """
    if _HAS_RAPIDFUZZ and _Levenshtein is not None:
        return int(_Levenshtein.distance(a, b))
    raise RuntimeError(
        "Falta rapidfuzz, que es obligatorio para calcular CER/WER sobre "
        "documentos completos. Instalar con: pip install -r requirements.txt"
    )


def _tasa(distancia: int, largo_referencia: int) -> float:
    if largo_referencia == 0:
        # Sin referencia no hay error que medir. Se reporta 0.0 y el llamador
        # decide: un documento sin ground truth no debería entrar al promedio.
        return 0.0
    return distancia / largo_referencia


def cer(esperado: str, obtenido: str) -> float:
    """Character Error Rate: errores de carácter por carácter de referencia."""
    ref = normalizar_para_cer(esperado)
    hip = normalizar_para_cer(obtenido)
    return _tasa(distancia_edicion(ref, hip), len(ref))


def wer(esperado: str, obtenido: str) -> float:
    """Word Error Rate: errores de palabra por palabra de referencia."""
    ref = tokenizar(esperado)
    hip = tokenizar(obtenido)
    return _tasa(distancia_edicion(ref, hip), len(ref))


def _multiconjunto(tokens: Sequence[str]) -> dict[str, int]:
    conteo: dict[str, int] = {}
    for token in tokens:
        conteo[token] = conteo.get(token, 0) + 1
    return conteo


def _interseccion(a: dict[str, int], b: dict[str, int]) -> int:
    return sum(min(cantidad, b.get(token, 0)) for token, cantidad in a.items())


def recall_precision_tokens(esperado: str, obtenido: str) -> tuple[float, float]:
    """Cuánto del contenido sobrevivió y cuánta basura se agregó.

    Se compara como multiconjunto y no como secuencia a propósito: es el modelo
    más cercano a cómo un índice de RAG usa el texto. Si la palabra está, el
    chunk la puede recuperar, aunque el orden se haya alterado. El orden se mide
    aparte en `orden_de_lectura`.

    - **recall**: fracción de tokens de referencia presentes en la extracción.
      Lo que baja acá es contenido irrecuperable — el asistente no lo puede citar
      porque no existe en el índice.
    - **precision**: fracción de tokens extraídos que estaban en la referencia.
      Lo que baja acá es ruido: fragmentos inventados por el OCR que el buscador
      puede llegar a recuperar como si fueran texto de las bases.
    """
    ref = _multiconjunto(tokenizar(esperado))
    hip = _multiconjunto(tokenizar(obtenido))
    comunes = _interseccion(ref, hip)
    total_ref = sum(ref.values())
    total_hip = sum(hip.values())
    recall = comunes / total_ref if total_ref else 0.0
    precision = comunes / total_hip if total_hip else 0.0
    return recall, precision


def recall_diacriticos(esperado: str, obtenido: str) -> float:
    """Recall restringido a los tokens que llevan tilde, diéresis o ñ.

    Un extractor que devuelve "licitacion" en vez de "licitación" puede tener un
    CER bajísimo y aun así degradar toda búsqueda literal en español. Esta
    métrica lo aísla: se calcula solo sobre los tokens de referencia que
    contienen alguno de esos caracteres, y **exige la forma acentuada exacta**.
    """
    ref = [t for t in tokenizar(esperado) if any(c in DIACRITICOS for c in t)]
    if not ref:
        return 1.0  # nada que perder en este documento
    hip = _multiconjunto(tokenizar(obtenido))
    return _interseccion(_multiconjunto(ref), hip) / len(ref)


def recall_digitos(esperado: str, obtenido: str) -> float:
    """Recall sobre las secuencias de dígitos: montos, plazos, RUTs, fechas.

    Es el error más caro del dominio. Confundir un 3 con un 8 en una fecha de
    cierre o en un monto no baja casi nada el CER, pero vuelve la respuesta del
    asistente derechamente falsa. Se comparan corridas completas de dígitos
    (`"2026"`, `"76086428"`), no dígitos sueltos: acertar el 2 de 2026 no es
    acertar el año.
    """
    ref = _DIGITOS.findall(esperado)
    if not ref:
        return 1.0
    hip = _DIGITOS.findall(obtenido)
    return _interseccion(_multiconjunto(ref), _multiconjunto(hip)) / len(ref)


def orden_de_lectura(esperado: str, obtenido: str) -> float:
    """Cuánto del orden original se conservó, medido sobre líneas.

    El caso que importa: las bases suelen venir a dos columnas o con cajas de
    texto flotantes, y un extractor que ignora el layout entrega las líneas
    intercaladas. El texto está completo — `token_recall` sale alto — pero las
    frases quedan partidas y el chunk que llega al modelo es incoherente.

    Se calcula como la subsecuencia común más larga entre las líneas de
    referencia y las extraídas, dividida por el número de líneas de referencia.
    Una extracción que trae todas las líneas pero en otro orden cae; una que las
    trae en orden con pequeñas diferencias de texto también, así que conviene
    leerla junto con `token_recall` y no sola.
    """
    ref = [normalizar_para_cer(l) for l in esperado.splitlines() if l.strip()]
    hip = [normalizar_para_cer(l) for l in obtenido.splitlines() if l.strip()]
    if not ref:
        return 1.0
    coincidencias = sum(
        bloque.size for bloque in SequenceMatcher(a=ref, b=hip).get_matching_blocks()
    )
    return coincidencias / len(ref)


@dataclass(frozen=True)
class MetricasTexto:
    """Resultado de comparar una extracción contra su ground truth."""

    cer: float
    wer: float
    token_recall: float
    token_precision: float
    diacritic_recall: float
    digit_recall: float
    reading_order: float
    gt_chars: int
    out_chars: int

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


def evaluar_texto(esperado: str, obtenido: str) -> MetricasTexto:
    """Aplica todas las métricas de texto de una vez."""
    recall, precision = recall_precision_tokens(esperado, obtenido)
    return MetricasTexto(
        cer=cer(esperado, obtenido),
        wer=wer(esperado, obtenido),
        token_recall=recall,
        token_precision=precision,
        diacritic_recall=recall_diacriticos(esperado, obtenido),
        digit_recall=recall_digitos(esperado, obtenido),
        reading_order=orden_de_lectura(esperado, obtenido),
        gt_chars=len(normalizar_para_cer(esperado)),
        out_chars=len(normalizar_para_cer(obtenido)),
    )


# --------------------------------------------------------------------------
# Métricas de campo — las del objetivo original del spike (#156 y #157).
# Se conservan porque el onboarding y la validación documental sí necesitan
# campos puntuales, no solo texto corrido.
# --------------------------------------------------------------------------

# Un RUT chileno tal como aparece impreso: con o sin puntos, con guion, y
# dígito verificador que puede ser K.
_RUT = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}\s*-\s*[\dkK]\b")

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# Los tres formatos que aparecen en documentos chilenos, en orden de frecuencia:
# 15/03/2026, 15-03-2026 y "15 de marzo de 2026".
_FECHA_NUMERICA = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
_FECHA_TEXTUAL = re.compile(
    r"\b(\d{1,2})\s+de\s+(" + "|".join(_MESES) + r")\s+(?:de\s+|del\s+)?(\d{4})\b"
)


def extraer_ruts(texto: str) -> list[str]:
    """Devuelve los RUTs encontrados, normalizados a `12345678-9` en mayúscula.

    No valida el dígito verificador: eso lo hace `is_valid_rut` del dominio, y
    conviene mantenerlo separado para poder medir dos cosas distintas — cuántos
    RUTs se detectaron y cuántos de esos son válidos. Un OCR que confunde un
    dígito produce un RUT bien formado pero inválido, y esa diferencia es
    justamente el hallazgo interesante.
    """
    encontrados = []
    for bruto in _RUT.findall(texto):
        limpio = bruto.replace(".", "").replace(" ", "").upper()
        encontrados.append(limpio)
    return encontrados


def extraer_fechas(texto: str) -> list[tuple[int, int, int]]:
    """Devuelve las fechas como tuplas (día, mes, año), en los tres formatos.

    Asume día-mes-año, que es el orden chileno. Un `03/04/2026` es 3 de abril,
    no 4 de marzo; la ambigüedad es real pero no se resuelve mirando el número.
    """
    fechas: list[tuple[int, int, int]] = []
    plano = normalizar_para_cer(texto)

    for dia, mes, anio in _FECHA_NUMERICA.findall(plano):
        a = int(anio)
        if a < 100:  # años de dos dígitos: 26 -> 2026
            a += 2000
        fechas.append((int(dia), int(mes), a))

    for dia, mes, anio in _FECHA_TEXTUAL.findall(plano):
        fechas.append((int(dia), _MESES[mes], int(anio)))

    return fechas


def evaluar_fechas_esperadas(esperadas: Sequence[str], texto: str) -> float:
    """Fracción de las fechas esperadas que aparece en el texto extraído.

    Las fechas esperadas se escriben en el `.gt.json` en cualquiera de los tres
    formatos y se comparan **normalizadas a (día, mes, año)**: da lo mismo que
    el documento diga `15/03/2026` y el ground truth `15 de marzo de 2026`, lo
    que se mide es si la fecha está, no cómo se escribió.

    Ojo con lo que esta métrica **no** responde: encontrar la fecha no es saber
    si es la de emisión, la de vigencia o la de vencimiento. Esa desambiguación
    es el problema real de #157 y se resuelve por contexto, no por regex.
    """
    objetivo = set()
    for texto_esperado in esperadas:
        objetivo.update(extraer_fechas(texto_esperado))
    if not objetivo:
        return 1.0
    encontradas = set(extraer_fechas(texto))
    return len(objetivo & encontradas) / len(objetivo)


def coincide_razon_social(esperado: str, texto: str, umbral: float = 0.9) -> bool:
    """¿Aparece la razón social en el texto extraído?

    Compara sin tildes y sin puntuación contra ventanas del mismo largo, porque
    una razón social casi nunca sale idéntica: sobra un punto, falta un acento o
    el OCR parte "LTDA." en dos. El umbral por defecto (0.9) tolera esos
    deslices sin aceptar una empresa distinta.
    """
    objetivo = _sin_tildes(normalizar_para_cer(esperado))
    objetivo = _NO_PALABRA.sub(" ", objetivo).strip()
    if not objetivo:
        return False

    plano = _sin_tildes(normalizar_para_cer(texto))
    plano = _NO_PALABRA.sub(" ", plano)

    palabras_objetivo = objetivo.split()
    palabras = plano.split()
    ventana = len(palabras_objetivo)
    for inicio in range(0, max(1, len(palabras) - ventana + 1)):
        candidato = " ".join(palabras[inicio : inicio + ventana])
        if SequenceMatcher(a=objetivo, b=candidato).ratio() >= umbral:
            return True
    return False
