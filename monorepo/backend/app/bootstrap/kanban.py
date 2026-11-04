"""Providers del tablero Kanban (HdU 10 + HU-18).

HU-18: cada use case de mutación recibe también un `IKanbanEventRepository`
para dejar registro en el historial del workspace.
"""

from app.application.use_cases.kanban.add_tender_to_board import AddTenderToBoardUseCase
from app.application.use_cases.kanban.archive_tender_from_board import (
    ArchiveTenderFromBoardUseCase,
)
from app.application.use_cases.kanban.create_kanban_column import (
    CreateKanbanColumnUseCase,
)
from app.application.use_cases.kanban.delete_kanban_column import (
    DeleteKanbanColumnUseCase,
)
from app.application.use_cases.kanban.list_archived_tenders import (
    ListArchivedTendersUseCase,
)
from app.application.use_cases.kanban.list_kanban_cards import ListKanbanCardsUseCase
from app.application.use_cases.kanban.list_kanban_columns import (
    ListKanbanColumnsUseCase,
)
from app.application.use_cases.kanban.list_kanban_events import (
    ListKanbanEventsUseCase,
)
from app.application.use_cases.kanban.move_kanban_card import MoveKanbanCardUseCase
from app.application.use_cases.kanban.notify_kanban_change import (
    NotifyKanbanChangeUseCase,
)
from app.application.use_cases.kanban.remove_tender_from_board import (
    RemoveTenderFromBoardUseCase,
)
from app.application.use_cases.kanban.reorder_kanban_columns import (
    ReorderKanbanColumnsUseCase,
)
from app.application.use_cases.kanban.restore_tender import RestoreTenderUseCase
from app.application.use_cases.kanban.update_kanban_column import (
    UpdateKanbanColumnUseCase,
)
from app.bootstrap.repositories import (
    KanbanCardRepoDep,
    KanbanColumnRepoDep,
    KanbanEventRepoDep,
    NotificationPreferenceRepoDep,
    NotificationRepoDep,
    SupplierMemberRepoDep,
)


def get_list_kanban_columns_use_case(
    column_repo: KanbanColumnRepoDep,
) -> ListKanbanColumnsUseCase:
    return ListKanbanColumnsUseCase(column_repo=column_repo)


def get_create_kanban_column_use_case(
    column_repo: KanbanColumnRepoDep,
    event_repo: KanbanEventRepoDep,
) -> CreateKanbanColumnUseCase:
    return CreateKanbanColumnUseCase(column_repo=column_repo, event_repo=event_repo)


def get_update_kanban_column_use_case(
    column_repo: KanbanColumnRepoDep,
    event_repo: KanbanEventRepoDep,
) -> UpdateKanbanColumnUseCase:
    return UpdateKanbanColumnUseCase(column_repo=column_repo, event_repo=event_repo)


def get_delete_kanban_column_use_case(
    column_repo: KanbanColumnRepoDep,
    event_repo: KanbanEventRepoDep,
) -> DeleteKanbanColumnUseCase:
    return DeleteKanbanColumnUseCase(column_repo=column_repo, event_repo=event_repo)


def get_list_kanban_cards_use_case(card_repo: KanbanCardRepoDep) -> ListKanbanCardsUseCase:
    return ListKanbanCardsUseCase(card_repo=card_repo)


def get_add_tender_to_board_use_case(
    card_repo: KanbanCardRepoDep,
    column_repo: KanbanColumnRepoDep,
    event_repo: KanbanEventRepoDep,
) -> AddTenderToBoardUseCase:
    return AddTenderToBoardUseCase(
        card_repo=card_repo, column_repo=column_repo, event_repo=event_repo
    )


def get_move_kanban_card_use_case(
    card_repo: KanbanCardRepoDep,
    column_repo: KanbanColumnRepoDep,
    event_repo: KanbanEventRepoDep,
) -> MoveKanbanCardUseCase:
    return MoveKanbanCardUseCase(
        card_repo=card_repo, column_repo=column_repo, event_repo=event_repo
    )


def get_remove_tender_from_board_use_case(
    card_repo: KanbanCardRepoDep,
    event_repo: KanbanEventRepoDep,
) -> RemoveTenderFromBoardUseCase:
    return RemoveTenderFromBoardUseCase(card_repo=card_repo, event_repo=event_repo)


def get_archive_tender_from_board_use_case(
    card_repo: KanbanCardRepoDep,
    event_repo: KanbanEventRepoDep,
) -> ArchiveTenderFromBoardUseCase:
    return ArchiveTenderFromBoardUseCase(card_repo=card_repo, event_repo=event_repo)


def get_list_archived_tenders_use_case(
    card_repo: KanbanCardRepoDep,
) -> ListArchivedTendersUseCase:
    return ListArchivedTendersUseCase(card_repo=card_repo)


def get_restore_tender_use_case(
    card_repo: KanbanCardRepoDep,
    event_repo: KanbanEventRepoDep,
) -> RestoreTenderUseCase:
    return RestoreTenderUseCase(card_repo=card_repo, event_repo=event_repo)


def get_reorder_kanban_columns_use_case(
    column_repo: KanbanColumnRepoDep,
    event_repo: KanbanEventRepoDep,
) -> ReorderKanbanColumnsUseCase:
    return ReorderKanbanColumnsUseCase(
        column_repo=column_repo, event_repo=event_repo
    )


def get_list_kanban_events_use_case(
    event_repo: KanbanEventRepoDep,
) -> ListKanbanEventsUseCase:
    return ListKanbanEventsUseCase(event_repo=event_repo)


def get_notify_kanban_change_use_case(
    member_repo: SupplierMemberRepoDep,
    preference_repo: NotificationPreferenceRepoDep,
    notification_repo: NotificationRepoDep,
) -> NotifyKanbanChangeUseCase:
    return NotifyKanbanChangeUseCase(
        member_repo=member_repo,
        preference_repo=preference_repo,
        notification_repo=notification_repo,
    )
