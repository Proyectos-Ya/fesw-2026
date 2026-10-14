"""Verificación de citas contra el texto del documento (plan 233, decisión 4).

Algoritmo:
1. Normalizar ambos lados: unir palabras cortadas por guion al final de línea, NFKD
   sin marcas combinantes (tildes, ligaduras como "ﬁ"), casefold y solo [0-9a-z]
   separados por un espacio.
2. Coincidencia exacta sobre límites de token.
3. Si no y la cita tiene al menos 4 tokens: cobertura difusa. Se toman hasta 3
   tokens de la cita, los más raros entre los que existen en el documento, como
   anclas. Para cada posición de un ancla se prueban ventanas de largo m + max(2, m//5)
   que empiezan a ±2 tokens de donde calzaría la cita. Cobertura = tokens de la cita
   que aparecen en orden en la ventana (bloques de SequenceMatcher) / m.
4. Se acepta con cobertura >= 0,85: tolera palabras partidas o pegadas por pypdf y
   una o dos palabras omitidas o cambiadas; una paráfrasis queda bajo 0,7.
Una cita con elipsis se parte y cada fragmento se verifica por separado.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.domain.entities.attachment_extraction import AttachmentExtractionData

UMBRAL_DE_COBERTURA = 0.85
MIN_TOKENS_DIFUSO = 4
_ANCLAS = 3
_POSICIONES_POR_ANCLA = 200  # acota el costo con tokens frecuentes
_DESPLAZAMIENTOS = (-2, -1, 0, 1, 2)
_ELIPSIS = re.compile(r"\[\.\.\.\]|\.{3,}|…")
_NO_ALFANUMERICO = re.compile(r"[^0-9a-z]+")


def normalizar_para_citas(texto: str) -> str:
    texto = texto.replace("-\n", "")
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c)).casefold()
    return " ".join(_NO_ALFANUMERICO.sub(" ", texto).split())


@dataclass(frozen=True)
class IndiceDeTexto:
    tokens: tuple[str, ...]
    plano: str  # " " + " ".join(tokens) + " "
    posiciones: dict[str, tuple[int, ...]]

    @classmethod
    def desde_secciones(cls, secciones: Sequence[str]) -> "IndiceDeTexto":
        tokens = tuple(normalizar_para_citas("\n".join(secciones)).split())
        posiciones: dict[str, list[int]] = {}
        for i, token in enumerate(tokens):
            posiciones.setdefault(token, []).append(i)
        return cls(
            tokens,
            f" {' '.join(tokens)} ",
            {t: tuple(p) for t, p in posiciones.items()},
        )


def verificar_cita(cita: str, indice: IndiceDeTexto | None) -> bool:
    if indice is None or not indice.tokens:
        return False
    fragmentos = [
        f
        for f in (normalizar_para_citas(x).split() for x in _ELIPSIS.split(cita))
        if f
    ]
    return bool(fragmentos) and all(_presente(f, indice) for f in fragmentos)


def _presente(q: list[str], indice: IndiceDeTexto) -> bool:
    if f" {' '.join(q)} " in indice.plano:
        return True
    if len(q) < MIN_TOKENS_DIFUSO:
        return False  # una cita corta calza en cualquier parte: solo vale exacta
    return _mejor_cobertura(q, indice) >= UMBRAL_DE_COBERTURA


def _mejor_cobertura(q: list[str], indice: IndiceDeTexto) -> float:
    m = len(q)
    holgura = max(2, m // 5)
    presentes = [t for t in set(q) if t in indice.posiciones]
    anclas = sorted(
        presentes, key=lambda t: (len(indice.posiciones[t]), -len(t))
    )[:_ANCLAS]
    inicios: set[int] = set()
    for ancla in anclas:
        en_cita = [i for i, t in enumerate(q) if t == ancla]
        for p in indice.posiciones[ancla][:_POSICIONES_POR_ANCLA]:
            for i in en_cita:
                for d in _DESPLAZAMIENTOS:
                    inicios.add(max(0, p - i + d))
    mejor = 0.0
    for inicio in inicios:
        ventana = indice.tokens[inicio : inicio + m + holgura]
        bloques = SequenceMatcher(
            None, q, ventana, autojunk=False
        ).get_matching_blocks()
        mejor = max(mejor, sum(b.size for b in bloques) / m)
        if mejor >= 1.0:
            break
    return mejor


def verificar_extraccion(
    data: AttachmentExtractionData, indice: IndiceDeTexto | None
) -> AttachmentExtractionData:
    copia = data.model_copy(deep=True)
    for cita in copia.todas_las_citas():
        cita.verificada = verificar_cita(cita.cita, indice)
    return copia
