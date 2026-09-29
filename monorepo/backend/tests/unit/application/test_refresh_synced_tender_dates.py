"""Criterio 4 de la HU-16: un cambio de fecha en Mercado Público actualiza el
evento del calendario y avisa "Fecha modificada" en la app y por correo."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.application.services.tender_refresher import (
    ITenderRefresher,
    OfficialTenderDates,
)
from app.application.use_cases.calendar.refresh_synced_tender_dates import (
    RefreshSyncedTenderDatesUseCase,
)
from app.application.use_cases.calendar.sync_milestones import (
    SyncMilestonesToCalendarUseCase,
)
from app.application.use_cases.milestones.milestone_views import (
    mercado_publico_milestones,
)
from app.domain.entities.calendar import (
    CalendarConnection,
    CalendarEventDraft,
    CalendarEventLink,
    CalendarProvider,
)
from app.domain.entities.notification import NotificationPreference
from app.domain.entities.tender import Tender
from app.domain.entities.tender_milestone import MilestoneKind
from tests.unit.application.fakes import (
    InMemoryNotificationDeliveryRepository,
    InMemoryNotificationPreferenceRepository,
    InMemoryNotificationRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.milestone_fakes import (
    FakeCalendarProviderClient,
    InMemoryCalendarConnectionRepository,
    InMemoryCalendarEventLinkRepository,
    InMemoryTenderMilestoneRepository,
)

AHORA = datetime(2026, 10, 1, 12, 0)
GOOGLE = CalendarProvider.GOOGLE
CIERRE = datetime(2026, 10, 20, 18, 0)
NUEVO_CIERRE = datetime(2026, 10, 27, 18, 0)


class FakeRefresher(ITenderRefresher):
    def __init__(self) -> None:
        self.fechas: dict[str, OfficialTenderDates] = {}
        self.fallan: set[str] = set()
        self.pedidos: list[str] = []

    async def refresh(self, code: str) -> OfficialTenderDates | None:
        self.pedidos.append(code)
        if code in self.fallan:
            raise RuntimeError("Mercado Público no respondió")
        return self.fechas.get(code)


class Escenario:
    def __init__(self) -> None:
        self.tenders = InMemoryTenderRepository()
        self.hitos = InMemoryTenderMilestoneRepository()
        self.enlaces = InMemoryCalendarEventLinkRepository(self.hitos)
        self.conexiones = InMemoryCalendarConnectionRepository()
        self.google = FakeCalendarProviderClient()
        self.avisos = InMemoryNotificationRepository()
        self.entregas = InMemoryNotificationDeliveryRepository()
        self.preferencias = InMemoryNotificationPreferenceRepository()
        self.refresher = FakeRefresher()
        sync = SyncMilestonesToCalendarUseCase(
            tenders=self.tenders,
            milestones=self.hitos,
            connections=self.conexiones,
            event_links=self.enlaces,
            providers={GOOGLE: self.google},
            app_base_url="https://proyectosya.cl",
            now=lambda: AHORA,
        )
        self.use_case = RefreshSyncedTenderDatesUseCase(
            tenders=self.tenders,
            refresher=self.refresher,
            milestones=self.hitos,
            event_links=self.enlaces,
            sync=sync,
            notifications=self.avisos,
            deliveries=self.entregas,
            preferences=self.preferencias,
            now=lambda: AHORA,
        )

    def licitacion(self, closing_at: datetime = CIERRE) -> Tender:
        tender = Tender(
            code=f"COT-{uuid4().hex[:6]}",
            name="Reparación de techumbre",
            status_id=1,
            published_at=AHORA - timedelta(days=3),
            closing_at=closing_at,
            last_change_at=AHORA,
            buyer_rut="1-9",
            buyer_unit="Operaciones",
        )
        self.tenders.tenders[tender.id] = tender
        self.refresher.fechas[tender.code] = OfficialTenderDates(
            published_at=tender.published_at, closing_at=tender.closing_at
        )
        return tender

    async def usuario_sincronizado(self, tender: Tender) -> tuple[UUID, str]:
        """Usuario con los hitos oficiales y el cierre ya en su Google Calendar."""
        user_id = uuid4()
        hitos = mercado_publico_milestones(tender, user_id)
        await self.hitos.save_many(hitos)
        cierre = next(h for h in hitos if h.kind is MilestoneKind.CIERRE_POSTULACION)
        evento_id = await self.google.create_event(
            "ya29.acceso",
            CalendarEventDraft.from_milestone(cierre, tender_title=tender.name, return_url="https://x"),
        )
        await self.enlaces.save(
            CalendarEventLink(
                user_id=user_id,
                milestone_id=cierre.id,
                provider=GOOGLE,
                external_event_id=evento_id,
                synced_due_at=cierre.due_at,
            )
        )
        await self.conexiones.save(
            CalendarConnection(
                user_id=user_id,
                provider=GOOGLE,
                access_token="ya29.acceso",
                refresh_token="1//refresco",
                expires_at=AHORA + timedelta(hours=1),
            )
        )
        return user_id, evento_id

    def mover_cierre(self, tender: Tender, nuevo: datetime = NUEVO_CIERRE) -> None:
        self.refresher.fechas[tender.code] = OfficialTenderDates(
            published_at=tender.published_at, closing_at=nuevo
        )


class TestCambioDeFecha:
    async def test_actualiza_el_evento_del_calendario(self):
        escenario = Escenario()
        tender = escenario.licitacion()
        _, evento_id = await escenario.usuario_sincronizado(tender)
        escenario.mover_cierre(tender)

        cambiadas = await escenario.use_case.execute()

        assert cambiadas == 1
        assert escenario.google.actualizados == [evento_id]
        assert escenario.google.eventos[evento_id].start == NUEVO_CIERRE

    async def test_actualiza_el_hito_oficial(self):
        escenario = Escenario()
        tender = escenario.licitacion()
        user_id, _ = await escenario.usuario_sincronizado(tender)
        escenario.mover_cierre(tender)

        await escenario.use_case.execute()

        hitos = await escenario.hitos.list_for_tender(user_id, tender.id)
        cierre = next(h for h in hitos if h.kind is MilestoneKind.CIERRE_POSTULACION)
        assert cierre.due_at == NUEVO_CIERRE

    async def test_avisa_fecha_modificada_en_la_app_con_el_antes_y_el_despues(self):
        escenario = Escenario()
        tender = escenario.licitacion()
        user_id, _ = await escenario.usuario_sincronizado(tender)
        escenario.mover_cierre(tender)

        await escenario.use_case.execute()

        [aviso] = await escenario.avisos.list_by_user(user_id)
        assert aviso.kind == "date_changed"
        assert aviso.tender_id == tender.id
        assert [(c.label, c.previous_at, c.new_at) for c in aviso.date_changes] == [
            ("Cierre de recepción de ofertas", CIERRE, NUEVO_CIERRE)
        ]
        assert aviso.read_at is None

    async def test_encola_el_correo_de_inmediato(self):
        escenario = Escenario()
        tender = escenario.licitacion()
        user_id, _ = await escenario.usuario_sincronizado(tender)
        escenario.mover_cierre(tender)

        await escenario.use_case.execute()

        [entrega] = escenario.entregas.deliveries.values()
        assert entrega.user_id == user_id
        assert entrega.kind == "immediate"
        [aviso] = await escenario.avisos.list_by_user(user_id)
        assert entrega.notification_ids == [aviso.id]

    async def test_aun_en_modo_resumen_diario_el_cambio_sale_al_momento(self):
        escenario = Escenario()
        tender = escenario.licitacion()
        user_id, _ = await escenario.usuario_sincronizado(tender)
        await escenario.preferencias.save(NotificationPreference(user_id=user_id, delivery_mode="daily_digest"))
        escenario.mover_cierre(tender)

        await escenario.use_case.execute()

        assert len(escenario.entregas.deliveries) == 1

    async def test_sin_correo_activado_solo_avisa_en_la_app(self):
        escenario = Escenario()
        tender = escenario.licitacion()
        user_id, _ = await escenario.usuario_sincronizado(tender)
        await escenario.preferencias.save(NotificationPreference(user_id=user_id, email_delivery_enabled=False))
        escenario.mover_cierre(tender)

        await escenario.use_case.execute()

        assert len(await escenario.avisos.list_by_user(user_id)) == 1
        assert escenario.entregas.deliveries == {}

    async def test_un_segundo_cambio_reemplaza_el_aviso_en_vez_de_acumular(self):
        escenario = Escenario()
        tender = escenario.licitacion()
        user_id, _ = await escenario.usuario_sincronizado(tender)
        escenario.mover_cierre(tender)
        await escenario.use_case.execute()
        escenario.tenders.tenders[tender.id] = tender.model_copy(update={"closing_at": NUEVO_CIERRE})

        escenario.mover_cierre(tender, NUEVO_CIERRE + timedelta(days=2))
        await escenario.use_case.execute()

        [aviso] = await escenario.avisos.list_by_user(user_id)
        assert aviso.date_changes[0].new_at == NUEVO_CIERRE + timedelta(days=2)

    async def test_si_google_falla_igual_avisa(self):
        escenario = Escenario()
        tender = escenario.licitacion()
        user_id, _ = await escenario.usuario_sincronizado(tender)
        escenario.google.refresh_revocado = True
        escenario.google.rechazar_token = "ya29.acceso"
        escenario.mover_cierre(tender)

        await escenario.use_case.execute()

        assert len(await escenario.avisos.list_by_user(user_id)) == 1


class TestSinCambios:
    async def test_sin_licitaciones_sincronizadas_no_consulta_mercado_publico(self):
        escenario = Escenario()
        escenario.licitacion()

        assert await escenario.use_case.execute() == 0
        assert escenario.refresher.pedidos == []

    async def test_si_las_fechas_no_cambiaron_no_hace_nada(self):
        escenario = Escenario()
        tender = escenario.licitacion()
        await escenario.usuario_sincronizado(tender)

        assert await escenario.use_case.execute() == 0
        assert escenario.google.actualizados == []
        assert escenario.avisos.notifications == {}

    async def test_una_licitacion_ya_cerrada_no_se_consulta(self):
        escenario = Escenario()
        tender = escenario.licitacion(closing_at=AHORA - timedelta(days=1))
        await escenario.usuario_sincronizado(tender)

        await escenario.use_case.execute()

        assert escenario.refresher.pedidos == []

    async def test_si_mercado_publico_falla_sigue_con_las_demas(self):
        escenario = Escenario()
        caida = escenario.licitacion()
        movida = escenario.licitacion()
        await escenario.usuario_sincronizado(caida)
        user_id, _ = await escenario.usuario_sincronizado(movida)
        escenario.refresher.fallan.add(caida.code)
        escenario.mover_cierre(movida)

        assert await escenario.use_case.execute() == 1
        assert len(await escenario.avisos.list_by_user(user_id)) == 1

    async def test_solo_avisa_a_quien_tiene_hitos_sincronizados(self):
        escenario = Escenario()
        tender = escenario.licitacion()
        await escenario.usuario_sincronizado(tender)
        sin_calendario = uuid4()
        await escenario.hitos.save_many(mercado_publico_milestones(tender, sin_calendario))
        escenario.mover_cierre(tender)

        await escenario.use_case.execute()

        assert await escenario.avisos.list_by_user(sin_calendario) == []
