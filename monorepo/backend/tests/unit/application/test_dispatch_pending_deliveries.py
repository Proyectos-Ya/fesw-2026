"""Entrega de los correos de alerta y sus dos modos de fallo (HdU 08)."""

from datetime import datetime
from uuid import UUID, uuid4

from app.application.use_cases.notifications.dispatch_pending_deliveries import (
    DispatchPendingDeliveriesUseCase,
)
from app.domain.entities.notification import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
)
from app.domain.entities.tender import Tender
from app.domain.entities.user import User
from tests.unit.application.fakes import (
    FakeEmailService,
    InMemoryNotificationDeliveryRepository,
    InMemoryNotificationPreferenceRepository,
    InMemoryNotificationRepository,
    InMemoryTenderRepository,
    InMemoryUserRepository,
)

AHORA = datetime(2026, 8, 26, 12, 0, 0)
BASE_URL = "https://proyectosya.test"


def build_tender(tender_id: UUID) -> Tender:
    return Tender(
        id=tender_id,
        code="1057539-228-COT26",
        name="Servicio de mantención de áreas verdes",
        status_id=1,
        status_code="publicada",
        published_at=AHORA,
        closing_at=AHORA,
        last_change_at=AHORA,
        buyer_rut="61.980.170-9",
        buyer_name="Municipalidad de Providencia",
        buyer_unit="Dirección de Operaciones",
    )


class Escenario:
    """Un usuario con un aviso pendiente de enviar por correo."""

    def __init__(self, email: str = "contacto@empresa.cl") -> None:
        self.user = User(
            email=email, hashed_password="x", full_name="Empresa de Prueba"
        )
        self.tender_id = uuid4()

        self.user_repo = InMemoryUserRepository()
        self.user_repo.users[self.user.id] = self.user

        self.tender_repo = InMemoryTenderRepository()
        self.tender_repo.tenders[self.tender_id] = build_tender(self.tender_id)

        self.notification_repo = InMemoryNotificationRepository()
        self.notificacion = Notification(
            user_id=self.user.id, tender_id=self.tender_id, score=0.82
        )
        self.notification_repo.notifications[self.notificacion.id] = self.notificacion

        self.preference_repo = InMemoryNotificationPreferenceRepository()
        self.delivery_repo = InMemoryNotificationDeliveryRepository()
        self.entrega = NotificationDelivery(
            user_id=self.user.id,
            notification_ids=[self.notificacion.id],
            next_attempt_at=AHORA,
        )
        self.delivery_repo.deliveries[self.entrega.id] = self.entrega

        self.email_service = FakeEmailService()

    def use_case(self) -> DispatchPendingDeliveriesUseCase:
        return DispatchPendingDeliveriesUseCase(
            delivery_repo=self.delivery_repo,
            notification_repo=self.notification_repo,
            preference_repo=self.preference_repo,
            user_repo=self.user_repo,
            tender_repo=self.tender_repo,
            email_service=self.email_service,
            base_url=BASE_URL,
        )

    async def preferencia(self) -> NotificationPreference:
        guardada = await self.preference_repo.get_by_user_id(self.user.id)
        return guardada or NotificationPreference(user_id=self.user.id)


class TestEnvioExitoso:
    async def test_envia_el_correo_y_marca_la_entrega(self):
        escenario = Escenario()

        enviados = await escenario.use_case().execute(now=AHORA)

        assert enviados == 1
        assert escenario.entrega.status == "sent"
        assert escenario.entrega.sent_at == AHORA
        assert len(escenario.email_service.sent) == 1

    async def test_el_correo_va_al_usuario_con_el_enlace_a_la_licitacion(self):
        escenario = Escenario()

        await escenario.use_case().execute(now=AHORA)

        mensaje = escenario.email_service.sent[0]
        assert mensaje.to == "contacto@empresa.cl"
        # El criterio pide que el enlace lleve a la ficha de la licitación.
        enlace = f"{BASE_URL}/matches/{escenario.tender_id}"
        assert enlace in mensaje.text_body
        assert enlace in mensaje.html_body
        # 0.82 se muestra como 82%, no como 0.82.
        assert "82%" in mensaje.text_body

    async def test_una_entrega_ya_enviada_no_se_reenvia(self):
        escenario = Escenario()
        await escenario.use_case().execute(now=AHORA)

        enviados = await escenario.use_case().execute(now=AHORA)

        assert enviados == 0
        assert len(escenario.email_service.sent) == 1


class TestServicioCaido:
    async def test_la_entrega_queda_pendiente_y_se_reintenta(self):
        # Criterio: "el sistema guarda el evento como Pendiente y reintenta la
        # entrega al recuperar la conexión con el servicio externo".
        escenario = Escenario()
        escenario.email_service.simular_caida()

        enviados = await escenario.use_case().execute(now=AHORA)

        assert enviados == 0
        assert escenario.entrega.status == "pending"
        assert escenario.entrega.attempts == 1
        assert escenario.entrega.next_attempt_at > AHORA

    async def test_al_volver_el_servicio_el_correo_sale_solo(self):
        escenario = Escenario()
        escenario.email_service.simular_caida()
        await escenario.use_case().execute(now=AHORA)

        escenario.email_service.restablecer()
        # El reintento no se ejecuta antes de tiempo: hay que llegar a la fecha
        # que fijó el backoff.
        enviados = await escenario.use_case().execute(
            now=escenario.entrega.next_attempt_at
        )

        assert enviados == 1
        assert escenario.entrega.status == "sent"

    async def test_no_reintenta_antes_de_que_venza_el_backoff(self):
        escenario = Escenario()
        escenario.email_service.simular_caida()
        await escenario.use_case().execute(now=AHORA)
        escenario.email_service.restablecer()

        enviados = await escenario.use_case().execute(now=AHORA)

        assert enviados == 0
        assert escenario.entrega.status == "pending"

    async def test_un_fallo_transitorio_no_desactiva_el_correo_del_usuario(self):
        # Que el servidor esté caído no es culpa de la dirección del usuario.
        escenario = Escenario()
        escenario.email_service.simular_caida()

        await escenario.use_case().execute(now=AHORA)

        assert (await escenario.preferencia()).email_delivery_enabled is True


class TestDestinatarioInexistente:
    async def test_registra_el_fallo_y_desactiva_el_envio(self):
        # Criterio: "el sistema registra el fallo internamente y desactiva el
        # envío de alertas para ese usuario".
        escenario = Escenario()
        escenario.email_service.simular_destinatario_invalido("la dirección no existe")

        enviados = await escenario.use_case().execute(now=AHORA)

        assert enviados == 0
        assert escenario.entrega.status == "failed_permanent"
        preferencia = await escenario.preferencia()
        assert preferencia.email_delivery_enabled is False
        assert preferencia.last_failure_reason == "la dirección no existe"
        assert preferencia.last_failure_at == AHORA

    async def test_no_vuelve_a_intentar_una_direccion_rechazada(self):
        escenario = Escenario()
        escenario.email_service.simular_destinatario_invalido()
        await escenario.use_case().execute(now=AHORA)

        escenario.email_service.restablecer()
        enviados = await escenario.use_case().execute(now=AHORA)

        assert enviados == 0
        assert escenario.email_service.sent == []


class TestCasosBorde:
    async def test_no_envia_si_el_usuario_apago_las_alertas_despues_de_encolar(self):
        escenario = Escenario()
        await escenario.preference_repo.save(
            NotificationPreference(user_id=escenario.user.id, enabled=False)
        )

        enviados = await escenario.use_case().execute(now=AHORA)

        assert enviados == 0
        assert escenario.entrega.status == "failed_permanent"
        assert escenario.email_service.sent == []

    async def test_cierra_la_entrega_si_la_licitacion_ya_no_esta_en_la_base(self):
        escenario = Escenario()
        escenario.tender_repo.tenders.clear()

        enviados = await escenario.use_case().execute(now=AHORA)

        assert enviados == 0
        # Reintentar no traería de vuelta la licitación.
        assert escenario.entrega.status == "failed_permanent"
