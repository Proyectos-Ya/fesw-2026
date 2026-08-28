from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.notification import (
    MAX_RETRY_BACKOFF_MINUTES,
    Notification,
    NotificationDelivery,
    NotificationPreference,
)

AHORA = datetime(2026, 8, 26, 12, 0, 0)


class TestNotificationPreference:
    def test_por_defecto_avisa_desde_el_umbral_verde(self):
        preferencia = NotificationPreference(user_id=uuid4())

        assert preferencia.threshold == 0.70
        assert preferencia.enabled is True
        assert preferencia.delivery_mode == "immediate"
        assert preferencia.wants_email() is True

    @pytest.mark.parametrize("valor", [0, -0.1, 1.5])
    def test_rechaza_umbrales_fuera_del_rango(self, valor: float):
        # Un 0 avisaría de todo y un valor mayor que 1 no avisaría nunca:
        # ambos dejan la funcionalidad inservible en silencio.
        with pytest.raises(ValueError):
            NotificationPreference(user_id=uuid4(), threshold=valor)

    def test_acepta_el_umbral_maximo(self):
        assert NotificationPreference(user_id=uuid4(), threshold=1.0).threshold == 1.0

    def test_no_quiere_correo_si_el_envio_esta_desactivado(self):
        # Es el estado en que queda un usuario cuyo correo rebotó.
        preferencia = NotificationPreference(
            user_id=uuid4(), email_delivery_enabled=False
        )

        assert preferencia.wants_email() is False

    def test_no_quiere_correo_si_apago_las_alertas(self):
        preferencia = NotificationPreference(user_id=uuid4(), enabled=False)

        assert preferencia.wants_email() is False


class TestNotification:
    def test_marcar_leido_registra_la_fecha(self):
        aviso = Notification(user_id=uuid4(), tender_id=uuid4(), score=0.8)
        assert aviso.is_read is False

        aviso.mark_read()

        assert aviso.is_read is True
        assert aviso.read_at is not None

    def test_marcar_leido_dos_veces_conserva_la_primera_fecha(self):
        aviso = Notification(user_id=uuid4(), tender_id=uuid4(), score=0.8)
        aviso.mark_read()
        primera = aviso.read_at

        aviso.mark_read()

        assert aviso.read_at == primera


class TestNotificationDelivery:
    def _entrega(self) -> NotificationDelivery:
        return NotificationDelivery(user_id=uuid4(), next_attempt_at=AHORA)

    def test_una_entrega_nueva_esta_vencida(self):
        assert self._entrega().is_due(AHORA) is True

    def test_una_entrega_enviada_ya_no_esta_vencida(self):
        entrega = self._entrega()
        entrega.mark_sent(AHORA)

        assert entrega.status == "sent"
        assert entrega.sent_at == AHORA
        assert entrega.is_due(AHORA) is False

    def test_fallo_transitorio_la_deja_pendiente_y_aleja_el_reintento(self):
        # Es el criterio del servicio de mensajería caído: el evento queda
        # "Pendiente" en vez de perderse.
        entrega = self._entrega()

        entrega.register_transient_failure("conexión rechazada", AHORA)

        assert entrega.status == "pending"
        assert entrega.attempts == 1
        assert entrega.last_error == "conexión rechazada"
        assert entrega.next_attempt_at == AHORA + timedelta(minutes=2)
        assert entrega.is_due(AHORA) is False

    def test_el_backoff_crece_con_cada_intento(self):
        entrega = self._entrega()

        entrega.register_transient_failure("falla", AHORA)
        primera_espera = entrega.next_attempt_at - AHORA
        entrega.register_transient_failure("falla", AHORA)
        segunda_espera = entrega.next_attempt_at - AHORA

        assert segunda_espera > primera_espera

    def test_el_backoff_tiene_tope(self):
        # Sin tope, unos pocos fallos empujarían el reintento a días de
        # distancia y el correo no saldría nunca.
        entrega = self._entrega()

        for _ in range(20):
            entrega.register_transient_failure("falla", AHORA)

        assert entrega.next_attempt_at == AHORA + timedelta(
            minutes=MAX_RETRY_BACKOFF_MINUTES
        )

    def test_fallo_permanente_cierra_la_entrega(self):
        entrega = self._entrega()

        entrega.mark_failed_permanent("la dirección no existe", AHORA)

        assert entrega.status == "failed_permanent"
        assert entrega.last_error == "la dirección no existe"
        assert entrega.is_due(AHORA) is False
