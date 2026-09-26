from datetime import datetime, time, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.services.calendar_provider_client import OAuthTokens
from app.application.use_cases.calendar.sync_milestones import (
    SyncMilestonesToCalendarUseCase,
)
from app.domain.entities.calendar import (
    CalendarConnection,
    CalendarConnectionStatus,
    CalendarEventLink,
    CalendarProvider,
)
from app.domain.entities.tender import Tender
from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    TenderMilestone,
)
from app.domain.errors.calendar_errors import (
    CalendarAuthExpired,
    CalendarNotConnected,
    MilestoneTimeRequired,
)
from app.domain.errors.milestone_errors import MilestoneNotFound
from tests.unit.application.fakes import InMemoryTenderRepository
from tests.unit.application.milestone_fakes import (
    FakeCalendarProviderClient,
    InMemoryCalendarConnectionRepository,
    InMemoryCalendarEventLinkRepository,
    InMemoryTenderMilestoneRepository,
)

AHORA = datetime(2026, 10, 1, 12, 0)
GOOGLE = CalendarProvider.GOOGLE
USUARIO = uuid4()
BASE_URL = "https://proyectosya.cl"


class Escenario:
    def __init__(self, conectado: bool = True, token_vencido: bool = False):
        self.tender = Tender(
            code="COT-1",
            name="Reparación de techumbre",
            status_id=1,
            published_at=AHORA,
            closing_at=AHORA + timedelta(days=20),
            last_change_at=AHORA,
            buyer_rut="1-9",
            buyer_unit="Operaciones",
        )
        self.tenders = InMemoryTenderRepository()
        self.tenders.tenders[self.tender.id] = self.tender
        self.hitos = InMemoryTenderMilestoneRepository()
        self.conexiones = InMemoryCalendarConnectionRepository()
        self.enlaces = InMemoryCalendarEventLinkRepository()
        self.google = FakeCalendarProviderClient()
        self.conexion = CalendarConnection(
            user_id=USUARIO,
            provider=GOOGLE,
            access_token="ya29.vigente",
            refresh_token="1//refresco",
            expires_at=AHORA + (timedelta(minutes=-5) if token_vencido else timedelta(hours=1)),
            account_email="usuario@gmail.com",
        )
        if conectado:
            self.conexiones.items[(USUARIO, GOOGLE)] = self.conexion
        self.use_case = SyncMilestonesToCalendarUseCase(
            tenders=self.tenders,
            milestones=self.hitos,
            connections=self.conexiones,
            event_links=self.enlaces,
            providers={GOOGLE: self.google},
            app_base_url=BASE_URL,
            now=lambda: AHORA,
        )

    async def hito(self, has_time: bool = True, dias: int = 5, tender_id: UUID | None = None) -> TenderMilestone:
        hito = TenderMilestone(
            user_id=USUARIO,
            tender_id=tender_id or self.tender.id,
            kind=MilestoneKind.VISITA_TECNICA,
            title=f"Visita técnica {uuid4().hex[:4]}",
            source=MilestoneSource.IA_DOCUMENTO,
            due_at=datetime(2026, 10, 20, 18, 0) if has_time else datetime(2026, 10, 20, 3, 0),
            has_time=has_time,
        )
        await self.hitos.save_many([hito])
        return hito

    async def sincronizar(self, hitos: list[TenderMilestone], default_time: time | None = None):
        return await self.use_case.execute(USUARIO, GOOGLE, self.tender.id, [h.id for h in hitos], default_time)


class TestCreacion:
    async def test_crea_un_evento_por_hito_con_titulo_fecha_y_enlace(self):
        escenario = Escenario()
        hito = await escenario.hito()

        resultado = await escenario.sincronizar([hito])

        assert [(r.milestone_id, r.synced) for r in resultado.results] == [(hito.id, True)]
        evento = next(iter(escenario.google.eventos.values()))
        assert evento.title == f"{hito.title} — Reparación de techumbre"
        assert evento.start == hito.due_at
        assert evento.return_url == f"{BASE_URL}/matches/{escenario.tender.id}"
        assert escenario.google.tokens_usados == ["ya29.vigente"]

    async def test_guarda_el_enlace_para_no_duplicar(self):
        escenario = Escenario()
        hito = await escenario.hito()

        await escenario.sincronizar([hito])

        enlaces = await escenario.enlaces.list_by_milestones([hito.id], GOOGLE)
        assert len(enlaces) == 1
        assert enlaces[0].synced_due_at == hito.due_at

    async def test_volver_a_sincronizar_actualiza_el_mismo_evento(self):
        escenario = Escenario()
        hito = await escenario.hito()
        await escenario.sincronizar([hito])
        evento_id = next(iter(escenario.google.eventos))

        await escenario.sincronizar([hito])

        assert list(escenario.google.eventos) == [evento_id]
        assert escenario.google.actualizados == [evento_id]

    async def test_si_el_usuario_borro_el_evento_lo_vuelve_a_crear(self):
        escenario = Escenario()
        hito = await escenario.hito()
        await escenario.sincronizar([hito])
        borrado = next(iter(escenario.google.eventos))
        escenario.google.eventos.pop(borrado)

        resultado = await escenario.sincronizar([hito])

        assert resultado.results[0].synced is True
        nuevo = (await escenario.enlaces.list_by_milestones([hito.id], GOOGLE))[0].external_event_id
        assert nuevo != borrado
        assert nuevo in escenario.google.eventos


class TestHoraPorDefecto:
    async def test_sin_hora_y_sin_hora_por_defecto_la_pide_para_esos_hitos(self):
        escenario = Escenario()
        con_hora = await escenario.hito()
        sin_hora = await escenario.hito(has_time=False)

        with pytest.raises(MilestoneTimeRequired) as error:
            await escenario.sincronizar([con_hora, sin_hora])

        assert error.value.milestone_ids == [sin_hora.id]
        assert escenario.google.eventos == {}

    async def test_aplica_la_hora_por_defecto_en_hora_de_chile(self):
        escenario = Escenario()
        sin_hora = await escenario.hito(has_time=False)

        await escenario.sincronizar([sin_hora], default_time=time(9, 0))

        evento = next(iter(escenario.google.eventos.values()))
        assert evento.start == datetime(2026, 10, 20, 12, 0)  # 09:00 Chile (UTC-3)

    async def test_la_hora_por_defecto_no_cambia_los_hitos_con_hora(self):
        escenario = Escenario()
        con_hora = await escenario.hito()

        await escenario.sincronizar([con_hora], default_time=time(9, 0))

        assert next(iter(escenario.google.eventos.values())).start == con_hora.due_at


class TestConexion:
    async def test_sin_conexion_pide_conectar(self):
        escenario = Escenario(conectado=False)
        hito = await escenario.hito()

        with pytest.raises(CalendarNotConnected):
            await escenario.sincronizar([hito])

    async def test_una_conexion_revocada_pide_reconectar(self):
        escenario = Escenario()
        escenario.conexiones.items[(USUARIO, GOOGLE)] = escenario.conexion.model_copy(
            update={"status": CalendarConnectionStatus.REVOKED}
        )
        hito = await escenario.hito()

        with pytest.raises(CalendarAuthExpired):
            await escenario.sincronizar([hito])

    async def test_refresca_un_token_vencido_y_lo_guarda(self):
        escenario = Escenario(token_vencido=True)
        escenario.google.tokens = OAuthTokens(
            access_token="ya29.nuevo", refresh_token=None, expires_at=AHORA + timedelta(hours=1)
        )
        hito = await escenario.hito()

        await escenario.sincronizar([hito])

        assert escenario.google.refrescos == ["1//refresco"]
        assert escenario.google.tokens_usados == ["ya29.nuevo"]
        guardada = await escenario.conexiones.get(USUARIO, GOOGLE)
        assert guardada is not None
        assert guardada.access_token.get_secret_value() == "ya29.nuevo"
        assert guardada.refresh_token.get_secret_value() == "1//refresco"

    async def test_si_el_refresh_fue_revocado_marca_la_conexion_y_pide_reconectar(self):
        escenario = Escenario(token_vencido=True)
        escenario.google.refresh_revocado = True
        hito = await escenario.hito()

        with pytest.raises(CalendarAuthExpired):
            await escenario.sincronizar([hito])

        guardada = await escenario.conexiones.get(USUARIO, GOOGLE)
        assert guardada is not None
        assert guardada.status is CalendarConnectionStatus.REVOKED

    async def test_si_google_rechaza_el_token_refresca_una_vez_y_reintenta(self):
        escenario = Escenario()
        escenario.google.rechazar_token = "ya29.vigente"
        hito = await escenario.hito()

        resultado = await escenario.sincronizar([hito])

        assert resultado.results[0].synced is True
        assert escenario.google.refrescos == ["1//refresco"]


class TestFallos:
    async def test_un_fallo_de_google_no_detiene_los_demas_hitos(self):
        escenario = Escenario()
        bueno, malo = await escenario.hito(), await escenario.hito()
        escenario.google.fallar_en = {malo.id}

        resultado = await escenario.sincronizar([bueno, malo])

        por_hito = {r.milestone_id: r.synced for r in resultado.results}
        assert por_hito == {bueno.id: True, malo.id: False}
        assert resultado.failed_count == 1
        assert await escenario.enlaces.list_by_milestones([malo.id], GOOGLE) == []

    async def test_rechaza_hitos_de_otra_licitacion(self):
        escenario = Escenario()
        ajeno = await escenario.hito(tender_id=uuid4())

        with pytest.raises(MilestoneNotFound):
            await escenario.sincronizar([ajeno])

    async def test_ya_sincronizado_con_otra_fecha_se_actualiza(self):
        escenario = Escenario()
        hito = await escenario.hito()
        await escenario.enlaces.save(
            CalendarEventLink(
                user_id=USUARIO,
                milestone_id=hito.id,
                provider=GOOGLE,
                external_event_id="evento-previo",
                synced_due_at=hito.due_at - timedelta(days=1),
            )
        )
        escenario.google.eventos["evento-previo"] = None  # type: ignore[assignment]

        await escenario.sincronizar([hito])

        assert escenario.google.actualizados == ["evento-previo"]
        enlace = (await escenario.enlaces.list_by_milestones([hito.id], GOOGLE))[0]
        assert enlace.synced_due_at == hito.due_at
