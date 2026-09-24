from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.calendar import CalendarEventDraft
from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    TenderMilestone,
)
from app.domain.errors.calendar_errors import MilestoneTimeRequired

RETORNO = "https://proyectosya.cl/matches/abc"


def _hito(has_time: bool = True, description: str | None = None) -> TenderMilestone:
    return TenderMilestone(
        user_id=uuid4(),
        tender_id=uuid4(),
        kind=MilestoneKind.CIERRE_POSTULACION,
        title="Cierre de recepción de ofertas",
        description=description,
        source=MilestoneSource.MERCADO_PUBLICO,
        due_at=datetime(2026, 10, 20, 18, 0),
        has_time=has_time,
    )


class TestDesdeHito:
    def test_el_titulo_incluye_el_hito_y_la_licitacion(self):
        borrador = CalendarEventDraft.from_milestone(
            _hito(), tender_title="Reparación de techumbre", return_url=RETORNO
        )

        assert borrador.title == "Cierre de recepción de ofertas — Reparación de techumbre"

    def test_empieza_en_la_fecha_exacta_del_hito_y_dura_una_hora(self):
        hito = _hito()

        borrador = CalendarEventDraft.from_milestone(
            hito, tender_title="Licitación", return_url=RETORNO
        )

        assert borrador.start == hito.due_at
        assert borrador.end == hito.due_at + timedelta(hours=1)

    def test_la_descripcion_lleva_el_enlace_de_retorno(self):
        borrador = CalendarEventDraft.from_milestone(
            _hito(description="Entregar en oficina de partes."),
            tender_title="Licitación",
            return_url=RETORNO,
        )

        assert "Entregar en oficina de partes." in borrador.description
        assert RETORNO in borrador.description

    def test_trae_recordatorios_un_dia_y_una_hora_antes(self):
        borrador = CalendarEventDraft.from_milestone(
            _hito(), tender_title="Licitación", return_url=RETORNO
        )

        assert borrador.reminders_minutes == (1440, 60)

    def test_conserva_el_id_del_hito(self):
        hito = _hito()

        borrador = CalendarEventDraft.from_milestone(
            hito, tender_title="Licitación", return_url=RETORNO
        )

        assert borrador.milestone_id == hito.id

    def test_un_hito_sin_hora_no_se_puede_convertir_en_evento(self):
        hito = _hito(has_time=False)

        with pytest.raises(MilestoneTimeRequired) as error:
            CalendarEventDraft.from_milestone(
                hito, tender_title="Licitación", return_url=RETORNO
            )

        assert error.value.milestone_ids == [hito.id]
