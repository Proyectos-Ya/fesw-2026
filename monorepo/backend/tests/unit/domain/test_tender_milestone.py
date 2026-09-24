from datetime import datetime, time, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    MilestoneUrgency,
    TenderMilestone,
)

AHORA = datetime(2026, 10, 1, 12, 0)


def _hito(**cambios: object) -> TenderMilestone:
    datos: dict[str, object] = {
        "user_id": uuid4(),
        "tender_id": uuid4(),
        "kind": MilestoneKind.VISITA_TECNICA,
        "title": "Visita técnica obligatoria",
        "source": MilestoneSource.IA_DOCUMENTO,
        "due_at": AHORA + timedelta(days=10),
        "has_time": True,
    }
    datos.update(cambios)
    return TenderMilestone.model_validate(datos)


class TestUrgencia:
    @pytest.mark.parametrize(
        ("falta", "esperado"),
        [
            (timedelta(minutes=-1), MilestoneUrgency.VENCIDO),
            (timedelta(hours=2), MilestoneUrgency.CRITICO),
            (timedelta(days=3), MilestoneUrgency.CRITICO),
            (timedelta(days=3, minutes=1), MilestoneUrgency.PROXIMO),
            (timedelta(days=7), MilestoneUrgency.PROXIMO),
            (timedelta(days=7, minutes=1), MilestoneUrgency.NORMAL),
        ],
    )
    def test_usa_los_mismos_umbrales_que_el_frontend(
        self, falta: timedelta, esperado: MilestoneUrgency
    ):
        assert _hito(due_at=AHORA + falta).urgencia(AHORA) is esperado


class TestConHora:
    def test_aplica_la_hora_local_de_chile_sobre_el_mismo_dia(self):
        # Sin hora: medianoche de Chile del 20-oct (UTC-3) = 03:00 UTC.
        sin_hora = _hito(due_at=datetime(2026, 10, 20, 3, 0), has_time=False)

        con_hora = sin_hora.con_hora(time(9, 0))

        assert con_hora.due_at == datetime(2026, 10, 20, 12, 0)
        assert con_hora.has_time is True

    def test_no_modifica_el_hito_original(self):
        sin_hora = _hito(due_at=datetime(2026, 10, 20, 3, 0), has_time=False)

        sin_hora.con_hora(time(9, 0))

        assert sin_hora.has_time is False
        assert sin_hora.due_at == datetime(2026, 10, 20, 3, 0)


class TestValidacion:
    def test_titulo_vacio_es_invalido(self):
        with pytest.raises(ValidationError):
            _hito(title="   ")

    def test_recorta_el_parrafo_fuente_largo(self):
        hito = _hito(source_excerpt="x" * 5000)

        assert hito.source_excerpt is not None
        assert len(hito.source_excerpt) == 1000

    def test_serializa_la_fecha_en_utc_con_z(self):
        hito = _hito(due_at=datetime(2026, 10, 20, 18, 0))

        assert hito.model_dump(mode="json")["due_at"] == "2026-10-20T18:00:00Z"
