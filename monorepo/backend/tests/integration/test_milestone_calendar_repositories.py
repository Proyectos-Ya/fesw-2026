"""Repositorios de hitos y calendario contra Postgres real (HU-16)."""

from datetime import datetime, time, timedelta
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.calendar import (
    CalendarConnection,
    CalendarConnectionStatus,
    CalendarEventLink,
    CalendarOAuthState,
    CalendarProvider,
)
from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    TenderMilestone,
)
from app.infrastructure.repositories.calendar_repository import (
    CalendarConnectionRepository,
    CalendarEventLinkRepository,
    CalendarOAuthStateRepository,
)
from app.infrastructure.repositories.tender_milestone_repository import (
    TenderMilestoneRepository,
)
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    RegionModel,
    TenderModel,
    TenderStatusModel,
)
from app.infrastructure.repositories.user_model import UserModel
from app.infrastructure.services.security.fernet_token_cipher import FernetTokenCipher
from app.shared.datetime_utils import utc_now_naive
from app.shared.regions import CHILE_REGIONS

GOOGLE = CalendarProvider.GOOGLE


async def _usuario(session: AsyncSession) -> UUID:
    ahora = utc_now_naive()
    user_id = uuid4()
    session.add(
        UserModel(
            id=user_id,
            email=f"{uuid4()}@example.com",
            full_name="Representante",
            created_at=ahora,
            updated_at=ahora,
        )
    )
    await session.commit()
    return user_id


async def _licitacion(session: AsyncSession) -> UUID:
    ahora = utc_now_naive()
    if await session.get(TenderStatusModel, 1) is None:
        session.add(RegionModel(id=13, name=CHILE_REGIONS[13]))
        session.add(TenderStatusModel(id=1, code="publicada", name="Publicada"))
        session.add(
            BuyerInstitutionModel(
                rut="12.345.678-9",
                name="Municipalidad",
                region_id=13,
                created_at=ahora,
                updated_at=ahora,
            )
        )
    tender_id = uuid4()
    session.add(
        TenderModel(
            id=tender_id,
            code=f"COT-{uuid4().hex[:8]}",
            name="Reparación de techumbre",
            status_id=1,
            published_at=ahora,
            closing_at=ahora + timedelta(days=10),
            last_change_at=ahora,
            buyer_rut="12.345.678-9",
            buyer_unit="Operaciones",
            available_amount_clp=1000.0,
            created_at=ahora,
            updated_at=ahora,
        )
    )
    await session.commit()
    return tender_id


def _hito(user_id: UUID, tender_id: UUID, dias: int, **cambios: object) -> TenderMilestone:
    datos: dict[str, object] = {
        "user_id": user_id,
        "tender_id": tender_id,
        "kind": MilestoneKind.VISITA_TECNICA,
        "title": f"Hito a {dias} días",
        "source": MilestoneSource.IA_DOCUMENTO,
        "source_excerpt": "La visita técnica será el día 20 a las 15:00 horas.",
        "due_at": datetime(2026, 10, 1, 12, 0) + timedelta(days=dias),
        "has_time": True,
    }
    datos.update(cambios)
    return TenderMilestone.model_validate(datos)


class TestHitos:
    async def test_guarda_y_lista_los_hitos_ordenados_por_fecha(self, db_session: AsyncSession):
        user_id = await _usuario(db_session)
        tender_id = await _licitacion(db_session)
        repo = TenderMilestoneRepository(db_session)

        await repo.save_many([_hito(user_id, tender_id, 9), _hito(user_id, tender_id, 2)])
        hitos = await repo.list_for_tender(user_id, tender_id)

        assert [h.title for h in hitos] == ["Hito a 2 días", "Hito a 9 días"]
        assert hitos[0].source_excerpt is not None

    async def test_no_mezcla_hitos_de_otro_usuario(self, db_session: AsyncSession):
        user_id = await _usuario(db_session)
        otro = await _usuario(db_session)
        tender_id = await _licitacion(db_session)
        repo = TenderMilestoneRepository(db_session)

        await repo.save_many([_hito(otro, tender_id, 3)])

        assert await repo.list_for_tender(user_id, tender_id) == []

    async def test_actualiza_un_hito_existente_por_id(self, db_session: AsyncSession):
        user_id = await _usuario(db_session)
        tender_id = await _licitacion(db_session)
        repo = TenderMilestoneRepository(db_session)
        hito = _hito(user_id, tender_id, 3, has_time=False)
        await repo.save_many([hito])

        await repo.save_many([hito.con_hora(time(9, 0))])
        hitos = await repo.list_for_tender(user_id, tender_id)

        assert len(hitos) == 1
        assert hitos[0].has_time is True

    async def test_busca_por_ids_solo_dentro_del_usuario(self, db_session: AsyncSession):
        user_id = await _usuario(db_session)
        otro = await _usuario(db_session)
        tender_id = await _licitacion(db_session)
        repo = TenderMilestoneRepository(db_session)
        propio, ajeno = _hito(user_id, tender_id, 1), _hito(otro, tender_id, 1)
        await repo.save_many([propio, ajeno])

        encontrados = await repo.list_by_ids(user_id, [propio.id, ajeno.id])

        assert [h.id for h in encontrados] == [propio.id]

    async def test_borra_hitos_del_usuario(self, db_session: AsyncSession):
        user_id = await _usuario(db_session)
        tender_id = await _licitacion(db_session)
        repo = TenderMilestoneRepository(db_session)
        hito = _hito(user_id, tender_id, 1)
        await repo.save_many([hito])

        await repo.delete_many(user_id, [hito.id])

        assert await repo.list_for_tender(user_id, tender_id) == []


class TestConexiones:
    def _repo(self, session: AsyncSession) -> CalendarConnectionRepository:
        return CalendarConnectionRepository(session, FernetTokenCipher(Fernet.generate_key().decode()))

    def _conexion(self, user_id: UUID, access: str = "ya29.acceso") -> CalendarConnection:
        return CalendarConnection(
            user_id=user_id,
            provider=GOOGLE,
            access_token=access,
            refresh_token="1//refresco",
            expires_at=utc_now_naive() + timedelta(hours=1),
            account_email="usuario@gmail.com",
        )

    async def test_los_tokens_se_guardan_cifrados_en_la_base(self, db_session: AsyncSession):
        user_id = await _usuario(db_session)

        await self._repo(db_session).save(self._conexion(user_id))
        fila = (
            await db_session.exec(  # type: ignore[call-overload]
                text(
                    "SELECT access_token_encrypted, refresh_token_encrypted "
                    "FROM calendar_connection WHERE user_id = :u"
                ).bindparams(u=user_id)
            )
        ).one()

        assert "ya29.acceso" not in fila[0]
        assert "1//refresco" not in fila[1]

    async def test_se_leen_descifrados(self, db_session: AsyncSession):
        user_id = await _usuario(db_session)
        repo = self._repo(db_session)
        await repo.save(self._conexion(user_id))

        conexion = await repo.get(user_id, GOOGLE)

        assert conexion is not None
        assert conexion.access_token.get_secret_value() == "ya29.acceso"
        assert conexion.refresh_token.get_secret_value() == "1//refresco"
        assert conexion.account_email == "usuario@gmail.com"

    async def test_guardar_de_nuevo_reemplaza_la_conexion(self, db_session: AsyncSession):
        user_id = await _usuario(db_session)
        repo = self._repo(db_session)
        await repo.save(self._conexion(user_id, access="viejo"))

        await repo.save(self._conexion(user_id, access="nuevo").model_copy(
            update={"status": CalendarConnectionStatus.REVOKED}
        ))
        conexion = await repo.get(user_id, GOOGLE)

        assert conexion is not None
        assert conexion.access_token.get_secret_value() == "nuevo"
        assert conexion.status is CalendarConnectionStatus.REVOKED

    async def test_borrar_la_conexion(self, db_session: AsyncSession):
        user_id = await _usuario(db_session)
        repo = self._repo(db_session)
        await repo.save(self._conexion(user_id))

        await repo.delete(user_id, GOOGLE)

        assert await repo.get(user_id, GOOGLE) is None


class TestEstadosOAuth:
    async def test_un_estado_se_consume_una_sola_vez(self, db_session: AsyncSession):
        user_id = await _usuario(db_session)
        tender_id = await _licitacion(db_session)
        repo = CalendarOAuthStateRepository(db_session)
        estado = CalendarOAuthState(
            state_hash="f" * 64,
            user_id=user_id,
            provider=GOOGLE,
            tender_id=tender_id,
            milestone_ids=[uuid4(), uuid4()],
            default_time=time(9, 0),
            expires_at=utc_now_naive() + timedelta(minutes=10),
        )
        await repo.save(estado)

        primero = await repo.consume("f" * 64)
        segundo = await repo.consume("f" * 64)

        assert primero is not None
        assert primero.milestone_ids == estado.milestone_ids
        assert primero.default_time == time(9, 0)
        assert segundo is None


class TestEnlacesDeEventos:
    async def test_guarda_y_actualiza_el_enlace_por_hito_y_proveedor(
        self, db_session: AsyncSession
    ):
        user_id = await _usuario(db_session)
        tender_id = await _licitacion(db_session)
        hito = _hito(user_id, tender_id, 5)
        await TenderMilestoneRepository(db_session).save_many([hito])
        repo = CalendarEventLinkRepository(db_session)
        enlace = CalendarEventLink(
            user_id=user_id,
            milestone_id=hito.id,
            provider=GOOGLE,
            external_event_id="evento-1",
            synced_due_at=hito.due_at,
        )

        await repo.save(enlace)
        await repo.save(enlace.model_copy(update={"synced_due_at": hito.due_at + timedelta(days=1)}))
        enlaces = await repo.list_by_milestones([hito.id], GOOGLE)

        assert len(enlaces) == 1
        assert enlaces[0].external_event_id == "evento-1"
        assert enlaces[0].synced_due_at == hito.due_at + timedelta(days=1)

    async def test_borrar_el_hito_borra_su_enlace(self, db_session: AsyncSession):
        user_id = await _usuario(db_session)
        tender_id = await _licitacion(db_session)
        hitos = TenderMilestoneRepository(db_session)
        hito = _hito(user_id, tender_id, 5)
        await hitos.save_many([hito])
        repo = CalendarEventLinkRepository(db_session)
        await repo.save(
            CalendarEventLink(
                user_id=user_id,
                milestone_id=hito.id,
                provider=GOOGLE,
                external_event_id="evento-1",
                synced_due_at=hito.due_at,
            )
        )

        await hitos.delete_many(user_id, [hito.id])

        assert await repo.list_by_milestones([hito.id], GOOGLE) == []


pytestmark = pytest.mark.integration


class TestConsultasDelRefresco:
    async def test_hitos_oficiales_de_todos_los_usuarios(self, db_session: AsyncSession):
        uno, otro = await _usuario(db_session), await _usuario(db_session)
        tender_id = await _licitacion(db_session)
        repo = TenderMilestoneRepository(db_session)
        oficial = _hito(uno, tender_id, 2, source=MilestoneSource.MERCADO_PUBLICO)
        oficial_otro = _hito(otro, tender_id, 2, source=MilestoneSource.MERCADO_PUBLICO)
        de_ia = _hito(uno, tender_id, 3)
        await repo.save_many([oficial, oficial_otro, de_ia])

        encontrados = await repo.list_by_tender_and_source(tender_id, MilestoneSource.MERCADO_PUBLICO)

        assert {h.id for h in encontrados} == {oficial.id, oficial_otro.id}

    async def test_licitaciones_con_hitos_sincronizados_y_sus_enlaces(self, db_session: AsyncSession):
        user_id = await _usuario(db_session)
        sincronizada = await _licitacion(db_session)
        sin_sincronizar = await _licitacion(db_session)
        hitos = TenderMilestoneRepository(db_session)
        hito, otro_hito = _hito(user_id, sincronizada, 2), _hito(user_id, sincronizada, 4)
        await hitos.save_many([hito, otro_hito, _hito(user_id, sin_sincronizar, 2)])
        repo = CalendarEventLinkRepository(db_session)
        for h in (hito, otro_hito):
            await repo.save(
                CalendarEventLink(
                    user_id=user_id,
                    milestone_id=h.id,
                    provider=GOOGLE,
                    external_event_id=f"evento-{h.id}",
                    synced_due_at=h.due_at,
                )
            )

        assert await repo.list_linked_tender_ids() == [sincronizada]
        assert {e.milestone_id for e in await repo.list_by_tender(sincronizada)} == {hito.id, otro_hito.id}
        assert await repo.list_by_tender(sin_sincronizar) == []


class TestAvisoDeFechaModificada:
    async def test_convive_con_el_de_compatibilidad_y_no_cuenta_como_avisado(self, db_session: AsyncSession):
        from app.domain.entities.notification import MilestoneDateChange, Notification
        from app.infrastructure.repositories.notification_repository import (
            NotificationRepository,
        )

        user_id = await _usuario(db_session)
        tender_id = await _licitacion(db_session)
        repo = NotificationRepository(db_session)
        await repo.save_bulk([Notification(user_id=user_id, tender_id=tender_id, score=0.9)])
        cambio = MilestoneDateChange(
            label="Cierre de recepción de ofertas",
            previous_at=datetime(2026, 10, 20, 18, 0),
            new_at=datetime(2026, 10, 27, 18, 0),
        )

        aviso = await repo.save_date_change(
            Notification(user_id=user_id, tender_id=tender_id, kind="date_changed", date_changes=[cambio])
        )

        guardados = await repo.list_by_user(user_id)
        assert {a.kind for a in guardados} == {"match", "date_changed"}
        leido = await repo.get(aviso.id)
        assert leido is not None
        assert leido.score is None
        assert leido.date_changes == [cambio]

    async def test_un_segundo_cambio_reemplaza_el_aviso_y_lo_marca_no_leido(self, db_session: AsyncSession):
        from app.domain.entities.notification import MilestoneDateChange, Notification
        from app.infrastructure.repositories.notification_repository import (
            NotificationRepository,
        )

        user_id = await _usuario(db_session)
        tender_id = await _licitacion(db_session)
        repo = NotificationRepository(db_session)

        def _aviso(dias: int) -> Notification:
            return Notification(
                user_id=user_id,
                tender_id=tender_id,
                kind="date_changed",
                date_changes=[
                    MilestoneDateChange(
                        label="Cierre",
                        previous_at=datetime(2026, 10, 20),
                        new_at=datetime(2026, 10, 20) + timedelta(days=dias),
                    )
                ],
            )

        primero = await repo.save_date_change(_aviso(7))
        await repo.mark_all_read(user_id)
        segundo = await repo.save_date_change(_aviso(9))

        assert segundo.id == primero.id
        assert segundo.read_at is None
        assert segundo.date_changes[0].new_at == datetime(2026, 10, 29)
        assert await repo.count_unread(user_id) == 1
