import hashlib
from datetime import datetime, time, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.services.calendar_provider_client import OAuthTokens
from app.application.use_cases.calendar.calendar_authorization import (
    CompleteCalendarAuthorizationUseCase,
    StartCalendarAuthorizationUseCase,
)
from app.domain.entities.calendar import (
    CalendarConnection,
    CalendarConnectionStatus,
    CalendarProvider,
)
from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    TenderMilestone,
)
from app.domain.errors.calendar_errors import (
    CalendarAuthExpired,
    CalendarNotConfigured,
    InvalidOAuthState,
)
from app.domain.errors.milestone_errors import MilestoneNotFound
from tests.unit.application.milestone_fakes import (
    FakeCalendarProviderClient,
    InMemoryCalendarConnectionRepository,
    InMemoryCalendarOAuthStateRepository,
    InMemoryTenderMilestoneRepository,
)

AHORA = datetime(2026, 10, 1, 12, 0)
GOOGLE = CalendarProvider.GOOGLE
USUARIO = uuid4()
LICITACION = uuid4()


def _hito(user_id: UUID = USUARIO, tender_id: UUID = LICITACION) -> TenderMilestone:
    return TenderMilestone(
        user_id=user_id,
        tender_id=tender_id,
        kind=MilestoneKind.VISITA_TECNICA,
        title="Visita técnica",
        source=MilestoneSource.IA_DOCUMENTO,
        due_at=AHORA + timedelta(days=5),
        has_time=False,
    )


class Escenario:
    def __init__(self, configurado: bool = True):
        self.hitos = InMemoryTenderMilestoneRepository()
        self.estados = InMemoryCalendarOAuthStateRepository()
        self.conexiones = InMemoryCalendarConnectionRepository()
        self.google = FakeCalendarProviderClient()
        proveedores = {GOOGLE: self.google} if configurado else {}
        self.reloj = [AHORA]
        self.iniciar = StartCalendarAuthorizationUseCase(
            milestones=self.hitos,
            states=self.estados,
            providers=proveedores,
            now=lambda: self.reloj[0],
        )
        self.completar = CompleteCalendarAuthorizationUseCase(
            states=self.estados,
            connections=self.conexiones,
            providers=proveedores,
            now=lambda: self.reloj[0],
        )

    async def autorizar(self, hitos: list[TenderMilestone], default_time: time | None = time(9, 0)) -> str:
        await self.hitos.save_many(hitos)
        url = await self.iniciar.execute(
            USUARIO, GOOGLE, LICITACION, [h.id for h in hitos], default_time
        )
        return url.split("state=")[1]


class TestInicio:
    async def test_devuelve_la_url_del_proveedor_con_un_state_aleatorio(self):
        escenario = Escenario()

        state = await escenario.autorizar([_hito()])

        assert len(state) >= 40
        assert escenario.google.urls_pedidas == [state]

    async def test_guarda_solo_el_hash_del_state_con_la_sincronizacion_pendiente(self):
        escenario = Escenario()
        hito = _hito()

        state = await escenario.autorizar([hito])

        guardado = next(iter(escenario.estados.items.values()))
        assert guardado.state_hash == hashlib.sha256(state.encode()).hexdigest()
        assert state not in escenario.estados.items
        assert guardado.milestone_ids == [hito.id]
        assert guardado.default_time == time(9, 0)
        assert guardado.expires_at == AHORA + timedelta(minutes=10)

    @pytest.mark.parametrize("dueno", ["otro_usuario", "otra_licitacion", "inexistente"])
    async def test_rechaza_hitos_que_no_son_del_usuario_o_de_la_licitacion(self, dueno):
        escenario = Escenario()
        propio = _hito()
        ajeno = {
            "otro_usuario": _hito(user_id=uuid4()),
            "otra_licitacion": _hito(tender_id=uuid4()),
            "inexistente": None,
        }[dueno]
        await escenario.hitos.save_many([propio] + ([ajeno] if ajeno else []))
        ids = [propio.id, ajeno.id if ajeno else uuid4()]

        with pytest.raises(MilestoneNotFound):
            await escenario.iniciar.execute(USUARIO, GOOGLE, LICITACION, ids, None)

        assert escenario.estados.items == {}

    async def test_sin_proveedor_configurado_no_se_puede_conectar(self):
        escenario = Escenario(configurado=False)

        with pytest.raises(CalendarNotConfigured):
            await escenario.autorizar([_hito()])


class TestCompletar:
    async def test_guarda_la_conexion_y_devuelve_la_sincronizacion_pendiente(self):
        escenario = Escenario()
        hito = _hito()
        state = await escenario.autorizar([hito])

        resultado = await escenario.completar.execute(USUARIO, GOOGLE, "codigo", state)

        assert resultado.tender_id == LICITACION
        assert resultado.milestone_ids == [hito.id]
        assert resultado.default_time == time(9, 0)
        assert resultado.account_email == "usuario@gmail.com"
        conexion = await escenario.conexiones.get(USUARIO, GOOGLE)
        assert conexion is not None
        assert conexion.access_token.get_secret_value() == "ya29.acceso"
        assert conexion.refresh_token.get_secret_value() == "1//refresco"
        assert conexion.status is CalendarConnectionStatus.ACTIVE
        assert escenario.google.codigos == ["codigo"]

    async def test_el_state_es_de_un_solo_uso(self):
        escenario = Escenario()
        state = await escenario.autorizar([_hito()])
        await escenario.completar.execute(USUARIO, GOOGLE, "codigo", state)

        with pytest.raises(InvalidOAuthState):
            await escenario.completar.execute(USUARIO, GOOGLE, "codigo", state)

    async def test_rechaza_un_state_de_otro_usuario(self):
        escenario = Escenario()
        state = await escenario.autorizar([_hito()])

        with pytest.raises(InvalidOAuthState):
            await escenario.completar.execute(uuid4(), GOOGLE, "codigo", state)

        assert escenario.google.codigos == []

    async def test_rechaza_un_state_vencido(self):
        escenario = Escenario()
        state = await escenario.autorizar([_hito()])
        escenario.reloj[0] = AHORA + timedelta(minutes=11)

        with pytest.raises(InvalidOAuthState):
            await escenario.completar.execute(USUARIO, GOOGLE, "codigo", state)

    async def test_rechaza_un_state_inventado(self):
        escenario = Escenario()

        with pytest.raises(InvalidOAuthState):
            await escenario.completar.execute(USUARIO, GOOGLE, "codigo", "no-existe")

    async def test_si_google_no_entrega_refresh_token_reutiliza_el_anterior(self):
        escenario = Escenario()
        await escenario.conexiones.save(
            CalendarConnection(
                user_id=USUARIO,
                provider=GOOGLE,
                access_token="viejo",
                refresh_token="1//anterior",
                expires_at=AHORA,
            )
        )
        escenario.google.tokens = OAuthTokens(
            access_token="nuevo", refresh_token=None, expires_at=AHORA + timedelta(hours=1)
        )
        state = await escenario.autorizar([_hito()])

        await escenario.completar.execute(USUARIO, GOOGLE, "codigo", state)

        conexion = await escenario.conexiones.get(USUARIO, GOOGLE)
        assert conexion is not None
        assert conexion.refresh_token.get_secret_value() == "1//anterior"

    async def test_sin_refresh_token_y_sin_conexion_previa_pide_reconectar(self):
        escenario = Escenario()
        escenario.google.tokens = OAuthTokens(
            access_token="nuevo", refresh_token=None, expires_at=AHORA + timedelta(hours=1)
        )
        state = await escenario.autorizar([_hito()])

        with pytest.raises(CalendarAuthExpired):
            await escenario.completar.execute(USUARIO, GOOGLE, "codigo", state)
