"""Tests de los use cases nuevos de HU-18.

- `RecordKanbanEventUseCase` + `ListKanbanEventsUseCase`
- `NotifyKanbanChangeUseCase`
- `SetWorkspaceMatchThresholdUseCase`
- Fallback de threshold en `ScanSupplierForAlertsUseCase`
"""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.application.repositories.kanban_event_repository import (
    IKanbanEventRepository,
)
from app.application.use_cases.kanban.list_kanban_events import (
    ListKanbanEventsUseCase,
)
from app.application.use_cases.kanban.notify_kanban_change import (
    NotifyKanbanChangeUseCase,
)
from app.application.use_cases.kanban.record_kanban_event import (
    RecordKanbanEventUseCase,
)
from app.application.use_cases.workspace.set_workspace_match_threshold import (
    SetWorkspaceMatchThresholdUseCase,
)
from app.domain.entities.kanban_event import KanbanEvent
from app.domain.entities.notification import NotificationPreference
from app.domain.entities.supplier import Supplier
from app.domain.entities.supplier_member import (
    MemberRole,
    MemberStatus,
    SupplierMember,
)
from app.domain.errors.membership_errors import UnauthorizedWorkspaceAction
from app.domain.errors.supplier_errors import SupplierNotFound
from tests.unit.application.fakes import (
    InMemoryNotificationPreferenceRepository,
    InMemoryNotificationRepository,
    InMemorySupplierMemberRepository,
    InMemorySupplierRepository,
)


class InMemoryKanbanEventRepository(IKanbanEventRepository):
    def __init__(self) -> None:
        self.events: list[KanbanEvent] = []

    async def save(self, event: KanbanEvent) -> KanbanEvent:
        self.events.append(event)
        return event

    async def list_by_supplier(
        self, supplier_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[KanbanEvent]:
        workspace_events = [e for e in self.events if e.supplier_id == supplier_id]
        workspace_events.sort(key=lambda e: e.created_at, reverse=True)
        return workspace_events[offset : offset + limit]


# ---------------------------------------------------------------------------
# RecordKanbanEventUseCase + ListKanbanEventsUseCase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_kanban_event_persiste_el_evento_con_defaults() -> None:
    repo = InMemoryKanbanEventRepository()
    use_case = RecordKanbanEventUseCase(event_repo=repo)
    supplier_id = uuid4()
    user_id = uuid4()

    event = await use_case.execute(
        supplier_id=supplier_id,
        user_id=user_id,
        event_type="card_added",
        entity_type="card",
        tender_id=uuid4(),
        tender_title="Suministro cables",
    )

    assert len(repo.events) == 1
    assert event.supplier_id == supplier_id
    assert event.user_id == user_id
    assert event.event_type == "card_added"
    assert event.details == {}


@pytest.mark.asyncio
async def test_list_kanban_events_devuelve_eventos_del_workspace_descendente() -> None:
    repo = InMemoryKanbanEventRepository()
    supplier_id = uuid4()
    other_supplier = uuid4()
    user_id = uuid4()

    recorder = RecordKanbanEventUseCase(event_repo=repo)
    primero = await recorder.execute(
        supplier_id=supplier_id, user_id=user_id, event_type="column_created"
    )
    segundo = await recorder.execute(
        supplier_id=supplier_id, user_id=user_id, event_type="card_added"
    )
    # Evento de otro workspace: no debe aparecer.
    await recorder.execute(
        supplier_id=other_supplier, user_id=user_id, event_type="column_created"
    )

    lister = ListKanbanEventsUseCase(event_repo=repo)
    result = await lister.execute(supplier_id=supplier_id)

    assert [e.id for e in result] == [segundo.id, primero.id]


# ---------------------------------------------------------------------------
# NotifyKanbanChangeUseCase
# ---------------------------------------------------------------------------


def _active_member(user_id: UUID, supplier_id: UUID, role: MemberRole = MemberRole.MEMBER) -> SupplierMember:
    return SupplierMember(
        user_id=user_id,
        supplier_id=supplier_id,
        role=role,
        status=MemberStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_notify_kanban_change_excluye_al_actor() -> None:
    member_repo = InMemorySupplierMemberRepository()
    pref_repo = InMemoryNotificationPreferenceRepository()
    notif_repo = InMemoryNotificationRepository()

    supplier_id = uuid4()
    actor = uuid4()
    otro = uuid4()
    await member_repo.add(_active_member(actor, supplier_id))
    await member_repo.add(_active_member(otro, supplier_id))

    # Ambos activaron las notifs del tablero.
    await pref_repo.save(
        NotificationPreference(user_id=actor, kanban_notifications_enabled=True)
    )
    await pref_repo.save(
        NotificationPreference(user_id=otro, kanban_notifications_enabled=True)
    )

    use_case = NotifyKanbanChangeUseCase(member_repo, pref_repo, notif_repo)
    notifs = await use_case.execute(
        supplier_id=supplier_id, actor_user_id=actor, tender_id=uuid4()
    )

    assert len(notifs) == 1
    assert notifs[0].user_id == otro
    assert notifs[0].kind == "kanban_change"


@pytest.mark.asyncio
async def test_notify_kanban_change_respeta_toggle_apagado() -> None:
    member_repo = InMemorySupplierMemberRepository()
    pref_repo = InMemoryNotificationPreferenceRepository()
    notif_repo = InMemoryNotificationRepository()

    supplier_id = uuid4()
    actor = uuid4()
    con_toggle = uuid4()
    sin_toggle = uuid4()
    await member_repo.add(_active_member(actor, supplier_id))
    await member_repo.add(_active_member(con_toggle, supplier_id))
    await member_repo.add(_active_member(sin_toggle, supplier_id))

    await pref_repo.save(
        NotificationPreference(user_id=con_toggle, kanban_notifications_enabled=True)
    )
    await pref_repo.save(
        NotificationPreference(user_id=sin_toggle, kanban_notifications_enabled=False)
    )

    use_case = NotifyKanbanChangeUseCase(member_repo, pref_repo, notif_repo)
    notifs = await use_case.execute(
        supplier_id=supplier_id, actor_user_id=actor, tender_id=uuid4()
    )

    assert [n.user_id for n in notifs] == [con_toggle]


@pytest.mark.asyncio
async def test_notify_kanban_change_sin_destinatarios_devuelve_vacio() -> None:
    member_repo = InMemorySupplierMemberRepository()
    pref_repo = InMemoryNotificationPreferenceRepository()
    notif_repo = InMemoryNotificationRepository()

    supplier_id = uuid4()
    actor = uuid4()
    await member_repo.add(_active_member(actor, supplier_id))

    use_case = NotifyKanbanChangeUseCase(member_repo, pref_repo, notif_repo)
    notifs = await use_case.execute(
        supplier_id=supplier_id, actor_user_id=actor, tender_id=uuid4()
    )

    assert notifs == []


# ---------------------------------------------------------------------------
# SetWorkspaceMatchThresholdUseCase
# ---------------------------------------------------------------------------


def _supplier(user_id: UUID | None = None) -> Supplier:
    return Supplier(
        rut="76.086.428-5",
        legal_name="Empresa SpA",
        user_id=user_id,
    )


@pytest.mark.asyncio
async def test_set_match_threshold_requiere_admin() -> None:
    supplier_repo = InMemorySupplierRepository()
    member_repo = InMemorySupplierMemberRepository()

    supplier = _supplier()
    await supplier_repo.save(supplier)
    non_admin_user = uuid4()
    await member_repo.add(_active_member(non_admin_user, supplier.id))

    use_case = SetWorkspaceMatchThresholdUseCase(supplier_repo, member_repo)
    with pytest.raises(UnauthorizedWorkspaceAction):
        await use_case.execute(
            user_id=non_admin_user, supplier_id=supplier.id, threshold=0.8
        )


@pytest.mark.asyncio
async def test_set_match_threshold_persiste_para_admin() -> None:
    supplier_repo = InMemorySupplierRepository()
    member_repo = InMemorySupplierMemberRepository()

    supplier = _supplier()
    await supplier_repo.save(supplier)
    admin_user = uuid4()
    await member_repo.add(
        _active_member(admin_user, supplier.id, role=MemberRole.ADMIN)
    )

    use_case = SetWorkspaceMatchThresholdUseCase(supplier_repo, member_repo)
    updated = await use_case.execute(
        user_id=admin_user, supplier_id=supplier.id, threshold=0.85
    )

    assert updated.match_threshold == 0.85


@pytest.mark.asyncio
async def test_set_match_threshold_rechaza_fuera_de_rango() -> None:
    supplier_repo = InMemorySupplierRepository()
    member_repo = InMemorySupplierMemberRepository()

    supplier = _supplier()
    await supplier_repo.save(supplier)
    admin_user = uuid4()
    await member_repo.add(
        _active_member(admin_user, supplier.id, role=MemberRole.ADMIN)
    )

    use_case = SetWorkspaceMatchThresholdUseCase(supplier_repo, member_repo)
    with pytest.raises(ValidationError):
        await use_case.execute(
            user_id=admin_user, supplier_id=supplier.id, threshold=1.5
        )


@pytest.mark.asyncio
async def test_set_match_threshold_devuelve_a_none_restaura_fallback() -> None:
    supplier_repo = InMemorySupplierRepository()
    member_repo = InMemorySupplierMemberRepository()

    supplier = _supplier()
    supplier.match_threshold = 0.9
    await supplier_repo.save(supplier)
    admin_user = uuid4()
    await member_repo.add(
        _active_member(admin_user, supplier.id, role=MemberRole.ADMIN)
    )

    use_case = SetWorkspaceMatchThresholdUseCase(supplier_repo, member_repo)
    updated = await use_case.execute(
        user_id=admin_user, supplier_id=supplier.id, threshold=None
    )

    assert updated.match_threshold is None


@pytest.mark.asyncio
async def test_set_match_threshold_supplier_inexistente_levanta_not_found() -> None:
    supplier_repo = InMemorySupplierRepository()
    member_repo = InMemorySupplierMemberRepository()

    use_case = SetWorkspaceMatchThresholdUseCase(supplier_repo, member_repo)
    with pytest.raises(SupplierNotFound):
        await use_case.execute(
            user_id=uuid4(), supplier_id=uuid4(), threshold=0.5
        )
