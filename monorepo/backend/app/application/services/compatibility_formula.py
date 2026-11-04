"""Fórmula calibrada de compatibilidad mediante regresión logística.

Este módulo implementa un modelo de scoring ordinal basado en dos modelos logísticos:
- P(relevancia >= 1): probabilidad de que la partida sea relevante (afín o exacta)
- P(relevancia == 2): probabilidad de que sea exacta

El score final es la media ponderada: 0.5·p1 + 0.5·p2 ∈ [0,1].

Los coeficientes se calibraron sobre 1.146 pares juzgados con validación cruzada
por proveedor (AUC 0,75 vs 0,58 de la fórmula anterior).

Variables de entrada:
- reranker_score: similitud semántica del cross-encoder BGE (calibrada en [0,1])
- B = max(similitud coseno de cada keyword vs cada partida): mejor calce keyword↔partida
- C = promedio sobre partidas del máximo coseno por partida: cobertura
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CalibrationCoefficients:
    """Coeficientes de un modelo logístico calibrado."""

    intercept: float
    reranker: float  # coeficiente de logit(reranker_score)
    best_match: float  # coeficiente de B
    coverage: float  # coeficiente de C


@dataclass(frozen=True)
class CompatibilityFormula:
    """Modelo de scoring con dos modelos logísticos (relevancia y exactitud)."""

    relevant: CalibrationCoefficients  # modelo de P(relevancia >= 1)
    exact: CalibrationCoefficients  # modelo de P(relevancia == 2)

    def score(
        self, reranker_score: float, best_match: float, coverage: float
    ) -> float:
        """Calcula el score de compatibilidad.

        Args:
            reranker_score: similitud del cross-encoder en [0,1]
            best_match: mejor calce keyword↔partida en [0,1]
            coverage: cobertura (promedio de máximos) en [0,1]

        Returns:
            Score en [0,1] = 0.5·p1 + 0.5·min(p2, p1)
            donde p1 = σ(z_relevant), p2 = σ(z_exact), z = intercept + ...
        """
        # Clip para evitar log(0) o log(1)
        clipped_reranker = max(1e-6, min(reranker_score, 1.0 - 1e-6))
        logit_reranker = math.log(clipped_reranker / (1.0 - clipped_reranker))

        # P(relevancia >= 1)
        z_relevant = (
            self.relevant.intercept
            + self.relevant.reranker * logit_reranker
            + self.relevant.best_match * best_match
            + self.relevant.coverage * coverage
        )
        p1 = 1.0 / (1.0 + math.exp(-z_relevant))

        # P(relevancia == 2)
        z_exact = (
            self.exact.intercept
            + self.exact.reranker * logit_reranker
            + self.exact.best_match * best_match
            + self.exact.coverage * coverage
        )
        p2 = 1.0 / (1.0 + math.exp(-z_exact))

        # p2 nunca supera p1
        p2 = min(p2, p1)

        # Score final: media ponderada
        return 0.5 * p1 + 0.5 * p2


def item_match_signals(
    keyword_vectors: Sequence[Sequence[float]], item_vectors: Sequence[Sequence[float]]
) -> tuple[float, float]:
    """Calcula B (mejor calce) y C (cobertura) a partir de vectores.

    B = máximo global de la matriz de similitudes coseno (keyword × item)
    C = promedio sobre items del máximo coseno por item

    Args:
        keyword_vectors: lista de vectores de keywords (cada uno normalizable a norma unitaria)
        item_vectors: lista de vectores de partidas

    Returns:
        (B, C) donde ambos están en [0,1]. Si alguna lista está vacía, devuelve (0.0, 0.0).
    """
    if not keyword_vectors or not item_vectors:
        return (0.0, 0.0)

    # Convertir a numpy arrays
    keywords = np.array(keyword_vectors, dtype=np.float64)
    items = np.array(item_vectors, dtype=np.float64)

    # Normalizar vectores (evitar división por cero)
    keyword_norms = np.linalg.norm(keywords, axis=1, keepdims=True)
    keyword_norms[keyword_norms == 0] = 1  # vectores cero quedan como [0, 0, ...]
    keywords_normalized = keywords / keyword_norms

    item_norms = np.linalg.norm(items, axis=1, keepdims=True)
    item_norms[item_norms == 0] = 1
    items_normalized = items / item_norms

    # Matriz de similitudes coseno: (num_keywords, num_items)
    similarity_matrix = np.dot(keywords_normalized, items_normalized.T)

    # B: máximo global
    B = float(np.max(similarity_matrix))

    # C: promedio de máximos por item (columna)
    max_per_item = np.max(similarity_matrix, axis=0)
    C = float(np.mean(max_per_item))

    return (B, C)
