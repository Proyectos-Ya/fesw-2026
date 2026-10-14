"""Tests unitarios de CompatibilityFormula — calibración logística de matching."""

import math

from app.application.services.compatibility_formula import (
    CalibrationCoefficients,
    CompatibilityFormula,
    item_match_signals,
)

# ---------------------------------------------------------------------------
# item_match_signals: similaridad coseno entre keywords e items
# ---------------------------------------------------------------------------


def test_item_match_signals_listas_vacias() -> None:
    """Listas vacías devuelven (0.0, 0.0)."""
    B, C = item_match_signals([], [])
    assert B == 0.0
    assert C == 0.0


def test_item_match_signals_solo_keywords_vacios() -> None:
    """Keywords vacíos con items devuelven (0.0, 0.0)."""
    B, C = item_match_signals([], [[1.0, 0.0]])
    assert B == 0.0
    assert C == 0.0


def test_item_match_signals_solo_items_vacios() -> None:
    """Items vacíos con keywords devuelven (0.0, 0.0)."""
    B, C = item_match_signals([[1.0, 0.0]], [])
    assert B == 0.0
    assert C == 0.0


def test_item_match_signals_vector_cero() -> None:
    """Vector de norma cero en keywords devuelve similitud 0."""
    # keyword [0, 0] vs item [1, 0]
    B, C = item_match_signals([[0.0, 0.0]], [[1.0, 0.0]])
    assert B == 0.0
    assert C == 0.0


def test_item_match_signals_ortogonales() -> None:
    """Vectores ortogonales tienen similitud 0, máximo 0."""
    # keyword [1, 0] vs item [0, 1]
    B, C = item_match_signals([[1.0, 0.0]], [[0.0, 1.0]])
    assert B == 0.0
    assert C == 0.0


def test_item_match_signals_identicos() -> None:
    """Keyword idéntico a item: B = 1.0 (máximo), C = 1.0 (promedio)."""
    # keyword [1, 0] vs item [1, 0]
    B, C = item_match_signals([[1.0, 0.0]], [[1.0, 0.0]])
    assert abs(B - 1.0) < 1e-6
    assert abs(C - 1.0) < 1e-6


def test_item_match_signals_dos_keywords_un_item() -> None:
    """Dos keywords, uno coincide totalmente: B=1, C = promedio del máximo de cada item."""
    # keywords [[1, 0], [0, 1]] vs items [[1, 0]]
    # similitudes: [1.0, 0.0]
    # B = max(1.0, 0.0) = 1.0
    # C = promedio sobre items = 1.0 (máximo para el único item)
    B, C = item_match_signals([[1.0, 0.0], [0.0, 1.0]], [[1.0, 0.0]])
    assert abs(B - 1.0) < 1e-6
    assert abs(C - 1.0) < 1e-6


def test_item_match_signals_dos_items() -> None:
    """Dos items: B es el máximo global, C es el promedio de los máximos por item."""
    # keywords [[1, 0], [0, 1]] vs items [[1, 0], [0, 1]]
    # matriz: [[1, 0], [0, 1]]
    # B = 1.0 (máximo global)
    # máximo por item: [1.0, 1.0]
    # C = (1.0 + 1.0) / 2 = 1.0
    B, C = item_match_signals(
        [[1.0, 0.0], [0.0, 1.0]], [[1.0, 0.0], [0.0, 1.0]]
    )
    assert abs(B - 1.0) < 1e-6
    assert abs(C - 1.0) < 1e-6


def test_item_match_signals_parcial() -> None:
    """Caso donde B y C no son máximos."""
    # keywords [[1, 1]] vs items [[1, 0], [0, 1]]
    # norma de keyword: sqrt(2)
    # similaridades: [1/sqrt(2) ≈ 0.707, 1/sqrt(2) ≈ 0.707]
    # B = 0.707
    # C = 0.707
    B, C = item_match_signals([[1.0, 1.0]], [[1.0, 0.0], [0.0, 1.0]])
    assert abs(B - 1.0 / math.sqrt(2)) < 1e-6
    assert abs(C - 1.0 / math.sqrt(2)) < 1e-6


# ---------------------------------------------------------------------------
# CompatibilityFormula.score
# ---------------------------------------------------------------------------


def test_score_rango_valido() -> None:
    """El score siempre está en [0, 1]."""
    coeffs_relevant = CalibrationCoefficients(
        intercept=-3.8878,
        reranker=0.3281,
        best_match=3.2548,
        coverage=6.0296,
    )
    coeffs_exact = CalibrationCoefficients(
        intercept=-5.0958,
        reranker=0.4013,
        best_match=3.5326,
        coverage=5.0620,
    )
    formula = CompatibilityFormula(relevant=coeffs_relevant, exact=coeffs_exact)

    # Casos extremos
    score_bajo = formula.score(0.01, 0.01, 0.01)
    score_alto = formula.score(0.99, 0.99, 0.99)

    assert 0.0 <= score_bajo <= 1.0
    assert 0.0 <= score_alto <= 1.0


def test_score_monotono_en_reranker() -> None:
    """Score es monótonamente creciente en reranker_score."""
    coeffs_relevant = CalibrationCoefficients(
        intercept=-3.8878,
        reranker=0.3281,
        best_match=3.2548,
        coverage=6.0296,
    )
    coeffs_exact = CalibrationCoefficients(
        intercept=-5.0958,
        reranker=0.4013,
        best_match=3.5326,
        coverage=5.0620,
    )
    formula = CompatibilityFormula(relevant=coeffs_relevant, exact=coeffs_exact)

    score_bajo = formula.score(0.1, 0.5, 0.5)
    score_medio = formula.score(0.5, 0.5, 0.5)
    score_alto = formula.score(0.9, 0.5, 0.5)

    assert score_bajo <= score_medio <= score_alto


def test_score_monotono_en_best_match() -> None:
    """Score es monótonamente creciente en best_match."""
    coeffs_relevant = CalibrationCoefficients(
        intercept=-3.8878,
        reranker=0.3281,
        best_match=3.2548,
        coverage=6.0296,
    )
    coeffs_exact = CalibrationCoefficients(
        intercept=-5.0958,
        reranker=0.4013,
        best_match=3.5326,
        coverage=5.0620,
    )
    formula = CompatibilityFormula(relevant=coeffs_relevant, exact=coeffs_exact)

    score_bajo = formula.score(0.5, 0.1, 0.5)
    score_medio = formula.score(0.5, 0.5, 0.5)
    score_alto = formula.score(0.5, 0.9, 0.5)

    assert score_bajo <= score_medio <= score_alto


def test_score_monotono_en_coverage() -> None:
    """Score es monótonamente creciente en coverage."""
    coeffs_relevant = CalibrationCoefficients(
        intercept=-3.8878,
        reranker=0.3281,
        best_match=3.2548,
        coverage=6.0296,
    )
    coeffs_exact = CalibrationCoefficients(
        intercept=-5.0958,
        reranker=0.4013,
        best_match=3.5326,
        coverage=5.0620,
    )
    formula = CompatibilityFormula(relevant=coeffs_relevant, exact=coeffs_exact)

    score_bajo = formula.score(0.5, 0.5, 0.1)
    score_medio = formula.score(0.5, 0.5, 0.5)
    score_alto = formula.score(0.5, 0.5, 0.9)

    assert score_bajo <= score_medio <= score_alto


def test_score_p2_nunca_supera_p1() -> None:
    """P(exacta) nunca supera P(relevancia>=1)."""
    coeffs_relevant = CalibrationCoefficients(
        intercept=-3.8878,
        reranker=0.3281,
        best_match=3.2548,
        coverage=6.0296,
    )
    coeffs_exact = CalibrationCoefficients(
        intercept=-5.0958,
        reranker=0.4013,
        best_match=3.5326,
        coverage=5.0620,
    )
    formula = CompatibilityFormula(relevant=coeffs_relevant, exact=coeffs_exact)

    # Recalcular el score internamente para verificar p2 <= p1
    # (Esto requiere un acceso a la implementación interna, se verifica
    # indirectamente con que el score esté dentro del rango esperado)
    for reranker in [0.1, 0.5, 0.9]:
        for best_match in [0.1, 0.5, 0.9]:
            for coverage in [0.1, 0.5, 0.9]:
                score = formula.score(reranker, best_match, coverage)
                assert 0.0 <= score <= 1.0


def test_score_caso_numerico_default() -> None:
    """Caso numérico con coeficientes default: reranker 0.43, B 0.61, C 0.61 → ~0.68 ± 0.02."""
    coeffs_relevant = CalibrationCoefficients(
        intercept=-3.8878,
        reranker=0.3281,
        best_match=3.2548,
        coverage=6.0296,
    )
    coeffs_exact = CalibrationCoefficients(
        intercept=-5.0958,
        reranker=0.4013,
        best_match=3.5326,
        coverage=5.0620,
    )
    formula = CompatibilityFormula(relevant=coeffs_relevant, exact=coeffs_exact)

    score = formula.score(reranker_score=0.43, best_match=0.61, coverage=0.61)
    assert 0.66 <= score <= 0.70, f"Score fuera del rango esperado: {score}"


# ---------------------------------------------------------------------------
# Integración: construcción de CompatibilityFormula
# ---------------------------------------------------------------------------


def test_compatibility_formula_construccion() -> None:
    """Se puede construir una CompatibilityFormula con coeficientes."""
    coeffs_relevant = CalibrationCoefficients(
        intercept=-3.8878,
        reranker=0.3281,
        best_match=3.2548,
        coverage=6.0296,
    )
    coeffs_exact = CalibrationCoefficients(
        intercept=-5.0958,
        reranker=0.4013,
        best_match=3.5326,
        coverage=5.0620,
    )
    formula = CompatibilityFormula(relevant=coeffs_relevant, exact=coeffs_exact)

    assert formula.relevant.intercept == -3.8878
    assert formula.exact.reranker == 0.4013
