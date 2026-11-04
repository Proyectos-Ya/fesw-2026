"""Palabras clave sugeridas a partir de la descripción de una empresa.

Extracción léxica, sin IA ni llamadas externas: la misma descripción da siempre las
mismas sugerencias y no gasta cuota de ningún proveedor.

Cómo elige
----------
1. Parte el texto en segmentos (puntuación y números cortan) y cada segmento en
   tramos de palabras con contenido. Las stopwords y las palabras de relleno
   ("empresa", "especializada") cortan el tramo; "de", "del", "para" y "en" solo
   unen dos palabras con contenido ("mantención de equipos").
2. Dentro de cada tramo toma n-gramas de 1 a 3 palabras. Son palabras completas del
   texto, con su ortografía, no raíces truncadas.
3. Ordena por puntaje. Pesan, de mayor a menor:
   * que sea una palabra clave de `activity_dictionary` (el vocabulario curado de
     compra pública; ahí cuentan frases de más de 3 palabras);
   * que `sector_classifier` lo asocie a un rubro del producto;
   * el largo (se prefieren los bigramas) y cuántas veces aparece.
4. Elige de a uno, de mayor a menor puntaje, y descarta lo que se traslapa con una
   sugerencia ya elegida en el texto.

Esta función es pura: no consulta la base de datos ni el perfil de la empresa.
"""

import re
import unicodedata
from dataclasses import dataclass

from app.application.services.company_profiling.activity_dictionary import (
    ACTIVITY_DICTIONARY,
)
from app.application.services.company_profiling.sector_classifier import (
    sectors_from_description,
)

# Tope de sugerencias: el paso 3 las muestra como chips y más de 10 vuelven a ser
# un listado que el usuario tiene que revisar entero.
MAX_SUGGESTIONS = 10

_MAX_NGRAM = 3
_MIN_UNIGRAM_LENGTH = 4

_SCORE_DICTIONARY = 100
_SCORE_SECTOR = 50
_SCORE_BY_LENGTH = {1: 5, 2: 10, 3: 8}
_SCORE_PER_REPETITION = 2
_MAX_REPETITION_BONUS = 6

# Une dos palabras con contenido; no puede abrir ni cerrar un término.
_CONNECTORS = frozenset({"de", "del", "para", "en"})

# Gramática del español, sin tildes (se compara con el texto ya normalizado).
_STOPWORDS = frozenset(
    """
    a al algo algun alguna algunas alguno algunos ante antes aqui asi aun aunque bajo
    cada casi como con contra cual cuales cuando cuyo de del desde donde dos durante e
    el ella ellas ello ellos en entre era eran eres es esa esas ese eso esos esta estaba
    estan estar estas este esto estos fue fueron ha han hace hacemos hacen hacer hasta
    hay he hemos la las le les lo los mas me mi mis mucho muchos muy nada ni no nos
    nosotros nuestra nuestras nuestro nuestros o os otra otras otro otros para pero poco
    por porque que quien quienes se sea segun ser si sido sin sobre solo son soy su sus
    tambien tan tanto te tiene tienen todas todo todos tras tu tus un una unas uno unos
    y ya yo
    """.split()
)

# Relleno propio de las descripciones de empresa: no dice qué se vende ni qué se hace.
_FILLER = frozenset(
    """
    empresa empresas compania companias firma organizacion dedicada dedicadas dedicado
    dedicados dedicamos especializada especializadas especializado especializados
    especializamos ofrecemos ofrece ofrecen realizamos realiza realizan brindamos
    brinda brindan prestamos presta prestan contamos cuenta cuentan trabajamos trabaja
    trabajan somos ano anos experiencia calidad clientes cliente mercado nivel amplia
    amplio diversas diversos diferentes distintas distintos variedad principalmente
    ademas tambien adicionalmente excelente mejor mejores nacional chile chilena
    chileno spa ltda limitada eirl
    """.split()
)

# Palabras con contenido tan genéricas que solas no sirven de palabra clave, pero que
# sí forman parte de términos útiles ("servicio técnico", "productos químicos").
_GENERIC_ALONE = frozenset(
    """
    servicio servicios producto productos trabajo trabajos soluciones solucion
    proyecto proyectos area areas equipo equipos sector sectores personal gestion
    general generales tipo tipos
    """.split()
)

_SEPARATORS = re.compile(r"[^\w\s]|\d|_")
_WORD = re.compile(r"[^\W\d_]+")


def _fold(text: str) -> str:
    """Minúsculas y sin tildes, para comparar."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _index_dictionary() -> tuple[dict[str, str], int]:
    """Palabras clave del diccionario por su forma sin tildes, y su largo máximo."""
    index: dict[str, str] = {}
    for entry in ACTIVITY_DICTIONARY.values():
        for keyword in entry.keywords:
            index.setdefault(_fold(keyword), keyword)
    longest = max((len(folded.split()) for folded in index), default=1)
    return index, longest


_DICTIONARY_INDEX, _DICTIONARY_MAX_WORDS = _index_dictionary()


@dataclass
class _Candidate:
    text: str
    folded: str
    first_at: int
    # Posiciones de palabra que ocupa su primera aparición en el texto.
    span: range
    score: int
    count: int = 1


@dataclass(frozen=True)
class _Word:
    shown: str
    folded: str
    position: int


def _words_by_segment(description: str) -> list[list[_Word]]:
    """Palabras del texto por segmento, con la posición global de cada una."""
    all_caps = description.isupper()
    segments: list[list[_Word]] = []
    position = 0
    for segment in _SEPARATORS.split(description):
        words: list[_Word] = []
        for raw in _WORD.findall(segment):
            # Las siglas cortas ("LED") se conservan; un texto entero en mayúsculas no.
            keep_upper = raw.isupper() and 2 <= len(raw) <= 4 and not all_caps
            words.append(
                _Word(raw if keep_upper else raw.lower(), _fold(raw), position)
            )
            position += 1
        if words:
            segments.append(words)
    return segments


def _is_boundary(word: _Word) -> bool:
    return (
        word.folded in _STOPWORDS or word.folded in _FILLER
    ) and word.folded not in _CONNECTORS


def _runs(words: list[_Word]) -> list[list[_Word]]:
    """Tramos de palabras con contenido, sin conectores en los extremos."""
    runs: list[list[_Word]] = []
    current: list[_Word] = []
    for word in words:
        if _is_boundary(word):
            runs.append(current)
            current = []
        else:
            current.append(word)
    runs.append(current)

    trimmed: list[list[_Word]] = []
    for run in runs:
        start, end = 0, len(run)
        while start < end and run[start].folded in _CONNECTORS:
            start += 1
        while end > start and run[end - 1].folded in _CONNECTORS:
            end -= 1
        if start < end:
            trimmed.append(run[start:end])
    return trimmed


def _is_valid_ngram(window: list[_Word]) -> bool:
    if window[0].folded in _CONNECTORS or window[-1].folded in _CONNECTORS:
        return False
    if any(
        a.folded in _CONNECTORS and b.folded in _CONNECTORS
        for a, b in zip(window, window[1:], strict=False)
    ):
        return False
    if len(window) == 1:
        word = window[0].folded
        return len(word) >= _MIN_UNIGRAM_LENGTH and word not in _GENERIC_ALONE
    return True


def _score(folded: str, text: str, words: int) -> int:
    score = _SCORE_BY_LENGTH.get(words, 0)
    if folded in _DICTIONARY_INDEX:
        score += _SCORE_DICTIONARY
    if sectors_from_description(text):
        score += _SCORE_SECTOR
    return score


def _collect_candidates(segments: list[list[_Word]]) -> dict[str, _Candidate]:
    candidates: dict[str, _Candidate] = {}
    order = 0

    def register(window: list[_Word], text: str, folded: str) -> None:
        nonlocal order
        found = candidates.get(folded)
        if found is not None:
            found.count += 1
            return
        span = range(window[0].position, window[-1].position + 1)
        candidates[folded] = _Candidate(
            text=text,
            folded=folded,
            first_at=order,
            span=span,
            score=_score(folded, text, len(window)),
        )
        order += 1

    for words in segments:
        # Frases del diccionario: se buscan en el texto corrido, sin cortar por
        # stopwords, y se devuelven con la ortografía curada.
        for size in range(1, _DICTIONARY_MAX_WORDS + 1):
            for start in range(len(words) - size + 1):
                window = words[start : start + size]
                folded = " ".join(w.folded for w in window)
                canonical = _DICTIONARY_INDEX.get(folded)
                if canonical is not None:
                    register(window, canonical, folded)

        for run in _runs(words):
            for size in range(1, _MAX_NGRAM + 1):
                for start in range(len(run) - size + 1):
                    window = run[start : start + size]
                    if not _is_valid_ngram(window):
                        continue
                    folded = " ".join(w.folded for w in window)
                    register(window, " ".join(w.shown for w in window), folded)
    return candidates


def suggest_keywords(
    description: str, existing_keywords: list[str] | None = None
) -> list[str]:
    """Hasta `MAX_SUGGESTIONS` palabras clave sacadas de `description`, mejores primero.

    No devuelve las que ya están en `existing_keywords` (se comparan sin tildes ni
    mayúsculas). Con texto vacío, o solo stopwords, devuelve una lista vacía.
    """
    if not description or not description.strip():
        return []

    taken = {_fold(keyword).strip() for keyword in existing_keywords or []}
    candidates = _collect_candidates(_words_by_segment(description))

    def rank(candidate: _Candidate) -> tuple[int, int]:
        repetitions = min(
            (candidate.count - 1) * _SCORE_PER_REPETITION, _MAX_REPETITION_BONUS
        )
        return (-(candidate.score + repetitions), candidate.first_at)

    chosen: list[_Candidate] = []
    occupied: set[int] = set()
    for candidate in sorted(candidates.values(), key=rank):
        if len(chosen) == MAX_SUGGESTIONS:
            break
        if candidate.folded in taken or occupied.intersection(candidate.span):
            continue
        chosen.append(candidate)
        occupied.update(candidate.span)
    return [candidate.text for candidate in chosen]
