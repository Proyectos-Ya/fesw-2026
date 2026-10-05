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
            # Mismo día, más tarde: vence hoy.
            (timedelta(hours=2), MilestoneUrgency.CRITICO),
            (timedelta(days=3), MilestoneUrgency.CRITICO),
            # Criterio 9: desde "5 días o menos" se destaca, sin un tono intermedio.
            (timedelta(days=5), MilestoneUrgency.CRITICO),
            # 6-oct 23:30 en Chile: son 5 días de calendario aunque falten más de
            # 5x24 horas. Es lo que dice la tabla ("En 5 días"), así que se destaca.
            (timedelta(days=5, hours=14, minutes=30), MilestoneUrgency.CRITICO),
            # 7-oct 00:30 en Chile: ya son 6 días de calendario.
            (timedelta(days=5, hours=15, minutes=30), MilestoneUrgency.NORMAL),
        ],
    )
    def test_destaca_los_hitos_a_cinco_dias_de_calendario_o_menos(
        self, falta: timedelta, esperado: MilestoneUrgency
    ):
        # AHORA es el 1-oct a las 09:00 en Chile (12:00 UTC).
        assert _hito(due_at=AHORA + falta).urgencia(AHORA) is esperado

    def test_solo_hay_tres_estados_sin_tono_intermedio(self):
        # Gris (normal o vencido) y rojo (crítico): no hay amarillo.
        assert {u.value for u in MilestoneUrgency} == {"vencido", "critico", "normal"}


class TestRecordatorio:
    """Criterio 10: recordatorio activable con anticipación configurable."""

    def test_sin_anticipacion_configurada_no_hay_recordatorio(self):
        assert _hito(reminder_days_before=None).recordatorio_pendiente(AHORA) is False

    def test_todavia_falta_para_la_anticipacion_elegida(self):
        # Vence en 10 días y pidió aviso 3 días antes: aún no toca.
        hito = _hito(due_at=AHORA + timedelta(days=10), reminder_days_before=3)

        assert hito.recordatorio_pendiente(AHORA) is False

    def test_al_entrar_en_la_ventana_toca_avisar(self):
        hito = _hito(due_at=AHORA + timedelta(days=3), reminder_days_before=3)

        assert hito.recordatorio_pendiente(AHORA) is True

    def test_dentro_de_la_ventana_sigue_tocando(self):
        hito = _hito(due_at=AHORA + timedelta(days=1), reminder_days_before=3)

        assert hito.recordatorio_pendiente(AHORA) is True

    def test_un_hito_ya_vencido_no_se_recuerda(self):
        hito = _hito(due_at=AHORA - timedelta(minutes=1), reminder_days_before=3)

        assert hito.recordatorio_pendiente(AHORA) is False

    def test_no_se_repite_si_ya_se_envio(self):
        hito = _hito(
            due_at=AHORA + timedelta(days=1),
            reminder_days_before=3,
            reminder_sent_at=AHORA - timedelta(hours=2),
        )

        assert hito.recordatorio_pendiente(AHORA) is False

    def test_marcar_enviado_deja_constancia_y_apaga_el_pendiente(self):
        hito = _hito(due_at=AHORA + timedelta(days=1), reminder_days_before=3)

        enviado = hito.con_recordatorio_enviado(AHORA)

        assert enviado.reminder_sent_at == AHORA
        assert enviado.recordatorio_pendiente(AHORA) is False
        # No muta el original.
        assert hito.reminder_sent_at is None

    @pytest.mark.parametrize("dias", [0, -1, 400])
    def test_rechaza_anticipaciones_absurdas(self, dias: int):
        with pytest.raises(ValidationError):
            _hito(reminder_days_before=dias)


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
