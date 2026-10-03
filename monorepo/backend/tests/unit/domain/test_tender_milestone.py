from datetime import datetime, time, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.entities.tender_milestone import (
    OFFICIAL_ONLY_KINDS,
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
            # El criterio 9 pide destacar desde "5 días o menos".
            (timedelta(days=5), MilestoneUrgency.PROXIMO),
            (timedelta(days=5, minutes=1), MilestoneUrgency.NORMAL),
        ],
    )
    def test_destaca_los_hitos_a_cinco_dias_o_menos(
        self, falta: timedelta, esperado: MilestoneUrgency
    ):
        assert _hito(due_at=AHORA + falta).urgencia(AHORA) is esperado


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


class TestCierreDelSegundoLlamado:
    """Tipo propio: `_cambios` indexa por tipo y dos oficiales iguales chocarían."""

    def test_el_valor_se_lee_desde_la_base(self):
        # El repositorio reconstruye el tipo con `MilestoneKind(model.kind)`.
        assert MilestoneKind("cierre_segundo_llamado") is MilestoneKind.CIERRE_SEGUNDO_LLAMADO

    def test_es_un_hito_solo_oficial(self):
        assert OFFICIAL_ONLY_KINDS == {MilestoneKind.CIERRE_SEGUNDO_LLAMADO}

    def test_un_hito_puede_ser_de_ese_tipo(self):
        hito = _hito(
            kind=MilestoneKind.CIERRE_SEGUNDO_LLAMADO,
            title="Cierre del segundo llamado",
            source=MilestoneSource.MERCADO_PUBLICO,
        )

        assert hito.kind is MilestoneKind.CIERRE_SEGUNDO_LLAMADO
