"""Prioridad de anexos en sombra: se calcula y se guarda, nadie la consume todavía."""

import pytest

from app.application.services.attachment_priority_shadow_service import (
    AttachmentPriorityShadowService,
)


@pytest.mark.parametrize(
    ("horas", "esperada"),
    [
        (1, 0.0),
        (2, 0.0),
        (13, 0.5),
        (24, 1.0),
        (48, 1.0),
        (72, 1.0),
        (120, 0.5),
        (168, 0.0),
        (200, 0.0),
    ],
)
def test_la_urgencia_es_un_trapecio(horas: float, esperada: float):
    assert AttachmentPriorityShadowService.closing_urgency(horas) == pytest.approx(
        esperada
    )


def test_prioridad_calculada_a_mano():
    # 3·ln(1+3) + 2·ln(1+1) + 2 (subida manual) + 1 (urgencia a 48 h)
    #   = 3·ln4 + 2·ln2 + 2 + 1 = 8.545177444479563
    valor, componentes = AttachmentPriorityShadowService().priority(
        top10_impressions=3,
        interactions=1,
        manual_upload=True,
        hours_to_close=48.0,
    )

    assert valor == pytest.approx(8.545177444479563, abs=1e-9)
    assert componentes == {
        "impresiones_top10_7d": 3,
        "interacciones_7d": 1,
        "subida_manual": True,
        "horas_al_cierre": 48.0,
        "urgencia_cierre": 1.0,
    }


def test_solo_con_urgencia_la_prioridad_es_la_urgencia():
    valor, _ = AttachmentPriorityShadowService().priority(
        top10_impressions=0,
        interactions=0,
        manual_upload=False,
        hours_to_close=120.0,
    )
    assert valor == pytest.approx(0.5)
