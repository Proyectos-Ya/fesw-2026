"""Avisos `kanban_change` contra Postgres real (HU-18, CA2)."""

from uuid import uuid4

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.notification import Notification
from app.infrastructure.repositories.notification_repository import (
    NotificationRepository,
)
from tests.integration.test_milestone_calendar_repositories import (
    _licitacion,
    _usuario,
)


async def test_un_segundo_cambio_sobre_la_misma_licitacion_vuelve_a_avisar(
    db_session: AsyncSession,
):
    user_id = await _usuario(db_session)
    tender_id = await _licitacion(db_session)
    repo = NotificationRepository(db_session)

    primero = await repo.save_kanban_change(
        Notification(user_id=user_id, tender_id=tender_id, kind="kanban_change")
    )
    await repo.mark_all_read(user_id)
    segundo = await repo.save_kanban_change(
        Notification(user_id=user_id, tender_id=tender_id, kind="kanban_change")
    )

    avisos = await repo.list_by_user(user_id)
    assert [a.id for a in avisos] == [primero.id]
    assert segundo.id == primero.id
    assert avisos[0].read_at is None
    assert await repo.count_unread(user_id) == 1


async def test_el_aviso_de_compatibilidad_sigue_siendo_uno_por_licitacion(
    db_session: AsyncSession,
):
    user_id = await _usuario(db_session)
    tender_id = await _licitacion(db_session)
    repo = NotificationRepository(db_session)

    await repo.save_bulk([Notification(user_id=user_id, tender_id=tender_id, score=0.9)])
    await repo.save_kanban_change(
        Notification(user_id=user_id, tender_id=tender_id, kind="kanban_change")
    )

    assert {a.kind for a in await repo.list_by_user(user_id)} == {"match", "kanban_change"}

