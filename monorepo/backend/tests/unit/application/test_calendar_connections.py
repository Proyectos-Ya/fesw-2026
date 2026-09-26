from datetime import datetime, timedelta
from uuid import uuid4

from app.application.use_cases.calendar.calendar_connections import (
    DisconnectCalendarUseCase,
    GetCalendarConnectionsUseCase,
)
from app.domain.entities.calendar import (
    CalendarConnection,
    CalendarConnectionStatus,
    CalendarProvider,
)
from tests.unit.application.milestone_fakes import (
    FakeCalendarProviderClient,
    InMemoryCalendarConnectionRepository,
)

GOOGLE = CalendarProvider.GOOGLE
USUARIO = uuid4()


def _conexion(**cambios: object) -> CalendarConnection:
    datos: dict[str, object] = {
        "user_id": USUARIO,
        "provider": GOOGLE,
        "access_token": "a",
        "refresh_token": "1//refresco",
        "expires_at": datetime(2026, 10, 1) + timedelta(hours=1),
        "account_email": "usuario@gmail.com",
    }
    datos.update(cambios)
    return CalendarConnection.model_validate(datos)


async def test_informa_cada_proveedor_configurado_y_su_estado():
    conexiones = InMemoryCalendarConnectionRepository()
    use_case = GetCalendarConnectionsUseCase(conexiones, {GOOGLE: FakeCalendarProviderClient()})

    sin_conectar = await use_case.execute(USUARIO)
    await conexiones.save(_conexion())
    conectado = await use_case.execute(USUARIO)

    assert [(c.provider, c.connected, c.account_email) for c in sin_conectar] == [(GOOGLE, False, None)]
    assert [(c.provider, c.connected, c.account_email) for c in conectado] == [
        (GOOGLE, True, "usuario@gmail.com")
    ]


async def test_una_conexion_revocada_no_cuenta_como_conectada():
    conexiones = InMemoryCalendarConnectionRepository()
    await conexiones.save(_conexion(status=CalendarConnectionStatus.REVOKED))

    resultado = await GetCalendarConnectionsUseCase(conexiones, {GOOGLE: FakeCalendarProviderClient()}).execute(USUARIO)

    assert resultado[0].connected is False
    assert resultado[0].needs_reconnect is True


async def test_sin_proveedores_configurados_la_lista_esta_vacia():
    resultado = await GetCalendarConnectionsUseCase(InMemoryCalendarConnectionRepository(), {}).execute(USUARIO)

    assert resultado == []


async def test_desconectar_revoca_en_google_y_borra_la_conexion():
    conexiones = InMemoryCalendarConnectionRepository()
    google = FakeCalendarProviderClient()
    await conexiones.save(_conexion())

    await DisconnectCalendarUseCase(conexiones, {GOOGLE: google}).execute(USUARIO, GOOGLE)

    assert google.revocados == ["1//refresco"]
    assert await conexiones.get(USUARIO, GOOGLE) is None


async def test_desconectar_sin_conexion_no_falla():
    google = FakeCalendarProviderClient()

    await DisconnectCalendarUseCase(InMemoryCalendarConnectionRepository(), {GOOGLE: google}).execute(USUARIO, GOOGLE)

    assert google.revocados == []
