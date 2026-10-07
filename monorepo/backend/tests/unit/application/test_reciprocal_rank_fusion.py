"""Pruebas unitarias para Reciprocal Rank Fusion (Plan 256, Fase 1)."""

from uuid import uuid4
import pytest

from app.application.services.reciprocal_rank_fusion import (
    FusedRankItem,
    reciprocal_rank_fusion,
)


def test_rrf_combina_dos_rankings_correctamente():
    id_a = uuid4()
    id_b = uuid4()
    id_c = uuid4()

    # Ranking 1: A en pos 0, B en pos 1
    # Ranking 2: B en pos 0, A en pos 1
    # Ambos tienen idéntica suma de 1/(60+1) + 1/(60+2)
    ranking1 = [id_a, id_b]
    ranking2 = [id_b, id_a]

    fused = reciprocal_rank_fusion([ranking1, ranking2], k=60)
    assert len(fused) == 2
    assert {fused[0].item_id, fused[1].item_id} == {id_a, id_b}
    assert fused[0].score == pytest.approx(fused[1].score, abs=1e-6)


def test_rrf_prioriza_item_presente_en_multiples_canales():
    id_a = uuid4()
    id_b = uuid4()
    id_c = uuid4()

    # id_a está en la posición 2 en ambos canales
    # id_b solo está en la posición 1 en un solo canal
    canal1 = [id_b, id_a]
    canal2 = [id_c, id_a]

    fused = reciprocal_rank_fusion([canal1, canal2], k=60)
    # id_a tiene 1/(60+2) + 1/(60+2) = 2/62 ≈ 0.032258
    # id_b tiene 1/(60+1) = 1/61 ≈ 0.016393
    # id_a debe quedar en el primer lugar
    assert fused[0].item_id == id_a
    assert fused[0].score > fused[1].score


def test_rrf_con_canales_vacios():
    id_a = uuid4()
    fused = reciprocal_rank_fusion([[], [id_a], []], k=60)
    assert len(fused) == 1
    assert fused[0].item_id == id_a
    assert fused[0].score == pytest.approx(1.0 / 61.0, abs=1e-6)


def test_rrf_totalmente_vacio_retorna_lista_vacia():
    fused = reciprocal_rank_fusion([], k=60)
    assert fused == []

    fused_vacios = reciprocal_rank_fusion([[], []], k=60)
    assert fused_vacios == []
