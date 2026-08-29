"""Pruebas e2e del router /notifications.

Todas las rutas requieren sesión iniciada. Los repositorios se sustituyen por
dobles en memoria, así que no hace falta Postgres.
"""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import bootstrap
from app.domain.entities.notification import Notification, NotificationDelivery
from app.domain.entities.tender import Tender
from app.main import app
from app.shared.datetime_utils import utc_now_naive
from tests.unit.application.fakes import (
    FakeEmbeddingService,
    FakeSupplierVectorRepository,
    InMemoryNotificationDeliveryRepository,
    InMemoryNotificationPreferenceRepository,
    InMemoryNotificationRepository,
    InMemorySupplierRepository,
    InMemoryTenderRepository,
    InMemoryUserRepository,
)

REGISTER = {
    "email": "alertas@example.com",
    "password": "supersecret",
    "full_name": "Empresa Alertas",
}


class Dobles:
    """Los repositorios en memoria que usa el test, accesibles para prepararlos."""

    def __init__(self) -> None:
        self.users = InMemoryUserRepository()
        self.notifications = InMemoryNotificationRepository()
        self.preferences = InMemoryNotificationPreferenceRepository()
        self.deliveries = InMemoryNotificationDeliveryRepository()
        self.tenders = InMemoryTenderRepository()


def build_tender(tender_id, closing_at) -> Tender:
    return Tender(
        id=tender_id,
        code="1057539-228-COT26",
        name="Mantención de áreas verdes",
        status_id=1,
        status_code="publicada",
        published_at=utc_now_naive(),
        closing_at=closing_at,
        last_change_at=utc_now_naive(),
        buyer_rut="61.980.170-9",
        buyer_name="Municipalidad de Providencia",
        buyer_unit="Operaciones",
    )


@pytest_asyncio.fixture
async def dobles() -> Dobles:
    return Dobles()


@pytest_asyncio.fixture
async def api(dobles: Dobles) -> AsyncGenerator[AsyncClient, None]:
    from app.application.use_cases.notifications.manage_notifications import (
        CountUnreadNotificationsUseCase,
        GetNotificationPreferencesUseCase,
        ListDeliveriesUseCase,
        ListNotificationsUseCase,
        MarkAllNotificationsReadUseCase,
        MarkNotificationReadUseCase,
        UpdateNotificationPreferencesUseCase,
    )

    app.dependency_overrides[bootstrap.get_user_repo] = lambda: dobles.users
    app.dependency_overrides[bootstrap.get_supplier_repo] = lambda: (
        InMemorySupplierRepository()
    )
    app.dependency_overrides[bootstrap.get_supplier_vector_repo] = lambda: (
        FakeSupplierVectorRepository()
    )
    app.dependency_overrides[bootstrap.get_embedding_service] = lambda: (
        FakeEmbeddingService()
    )
    app.dependency_overrides[bootstrap.get_list_notifications_use_case] = lambda: (
        ListNotificationsUseCase(
            notification_repo=dobles.notifications, tender_repo=dobles.tenders
        )
    )
    app.dependency_overrides[bootstrap.get_count_unread_use_case] = lambda: (
        CountUnreadNotificationsUseCase(notification_repo=dobles.notifications)
    )
    app.dependency_overrides[bootstrap.get_mark_notification_read_use_case] = lambda: (
        MarkNotificationReadUseCase(notification_repo=dobles.notifications)
    )
    app.dependency_overrides[bootstrap.get_mark_all_read_use_case] = lambda: (
        MarkAllNotificationsReadUseCase(notification_repo=dobles.notifications)
    )
    app.dependency_overrides[bootstrap.get_notification_preferences_use_case] = lambda: (
        GetNotificationPreferencesUseCase(preference_repo=dobles.preferences)
    )
    app.dependency_overrides[bootstrap.get_update_notification_preferences_use_case] = (
        lambda: UpdateNotificationPreferencesUseCase(preference_repo=dobles.preferences)
    )
    app.dependency_overrides[bootstrap.get_list_deliveries_use_case] = lambda: (
        ListDeliveriesUseCase(delivery_repo=dobles.deliveries)
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


async def login(api: AsyncClient) -> str:
    """Registra e inicia sesión; deja la cookie en el cliente y devuelve el id."""
    await api.post("/auth/register", json=REGISTER)
    resp = await api.post(
        "/auth/login",
        json={"email": REGISTER["email"], "password": REGISTER["password"]},
    )
    assert resp.status_code == 200
    me = await api.get("/auth/me")
    return me.json()["id"]


@pytest.mark.asyncio
class TestAutenticacion:
    async def test_listar_sin_sesion_devuelve_401(self, api: AsyncClient):
        assert (await api.get("/notifications")).status_code == 401

    async def test_preferencias_sin_sesion_devuelve_401(self, api: AsyncClient):
        assert (await api.get("/notifications/preferences")).status_code == 401


@pytest.mark.asyncio
class TestListado:
    async def test_sin_avisos_devuelve_lista_vacia(self, api: AsyncClient):
        await login(api)

        resp = await api.get("/notifications")

        assert resp.status_code == 200
        assert resp.json() == []

    async def test_devuelve_el_aviso_con_la_licitacion_y_el_porcentaje(
        self, api: AsyncClient, dobles: Dobles
    ):
        user_id = await login(api)
        tender_id = uuid4()
        futuro = utc_now_naive().replace(year=utc_now_naive().year + 1)
        dobles.tenders.tenders[tender_id] = build_tender(tender_id, futuro)
        await dobles.notifications.save(
            Notification(user_id=user_id, tender_id=tender_id, score=0.84)
        )

        resp = await api.get("/notifications")

        cuerpo = resp.json()
        assert len(cuerpo) == 1
        # El dominio guarda 0.84; la API expone 84.
        assert cuerpo[0]["score_pct"] == 84
        assert cuerpo[0]["is_closed"] is False
        assert cuerpo[0]["tender"]["name"] == "Mantención de áreas verdes"

    async def test_marca_como_cerrada_una_licitacion_vencida(
        self, api: AsyncClient, dobles: Dobles
    ):
        # Criterio: la alerta de una licitación que ya cerró debe decirlo.
        user_id = await login(api)
        tender_id = uuid4()
        pasado = utc_now_naive().replace(year=utc_now_naive().year - 1)
        dobles.tenders.tenders[tender_id] = build_tender(tender_id, pasado)
        await dobles.notifications.save(
            Notification(user_id=user_id, tender_id=tender_id, score=0.84)
        )

        resp = await api.get("/notifications")

        assert resp.json()[0]["is_closed"] is True

    async def test_filtra_por_no_leidas(self, api: AsyncClient, dobles: Dobles):
        user_id = await login(api)
        leido = Notification(user_id=user_id, tender_id=uuid4(), score=0.8)
        leido.mark_read()
        await dobles.notifications.save(leido)
        await dobles.notifications.save(
            Notification(user_id=user_id, tender_id=uuid4(), score=0.9)
        )

        resp = await api.get("/notifications", params={"only_unread": "true"})

        assert len(resp.json()) == 1


@pytest.mark.asyncio
class TestLectura:
    async def test_contador_de_no_leidas(self, api: AsyncClient, dobles: Dobles):
        user_id = await login(api)
        await dobles.notifications.save(
            Notification(user_id=user_id, tender_id=uuid4(), score=0.9)
        )

        resp = await api.get("/notifications/unread-count")

        assert resp.json() == {"count": 1}

    async def test_marcar_uno_como_leido(self, api: AsyncClient, dobles: Dobles):
        user_id = await login(api)
        aviso = Notification(user_id=user_id, tender_id=uuid4(), score=0.9)
        await dobles.notifications.save(aviso)

        resp = await api.post(f"/notifications/{aviso.id}/read")

        assert resp.status_code == 200
        assert resp.json()["read_at"] is not None
        assert await dobles.notifications.count_unread(user_id) == 0

    async def test_no_deja_marcar_un_aviso_ajeno(
        self, api: AsyncClient, dobles: Dobles
    ):
        await login(api)
        ajeno = Notification(user_id=uuid4(), tender_id=uuid4(), score=0.9)
        await dobles.notifications.save(ajeno)

        resp = await api.post(f"/notifications/{ajeno.id}/read")

        assert resp.status_code == 404

    async def test_marcar_todo_como_leido(self, api: AsyncClient, dobles: Dobles):
        user_id = await login(api)
        for _ in range(3):
            await dobles.notifications.save(
                Notification(user_id=user_id, tender_id=uuid4(), score=0.9)
            )

        resp = await api.post("/notifications/read-all")

        assert resp.json() == {"updated": 3}
        assert await dobles.notifications.count_unread(user_id) == 0


@pytest.mark.asyncio
class TestPreferencias:
    async def test_devuelve_los_valores_por_defecto(self, api: AsyncClient):
        await login(api)

        resp = await api.get("/notifications/preferences")

        cuerpo = resp.json()
        assert cuerpo["enabled"] is True
        assert cuerpo["threshold_pct"] == 70
        assert cuerpo["delivery_mode"] == "immediate"
        assert cuerpo["email_delivery_enabled"] is True

    async def test_guarda_un_umbral_personalizado(self, api: AsyncClient):
        await login(api)

        resp = await api.patch("/notifications/preferences", json={"threshold_pct": 55})

        assert resp.json()["threshold_pct"] == 55
        # Y persiste entre peticiones.
        assert (await api.get("/notifications/preferences")).json()[
            "threshold_pct"
        ] == 55

    async def test_cambia_a_resumen_diario(self, api: AsyncClient):
        await login(api)

        resp = await api.patch(
            "/notifications/preferences", json={"delivery_mode": "daily_digest"}
        )

        assert resp.json()["delivery_mode"] == "daily_digest"

    async def test_rechaza_un_modo_de_entrega_invalido(self, api: AsyncClient):
        await login(api)

        resp = await api.patch(
            "/notifications/preferences", json={"delivery_mode": "por_paloma"}
        )

        assert resp.status_code == 422

    async def test_rechaza_un_umbral_fuera_de_rango(self, api: AsyncClient):
        await login(api)

        resp = await api.patch("/notifications/preferences", json={"threshold_pct": 0})

        assert resp.status_code == 422

    async def test_permite_apagar_las_alertas(self, api: AsyncClient):
        await login(api)

        resp = await api.patch("/notifications/preferences", json={"enabled": False})

        assert resp.json()["enabled"] is False

    async def test_reactivar_el_correo_limpia_el_fallo(
        self, api: AsyncClient, dobles: Dobles
    ):
        from app.domain.entities.notification import NotificationPreference

        user_id = await login(api)
        await dobles.preferences.save(
            NotificationPreference(
                user_id=user_id,
                email_delivery_enabled=False,
                last_failure_reason="la dirección no existe",
                last_failure_at=utc_now_naive(),
            )
        )

        resp = await api.post("/notifications/preferences/reactivate-email")

        cuerpo = resp.json()
        assert cuerpo["email_delivery_enabled"] is True
        assert cuerpo["last_failure_reason"] is None


@pytest.mark.asyncio
class TestBandejaDeSalida:
    async def test_muestra_una_entrega_pendiente_con_su_reintento(
        self, api: AsyncClient, dobles: Dobles
    ):
        # Es la evidencia visible del criterio "guarda el evento como Pendiente".
        user_id = await login(api)
        entrega = NotificationDelivery(
            user_id=user_id, notification_ids=[uuid4()], next_attempt_at=utc_now_naive()
        )
        entrega.register_transient_failure("conexión rechazada", utc_now_naive())
        await dobles.deliveries.save(entrega)

        resp = await api.get("/notifications/deliveries")

        cuerpo = resp.json()
        assert len(cuerpo) == 1
        assert cuerpo[0]["status"] == "pending"
        assert cuerpo[0]["attempts"] == 1
        assert cuerpo[0]["last_error"] == "conexión rechazada"
