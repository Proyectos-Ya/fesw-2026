"""Resumen diario de alertas (HdU 08, criterio del modo de entrega).

En modo `daily_digest` el escaneo crea los avisos in-app pero no encola correo:
lo agrupa este caso de uso, una vez al día, en una sola entrega.
"""

from uuid import UUID, uuid4

from app.application.use_cases.notifications.build_daily_digest import (
    BuildDailyDigestUseCase,
)
from app.domain.entities.notification import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
)
from tests.unit.application.fakes import (
    InMemoryNotificationDeliveryRepository,
    InMemoryNotificationPreferenceRepository,
    InMemoryNotificationRepository,
)


class Escenario:
    """Repositorios en memoria más atajos para preparar el estado del test."""

    def __init__(self, max_por_resumen: int = 20) -> None:
        self.preferences = InMemoryNotificationPreferenceRepository()
        self.notifications = InMemoryNotificationRepository()
        self.deliveries = InMemoryNotificationDeliveryRepository()
        self.use_case = BuildDailyDigestUseCase(
            preference_repo=self.preferences,
            notification_repo=self.notifications,
            delivery_repo=self.deliveries,
            max_por_resumen=max_por_resumen,
        )

    async def con_preferencia(self, **kwargs) -> UUID:
        """Crea un usuario en modo resumen diario y devuelve su id."""
        preferencia = NotificationPreference(
            user_id=uuid4(), delivery_mode="daily_digest", **kwargs
        )
        await self.preferences.save(preferencia)
        return preferencia.user_id

    async def con_avisos(self, user_id: UUID, cuantos: int) -> list[Notification]:
        avisos = [
            Notification(user_id=user_id, tender_id=uuid4(), score=0.9)
            for _ in range(cuantos)
        ]
        await self.notifications.save_bulk(avisos)
        return avisos

    def entregas_de(self, user_id: UUID) -> list[NotificationDelivery]:
        return [d for d in self.deliveries.deliveries.values() if d.user_id == user_id]


class TestAgrupacion:
    async def test_junta_todos_los_avisos_en_una_sola_entrega(self):
        # Es el punto del modo: un correo al día, no uno por licitación.
        escenario = Escenario()
        user_id = await escenario.con_preferencia()
        await escenario.con_avisos(user_id, 3)

        encoladas = await escenario.use_case.execute()

        assert encoladas == 1
        entregas = escenario.entregas_de(user_id)
        assert len(entregas) == 1
        assert len(entregas[0].notification_ids) == 3

    async def test_la_entrega_queda_marcada_como_resumen(self):
        # `kind` decide el asunto y el encabezado del correo.
        escenario = Escenario()
        user_id = await escenario.con_preferencia()
        await escenario.con_avisos(user_id, 2)

        await escenario.use_case.execute()

        assert escenario.entregas_de(user_id)[0].kind == "digest"

    async def test_la_entrega_nace_pendiente_de_envio(self):
        escenario = Escenario()
        user_id = await escenario.con_preferencia()
        await escenario.con_avisos(user_id, 1)

        await escenario.use_case.execute()

        assert escenario.entregas_de(user_id)[0].status == "pending"

    async def test_arma_un_resumen_por_usuario(self):
        escenario = Escenario()
        primero = await escenario.con_preferencia()
        segundo = await escenario.con_preferencia()
        await escenario.con_avisos(primero, 2)
        await escenario.con_avisos(segundo, 1)

        encoladas = await escenario.use_case.execute()

        assert encoladas == 2
        assert len(escenario.entregas_de(primero)) == 1
        assert len(escenario.entregas_de(segundo)) == 1

    async def test_corta_en_el_maximo_configurado(self):
        escenario = Escenario(max_por_resumen=2)
        user_id = await escenario.con_preferencia()
        await escenario.con_avisos(user_id, 5)

        await escenario.use_case.execute()

        assert len(escenario.entregas_de(user_id)[0].notification_ids) == 2


class TestAQuienAlcanza:
    async def test_ignora_a_quien_eligio_aviso_inmediato(self):
        # A ese usuario ya le encoló el correo el propio escaneo.
        escenario = Escenario()
        preferencia = NotificationPreference(user_id=uuid4(), delivery_mode="immediate")
        await escenario.preferences.save(preferencia)
        await escenario.con_avisos(preferencia.user_id, 3)

        assert await escenario.use_case.execute() == 0
        assert escenario.deliveries.deliveries == {}

    async def test_ignora_a_quien_apago_las_alertas(self):
        escenario = Escenario()
        user_id = await escenario.con_preferencia(enabled=False)
        await escenario.con_avisos(user_id, 2)

        assert await escenario.use_case.execute() == 0

    async def test_ignora_a_quien_tiene_el_correo_desactivado(self):
        # El usuario cuyo correo rebotó sigue viendo sus avisos en la
        # plataforma, pero no se le vuelve a escribir.
        escenario = Escenario()
        user_id = await escenario.con_preferencia(email_delivery_enabled=False)
        await escenario.con_avisos(user_id, 2)

        assert await escenario.use_case.execute() == 0

    async def test_sin_avisos_no_encola_nada(self):
        escenario = Escenario()
        await escenario.con_preferencia()

        assert await escenario.use_case.execute() == 0
        assert escenario.deliveries.deliveries == {}

    async def test_sin_usuarios_en_modo_resumen_no_hace_nada(self):
        escenario = Escenario()

        assert await escenario.use_case.execute() == 0


class TestNoRepetir:
    async def test_no_reenvia_un_aviso_que_ya_viajo_en_otro_correo(self):
        # Alternar entre inmediato y resumen no debe traer la misma licitación
        # dos veces a la bandeja.
        escenario = Escenario()
        user_id = await escenario.con_preferencia()
        avisos = await escenario.con_avisos(user_id, 2)
        await escenario.deliveries.save(
            NotificationDelivery(
                user_id=user_id, kind="immediate", notification_ids=[avisos[0].id]
            )
        )

        await escenario.use_case.execute()

        resumen = next(d for d in escenario.entregas_de(user_id) if d.kind == "digest")
        assert resumen.notification_ids == [avisos[1].id]

    async def test_no_encola_nada_si_todo_ya_viajo(self):
        escenario = Escenario()
        user_id = await escenario.con_preferencia()
        avisos = await escenario.con_avisos(user_id, 2)
        await escenario.deliveries.save(
            NotificationDelivery(
                user_id=user_id,
                kind="immediate",
                notification_ids=[a.id for a in avisos],
            )
        )

        assert await escenario.use_case.execute() == 0

    async def test_dos_ejecuciones_seguidas_no_duplican_el_resumen(self):
        # El loop diario podría dispararse dos veces tras un reinicio.
        escenario = Escenario()
        user_id = await escenario.con_preferencia()
        await escenario.con_avisos(user_id, 2)

        await escenario.use_case.execute()
        segunda = await escenario.use_case.execute()

        assert segunda == 0
        assert len(escenario.entregas_de(user_id)) == 1
