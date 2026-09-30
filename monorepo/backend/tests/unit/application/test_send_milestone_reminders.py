"""Criterio 10 de la HU-16: recordatorio activable con anticipación configurable,
notificado dentro de la plataforma y por correo."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.application.use_cases.milestones.send_milestone_reminders import (
    SendMilestoneRemindersUseCase,
)
from app.domain.entities.notification import NotificationPreference
from app.domain.entities.tender import Tender
from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    TenderMilestone,
)
from tests.unit.application.fakes import (
    InMemoryNotificationDeliveryRepository,
    InMemoryNotificationPreferenceRepository,
    InMemoryNotificationRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.milestone_fakes import InMemoryTenderMilestoneRepository

AHORA = datetime(2026, 10, 1, 12, 0)
USUARIO = uuid4()


class Escenario:
    def __init__(self) -> None:
        self.tender = Tender(
            code="COT-1",
            name="Reparación de techumbre",
            status_id=1,
            published_at=AHORA - timedelta(days=5),
            closing_at=AHORA + timedelta(days=20),
            last_change_at=AHORA,
            buyer_rut="1-9",
            buyer_unit="Operaciones",
        )
        self.tenders = InMemoryTenderRepository()
        self.tenders.tenders[self.tender.id] = self.tender
        self.hitos = InMemoryTenderMilestoneRepository()
        self.avisos = InMemoryNotificationRepository()
        self.entregas = InMemoryNotificationDeliveryRepository()
        self.preferencias = InMemoryNotificationPreferenceRepository()
        self.use_case = SendMilestoneRemindersUseCase(
            tenders=self.tenders,
            milestones=self.hitos,
            notifications=self.avisos,
            deliveries=self.entregas,
            preferences=self.preferencias,
            now=lambda: AHORA,
        )

    async def hito(
        self,
        dias_para_vencer: int = 2,
        anticipacion: int | None = 3,
        user_id: UUID = USUARIO,
        titulo: str = "Visita técnica",
    ) -> TenderMilestone:
        hito = TenderMilestone(
            user_id=user_id,
            tender_id=self.tender.id,
            kind=MilestoneKind.VISITA_TECNICA,
            title=titulo,
            source=MilestoneSource.IA_DOCUMENTO,
            due_at=AHORA + timedelta(days=dias_para_vencer),
            has_time=True,
            reminder_days_before=anticipacion,
        )
        await self.hitos.save_many([hito])
        return hito


class TestAvisa:
    async def test_avisa_en_la_app_con_el_hito_y_su_fecha(self):
        escenario = Escenario()
        hito = await escenario.hito()

        enviados = await escenario.use_case.execute()

        assert enviados == 1
        [aviso] = await escenario.avisos.list_by_user(USUARIO)
        assert aviso.kind == "milestone_reminder"
        assert aviso.tender_id == escenario.tender.id
        assert [(r.title, r.due_at) for r in aviso.milestone_reminders] == [
            (hito.title, hito.due_at)
        ]
        assert aviso.read_at is None

    async def test_encola_el_correo(self):
        escenario = Escenario()
        await escenario.hito()

        await escenario.use_case.execute()

        [entrega] = escenario.entregas.deliveries.values()
        assert entrega.user_id == USUARIO
        assert entrega.kind == "immediate"

    async def test_marca_el_hito_para_no_repetirlo(self):
        escenario = Escenario()
        await escenario.hito()

        await escenario.use_case.execute()
        segunda = await escenario.use_case.execute()

        assert segunda == 0
        assert len(escenario.entregas.deliveries) == 1

    async def test_sin_correo_activado_igual_avisa_en_la_app(self):
        escenario = Escenario()
        await escenario.preferencias.save(
            NotificationPreference(user_id=USUARIO, email_delivery_enabled=False)
        )
        await escenario.hito()

        await escenario.use_case.execute()

        assert len(await escenario.avisos.list_by_user(USUARIO)) == 1
        assert escenario.entregas.deliveries == {}

    async def test_agrupa_varios_hitos_de_la_misma_licitacion(self):
        escenario = Escenario()
        await escenario.hito(titulo="Visita técnica")
        await escenario.hito(titulo="Entrega de muestras", dias_para_vencer=1)

        enviados = await escenario.use_case.execute()

        assert enviados == 2
        [aviso] = await escenario.avisos.list_by_user(USUARIO)
        assert {r.title for r in aviso.milestone_reminders} == {
            "Visita técnica",
            "Entrega de muestras",
        }

    async def test_cada_usuario_recibe_lo_suyo(self):
        escenario = Escenario()
        otro = uuid4()
        await escenario.hito()
        await escenario.hito(user_id=otro, titulo="Entrega")

        await escenario.use_case.execute()

        assert len(await escenario.avisos.list_by_user(USUARIO)) == 1
        assert len(await escenario.avisos.list_by_user(otro)) == 1


class TestNoAvisa:
    async def test_sin_recordatorio_activado(self):
        escenario = Escenario()
        await escenario.hito(anticipacion=None)

        assert await escenario.use_case.execute() == 0
        assert escenario.avisos.notifications == {}

    async def test_todavia_falta_para_la_anticipacion(self):
        escenario = Escenario()
        await escenario.hito(dias_para_vencer=10, anticipacion=3)

        assert await escenario.use_case.execute() == 0

    async def test_un_hito_ya_vencido(self):
        escenario = Escenario()
        await escenario.hito(dias_para_vencer=-1, anticipacion=3)

        assert await escenario.use_case.execute() == 0

    async def test_si_la_licitacion_ya_no_existe_no_falla(self):
        escenario = Escenario()
        await escenario.hito()
        escenario.tenders.tenders.clear()

        assert await escenario.use_case.execute() == 0
