"""Providers del tablero Kanban (HdU 10)."""

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
from app.application.use_cases.kanban.move_kanban_card import MoveKanbanCardUseCase
from app.application.use_cases.kanban.remove_tender_from_board import (
    RemoveTenderFromBoardUseCase,
)
from app.application.use_cases.kanban.restore_tender import RestoreTenderUseCase
from app.application.use_cases.kanban.reorder_kanban_columns import (
    ReorderKanbanColumnsUseCase,
)
from app.application.use_cases.kanban.update_kanban_column import (
    UpdateKanbanColumnUseCase,
)
from app.bootstrap.repositories import KanbanCardRepoDep, KanbanColumnRepoDep


def get_list_kanban_columns_use_case(
    column_repo: KanbanColumnRepoDep,
) -> ListKanbanColumnsUseCase:
    return ListKanbanColumnsUseCase(column_repo=column_repo)


def get_create_kanban_column_use_case(
    column_repo: KanbanColumnRepoDep,
) -> CreateKanbanColumnUseCase:
    return CreateKanbanColumnUseCase(column_repo=column_repo)


def get_update_kanban_column_use_case(
    column_repo: KanbanColumnRepoDep,
) -> UpdateKanbanColumnUseCase:
    return UpdateKanbanColumnUseCase(column_repo=column_repo)


def get_delete_kanban_column_use_case(
    column_repo: KanbanColumnRepoDep,
) -> DeleteKanbanColumnUseCase:
    return DeleteKanbanColumnUseCase(column_repo=column_repo)


def get_list_kanban_cards_use_case(card_repo: KanbanCardRepoDep) -> ListKanbanCardsUseCase:
    return ListKanbanCardsUseCase(card_repo=card_repo)


def get_add_tender_to_board_use_case(
    card_repo: KanbanCardRepoDep,
    column_repo: KanbanColumnRepoDep,
) -> AddTenderToBoardUseCase:
    return AddTenderToBoardUseCase(card_repo=card_repo, column_repo=column_repo)


def get_move_kanban_card_use_case(
    card_repo: KanbanCardRepoDep,
    column_repo: KanbanColumnRepoDep,
) -> MoveKanbanCardUseCase:
    return MoveKanbanCardUseCase(card_repo=card_repo, column_repo=column_repo)


def get_remove_tender_from_board_use_case(
    card_repo: KanbanCardRepoDep,
) -> RemoveTenderFromBoardUseCase:
    return RemoveTenderFromBoardUseCase(card_repo=card_repo)


def get_archive_tender_from_board_use_case(
    card_repo: KanbanCardRepoDep,
) -> ArchiveTenderFromBoardUseCase:
    return ArchiveTenderFromBoardUseCase(card_repo=card_repo)


def get_list_archived_tenders_use_case(
    card_repo: KanbanCardRepoDep,
) -> ListArchivedTendersUseCase:
    return ListArchivedTendersUseCase(card_repo=card_repo)


def get_restore_tender_use_case(card_repo: KanbanCardRepoDep) -> RestoreTenderUseCase:
    return RestoreTenderUseCase(card_repo=card_repo)
def get_reorder_kanban_columns_use_case(
    column_repo: KanbanColumnRepoDep,
) -> ReorderKanbanColumnsUseCase:
    return ReorderKanbanColumnsUseCase(column_repo=column_repo)
