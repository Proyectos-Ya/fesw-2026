"""Servicio de tokenización léxica y codificación sparse para BM25 en Qdrant (Plan 256, Fase 1).

Produce vectores dispersos deterministas basados en hashing de 32 bits (fnv1a / sha256 truncado)
y cálculo de frecuencia de términos. El IDF es computado del lado servidor por Qdrant (Modifier.IDF).
"""

from collections import Counter
from dataclasses import dataclass
import hashlib
import re
import unicodedata

STOPWORDS_ES = frozenset(
    "de la el en y a los las del por para con un una al se que o su sus lo como mas son sin "
    "sobre este esta estos estas entre durante hasta hacia segun tras mediante contra donde "
    "cuando cual cuales quien quienes cada otro otra otros otras tanto tanta tantos tantas "
    "mucho mucha muchos muchas poco poca pocos pocas todo toda todos todas mismo misma mismos mismas".split()
)


def hash_term_to_uint32(term: str) -> int:
    """Calcula un hash de 32 bits determinista y estable entre procesos y plataformas."""
    digest = hashlib.sha256(term.encode("utf-8")).digest()
    # Tomar los primeros 4 bytes como uint32 big-endian
    val = int.from_bytes(digest[:4], byteorder="big", signed=False)
    # Rango en uint32 positivo [0, 2^32 - 1]
    return val % (2**32)


@dataclass(frozen=True)
class SparseTermVector:
    """Representación de un vector disperso compatible con Qdrant SparseVector."""

    indices: list[int]
    values: list[float]


class LexicalTokenizer:
    """Tokenizador liviano sin dependencias externas pesadas."""

    def __init__(self, stopwords: frozenset[str] = STOPWORDS_ES) -> None:
        self._stopwords = stopwords

    def normalize(self, text: str) -> str:
        """Remueve acentos, normaliza a minúsculas y elimina caracteres especiales."""
        if not text:
            return ""
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c)).lower()
        return text

    def stem(self, word: str) -> str:
        """Stemming ligero en español para unificar plurales y derivaciones comunes."""
        for suf in ("ciones", "cion", "mente", "idad", "ades", "es", "s"):
            if word.endswith(suf) and len(word) - len(suf) >= 4:
                return word[: -len(suf)]
        return word

    def tokenize(self, text: str) -> list[str]:
        """Tokeniza el texto extrayendo términos válidos y sin stopwords."""
        norm_text = self.normalize(text)
        words = re.findall(r"[a-z0-9]{3,}", norm_text)
        return [w for w in words if w not in self._stopwords]

    def stem_tokens(self, text: str) -> list[str]:
        """Tokeniza y aplica stemming a los términos resultantes."""
        tokens = self.tokenize(text)
        return [self.stem(t) for t in tokens]

    def encode_sparse(self, text: str) -> SparseTermVector:
        """Genera el vector disperso con frecuencias de término e índices uint32 ordenados."""
        stemmed = self.stem_tokens(text)
        if not stemmed:
            return SparseTermVector(indices=[], values=[])

        tf = Counter(stemmed)
        # Mapear término a índice uint32
        term_map: dict[int, float] = {}
        for term, count in tf.items():
            idx = hash_term_to_uint32(term)
            term_map[idx] = term_map.get(idx, 0.0) + float(count)

        # Ordenar por índice ascendente (requerimiento estricto de Qdrant SparseVector)
        sorted_indices = sorted(term_map.keys())
        sorted_values = [term_map[idx] for idx in sorted_indices]

        return SparseTermVector(indices=sorted_indices, values=sorted_values)
