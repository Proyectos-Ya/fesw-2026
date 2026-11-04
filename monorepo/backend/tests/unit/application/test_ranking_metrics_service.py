"""NDCG@10 de los rankings servidos en producción, calculado a mano.

Los números esperados están desarrollados en los comentarios: la prueba comprueba
la fórmula, no que el código se parezca a sí mismo.
"""

import math
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.application.services.ranking_metrics_service import RankingMetricsService
from app.domain.entities.ranking_telemetry import (
    InteractionKind,
    RankingImpression,
    TenderInteraction,
)

AHORA = datetime(2026, 10, 3, 12, 0)


def _imp(ranking: UUID, tender: UUID, position: int) -> RankingImpression:
    return RankingImpression(
        ranking_id=ranking,
        supplier_id=uuid4(),
        user_id=uuid4(),
        tender_id=tender,
        position=position,
        model_version="m1",
        created_at=AHORA,
    )


def _int(
    ranking: UUID | None, tender: UUID, kind: InteractionKind
) -> TenderInteraction:
    return TenderInteraction(
        user_id=uuid4(),
        tender_id=tender,
        kind=kind,
        ranking_id=ranking,
        position=1 if ranking else None,
        source="matches",
        created_at=AHORA,
    )


class TestDcgYNdcg:
    def test_dcg_divide_cada_ganancia_por_log2_de_su_posicion_mas_uno(self):
        # 3/log2(2) + 2/log2(3) + 1/log2(4) = 3 + 2/log2(3) + 1/2
        assert RankingMetricsService().dcg([3, 2, 1]) == pytest.approx(
            3 + 2 / math.log2(3) + 1 / 2
        )
        assert RankingMetricsService().dcg([3, 2, 1]) == pytest.approx(
            4.7618595071429155
        )

    def test_ndcg_calculado_a_mano(self):
        # Servido [0, 3, 0, 1, 2]
        #   DCG  = 3/log2(3) + 1/log2(5) + 2/log2(6) = 3.0971714332568485
        #   IDCG = orden ideal [3, 2, 1, 0, 0] = 3 + 2/log2(3) + 1/2
        #        = 4.7618595071429155
        #   NDCG = 3.0971714332568485 / 4.7618595071429155 = 0.6504121821761035
        assert RankingMetricsService().ndcg([0, 3, 0, 1, 2]) == pytest.approx(
            0.6504121821761035, abs=1e-12
        )

    def test_ndcg_de_una_sola_ganancia_en_la_segunda_posicion(self):
        # DCG = 1/log2(3); IDCG = 1/log2(2) = 1  ->  1/log2(3) = 0.6309297535714575
        assert RankingMetricsService().ndcg([0, 1]) == pytest.approx(
            0.6309297535714575, abs=1e-12
        )

    def test_la_unica_ganancia_fuera_del_top_10_vale_cero_pero_entra(self):
        # El ideal sí la ve (IDCG = 3), el DCG@10 no: el ranking se evalúa y vale 0.
        assert RankingMetricsService().ndcg([0] * 10 + [3, 0]) == 0.0

    def test_sin_ninguna_ganancia_no_hay_ndcg(self):
        assert RankingMetricsService().ndcg([0, 0, 0]) is None


class TestRelevanciaPorRanking:
    def test_ordena_por_posicion_servida_y_toma_la_mayor_ganancia_atribuida(self):
        r = uuid4()
        t1, t2, t3 = uuid4(), uuid4(), uuid4()
        # Impresiones desordenadas a propósito: la base no garantiza el orden.
        impresiones = [_imp(r, t3, 3), _imp(r, t1, 1), _imp(r, t2, 2)]
        interacciones = [
            _int(r, t2, InteractionKind.DETALLE),  # 1
            _int(r, t2, InteractionKind.ANALISIS),  # 3  <- gana
            _int(r, t1, InteractionKind.IMPRESION),  # 0
            _int(uuid4(), t3, InteractionKind.COTIZACION),  # otro ranking: no cuenta
            _int(None, t3, InteractionKind.GUARDAR),  # sin atribuir: no cuenta
        ]

        resultado = RankingMetricsService.relevance_by_ranking(
            impresiones, interacciones
        )

        assert resultado == {r: [0, 3, 0]}


class TestEvaluate:
    def test_un_ranking_sin_interacciones_queda_fuera_del_promedio(self):
        a, b = uuid4(), uuid4()
        ta = [uuid4() for _ in range(5)]
        tb = [uuid4() for _ in range(3)]
        impresiones = [_imp(a, t, i) for i, t in enumerate(ta, start=1)] + [
            _imp(b, t, i) for i, t in enumerate(tb, start=1)
        ]
        interacciones = [
            _int(a, ta[1], InteractionKind.ANALISIS),  # posición 2 -> 3
            _int(a, ta[3], InteractionKind.DETALLE),  # posición 4 -> 1
            _int(a, ta[4], InteractionKind.GUARDAR),  # posición 5 -> 2
        ]

        ev = RankingMetricsService().evaluate(impresiones, interacciones)

        assert ev is not None
        assert ev.rankings_served == 2
        assert ev.rankings_evaluated == 1
        # Relevancias de A: [0, 3, 0, 1, 2] -> 0.6504. Si B contara como 0,
        # el promedio daría 0.3252.
        assert ev.ndcg_at_10 == pytest.approx(0.6504121821761035)
        assert ev.ci_low == pytest.approx(0.6504121821761035)
        assert ev.ci_high == pytest.approx(0.6504121821761035)

    def test_sin_ningun_ranking_con_ganancia_devuelve_none(self):
        r = uuid4()
        t = uuid4()
        impresiones = [_imp(r, t, 1)]
        interacciones = [_int(r, t, InteractionKind.IMPRESION)]
        assert RankingMetricsService().evaluate(impresiones, interacciones) is None

    def test_sin_impresiones_devuelve_none(self):
        assert RankingMetricsService().evaluate([], []) is None


class TestBootstrapCi:
    def test_valores_iguales_dan_un_intervalo_de_un_punto(self):
        assert RankingMetricsService().bootstrap_ci([0.5] * 5) == (0.5, 0.5)

    def test_un_solo_valor_es_su_propio_intervalo(self):
        assert RankingMetricsService().bootstrap_ci([0.7]) == (0.7, 0.7)

    def test_es_determinista_y_envuelve_a_la_media(self):
        valores = [0.0, 1.0] * 10
        servicio = RankingMetricsService()

        primero = servicio.bootstrap_ci(valores)
        segundo = servicio.bootstrap_ci(valores)

        assert primero == segundo
        bajo, alto = primero
        assert 0.0 <= bajo < 0.5 < alto <= 1.0
