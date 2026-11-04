"""Router del tablero Kanban (HdU 10 + HU-18).

HU-18: todos los endpoints operan a nivel de workspace. El `supplier_id` se
toma de `WorkspaceContext.active_supplier_id`; si no hay workspace activo,
el request retorna 403 (el usuario tiene que elegir uno antes).

Las mutaciones encolan `notify_kanban_change` como BackgroundTask: la
notificación es informativa y no debe bloquear la respuesta.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.application.schemas.kanban_schema import (
    KanbanArchiveResponse,
    KanbanCardCreate,
    KanbanCardMove,
    KanbanCardResponse,
    KanbanColumnCreate,
    KanbanColumnResponse,
    KanbanColumnUpdate,
    ReorderColumnsRequest,
)
from app.application.schemas.kanban_event_schema import KanbanEventResponse
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
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.entities.user import User
from app.domain.errors.kanban_errors import (
    ArchiveNotRestorable,
    KanbanCardNotFound,
    KanbanColumnNotFound,
    TenderAlreadyOnBoard,
)


def _require_workspace(context: WorkspaceContext | None) -> UUID:
    """Rechaza con 403 si el usuario no tiene un workspace activo.

    El tablero kanban no existe fuera de un workspace: sin contexto no hay
    nada que listar ni dónde escribir.
    """
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes seleccionar un workspace activo para usar el tablero.",
        )
    return context.active_supplier_id


def create_kanban_router(
    get_current_user: Callable,
    get_list_kanban_columns_use_case: Callable,
    get_create_kanban_column_use_case: Callable,
    get_update_kanban_column_use_case: Callable,
    get_delete_kanban_column_use_case: Callable,
    get_list_kanban_cards_use_case: Callable,
    get_add_tender_to_board_use_case: Callable,
    get_move_kanban_card_use_case: Callable,
    get_remove_tender_from_board_use_case: Callable,
    get_archive_tender_from_board_use_case: Callable,
    get_list_archived_tenders_use_case: Callable,
    get_restore_tender_use_case: Callable,
    get_reorder_kanban_columns_use_case: Callable,
    get_list_kanban_events_use_case: Callable,
    get_notify_kanban_change_use_case: Callable,
    get_current_workspace_context: Callable | None = None,
) -> APIRouter:
    workspace_context_dep = get_current_workspace_context or (lambda: None)

    router = APIRouter(
        prefix="/kanban",
        tags=["Kanban"],
        dependencies=[Depends(get_current_user)],
    )

    def _schedule_notify(
        background_tasks: BackgroundTasks,
        notify_use_case: NotifyKanbanChangeUseCase,
        supplier_id: UUID,
        actor_user_id: UUID,
        tender_id: UUID | None,
    ) -> None:
        async def _run() -> None:
            try:
                await notify_use_case.execute(
                    supplier_id=supplier_id,
                    actor_user_id=actor_user_id,
                    tender_id=tender_id,
                )
            except Exception:
                # Si falla el aviso, la mutación ya está confirmada; se
                # ignora para no colgar el worker. La captura explícita evita
                # que BackgroundTasks dropee la excepción silenciosamente en
                # un stack ajeno.
                pass

        background_tasks.add_task(_run)

    @router.get(
        "/columns",
        response_model=list[KanbanColumnResponse],
        summary="Lista las columnas del tablero del workspace",
    )
    async def list_columns(
        current_user: Annotated[User, Depends(get_current_user)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
        use_case: Annotated[
            ListKanbanColumnsUseCase, Depends(get_list_kanban_columns_use_case)
        ],
    ):
        supplier_id = _require_workspace(workspace_context)
        return await use_case.execute(
            supplier_id=supplier_id, user_id=current_user.id
        )

    @router.post(
        "/columns",
        response_model=KanbanColumnResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Crea una columna nueva en el tablero del workspace",
    )
    async def create_column(
        body: KanbanColumnCreate,
        background_tasks: BackgroundTasks,
        current_user: Annotated[User, Depends(get_current_user)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
        use_case: Annotated[
            CreateKanbanColumnUseCase, Depends(get_create_kanban_column_use_case)
        ],
        notify_use_case: Annotated[
            NotifyKanbanChangeUseCase, Depends(get_notify_kanban_change_use_case)
        ],
    ):
        supplier_id = _require_workspace(workspace_context)
        column = await use_case.execute(
            supplier_id=supplier_id,
            user_id=current_user.id,
            name=body.name,
            position=body.position,
            color=body.color,
        )
        _schedule_notify(
            background_tasks, notify_use_case, supplier_id, current_user.id, None
        )
        return KanbanColumnResponse(
            id=column.id,
            name=column.name,
            position=column.position,
            color=column.color,
            card_count=0,
            created_at=column.created_at,
        )

    @router.patch(
        "/columns/reorder",
        response_model=list[KanbanColumnResponse],
        summary="Reordena las columnas del tablero del workspace",
        responses={
            400: {"description": "Lista inválida (incompleta o con duplicados)"},
            403: {"description": "Sin workspace activo"},
            404: {"description": "Alguna columna no pertenece al workspace"},
        },
    )
    async def reorder_columns(
        body: ReorderColumnsRequest,
        background_tasks: BackgroundTasks,
        current_user: Annotated[User, Depends(get_current_user)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
        use_case: Annotated[
            ReorderKanbanColumnsUseCase, Depends(get_reorder_kanban_columns_use_case)
        ],
        list_use_case: Annotated[
            ListKanbanColumnsUseCase, Depends(get_list_kanban_columns_use_case)
        ],
        notify_use_case: Annotated[
            NotifyKanbanChangeUseCase, Depends(get_notify_kanban_change_use_case)
        ],
    ):
        supplier_id = _require_workspace(workspace_context)
        try:
            await use_case.execute(
                supplier_id=supplier_id,
                user_id=current_user.id,
                column_ids=body.column_ids,
            )
        except KanbanColumnNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        _schedule_notify(
            background_tasks, notify_use_case, supplier_id, current_user.id, None
        )
        return await list_use_case.execute(
            supplier_id=supplier_id, user_id=current_user.id
        )

    @router.patch(
        "/columns/{column_id}",
        response_model=KanbanColumnResponse,
        summary="Actualiza una columna del tablero",
        responses={404: {"description": "Columna no encontrada"}},
    )
    async def update_column(
        column_id: UUID,
        body: KanbanColumnUpdate,
        background_tasks: BackgroundTasks,
        current_user: Annotated[User, Depends(get_current_user)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
        use_case: Annotated[
            UpdateKanbanColumnUseCase, Depends(get_update_kanban_column_use_case)
        ],
        list_use_case: Annotated[
            ListKanbanColumnsUseCase, Depends(get_list_kanban_columns_use_case)
        ],
        notify_use_case: Annotated[
            NotifyKanbanChangeUseCase, Depends(get_notify_kanban_change_use_case)
        ],
    ):
        supplier_id = _require_workspace(workspace_context)
        try:
            await use_case.execute(
                column_id=column_id,
                supplier_id=supplier_id,
                user_id=current_user.id,
                name=body.name,
                position=body.position,
                color=body.color,
            )
        except KanbanColumnNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        _schedule_notify(
            background_tasks, notify_use_case, supplier_id, current_user.id, None
        )
        columns = await list_use_case.execute(
            supplier_id=supplier_id, user_id=current_user.id
        )
        return next(c for c in columns if c.id == column_id)

    @router.delete(
        "/columns/{column_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Elimina una columna del tablero",
        responses={404: {"description": "Columna no encontrada"}},
    )
    async def delete_column(
        column_id: UUID,
        background_tasks: BackgroundTasks,
        current_user: Annotated[User, Depends(get_current_user)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
        use_case: Annotated[
            DeleteKanbanColumnUseCase, Depends(get_delete_kanban_column_use_case)
        ],
        notify_use_case: Annotated[
            NotifyKanbanChangeUseCase, Depends(get_notify_kanban_change_use_case)
        ],
    ):
        supplier_id = _require_workspace(workspace_context)
        try:
            await use_case.execute(
                column_id=column_id,
                supplier_id=supplier_id,
                user_id=current_user.id,
            )
        except KanbanColumnNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        _schedule_notify(
            background_tasks, notify_use_case, supplier_id, current_user.id, None
        )

    @router.get(
        "/cards",
        response_model=list[KanbanCardResponse],
        summary="Lista las tarjetas activas del tablero del workspace",
    )
    async def list_cards(
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
        use_case: Annotated[
            ListKanbanCardsUseCase, Depends(get_list_kanban_cards_use_case)
        ],
    ):
        supplier_id = _require_workspace(workspace_context)
        return await use_case.execute(supplier_id=supplier_id)

    @router.post(
        "/cards",
        response_model=KanbanCardResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Agrega una licitación al tablero del workspace",
        responses={
            404: {"description": "Columna no encontrada"},
            409: {"description": "La licitación ya está en el tablero del workspace"},
        },
    )
    async def add_card(
        body: KanbanCardCreate,
        background_tasks: BackgroundTasks,
        current_user: Annotated[User, Depends(get_current_user)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
        use_case: Annotated[
            AddTenderToBoardUseCase, Depends(get_add_tender_to_board_use_case)
        ],
        notify_use_case: Annotated[
            NotifyKanbanChangeUseCase, Depends(get_notify_kanban_change_use_case)
        ],
    ):
        supplier_id = _require_workspace(workspace_context)
        try:
            card = await use_case.execute(
                supplier_id=supplier_id,
                user_id=current_user.id,
                tender_id=body.tender_id,
                column_id=body.column_id,
                position=body.position,
            )
        except KanbanColumnNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except TenderAlreadyOnBoard as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        _schedule_notify(
            background_tasks,
            notify_use_case,
            supplier_id,
            current_user.id,
            body.tender_id,
        )
        return card

    @router.patch(
        "/cards/{tender_id}",
        response_model=KanbanCardResponse,
        summary="Mueve o reposiciona una tarjeta",
        responses={404: {"description": "Tarjeta o columna no encontrada"}},
    )
    async def move_card(
        tender_id: UUID,
        body: KanbanCardMove,
        background_tasks: BackgroundTasks,
        current_user: Annotated[User, Depends(get_current_user)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
        use_case: Annotated[
            MoveKanbanCardUseCase, Depends(get_move_kanban_card_use_case)
        ],
        notify_use_case: Annotated[
            NotifyKanbanChangeUseCase, Depends(get_notify_kanban_change_use_case)
        ],
    ):
        supplier_id = _require_workspace(workspace_context)
        try:
            card = await use_case.execute(
                supplier_id=supplier_id,
                user_id=current_user.id,
                tender_id=tender_id,
                column_id=body.column_id,
                position=body.position,
            )
        except KanbanCardNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except KanbanColumnNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        _schedule_notify(
            background_tasks,
            notify_use_case,
            supplier_id,
            current_user.id,
            tender_id,
        )
        return card

    @router.delete(
        "/cards/{tender_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Elimina una tarjeta activa del tablero",
        responses={404: {"description": "La licitación no está en el tablero"}},
    )
    async def remove_card(
        tender_id: UUID,
        background_tasks: BackgroundTasks,
        current_user: Annotated[User, Depends(get_current_user)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
        use_case: Annotated[
            RemoveTenderFromBoardUseCase,
            Depends(get_remove_tender_from_board_use_case),
        ],
        notify_use_case: Annotated[
            NotifyKanbanChangeUseCase, Depends(get_notify_kanban_change_use_case)
        ],
    ):
        supplier_id = _require_workspace(workspace_context)
        try:
            await use_case.execute(
                supplier_id=supplier_id,
                user_id=current_user.id,
                tender_id=tender_id,
            )
        except KanbanCardNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        _schedule_notify(
            background_tasks,
            notify_use_case,
            supplier_id,
            current_user.id,
            tender_id,
        )

    @router.post(
        "/cards/{card_id}/archive",
        response_model=KanbanCardResponse,
        summary="Archivar una tarjeta del tablero (soft-delete)",
        responses={404: {"description": "La tarjeta no existe"}},
    )
    async def archive_card(
        card_id: UUID,
        background_tasks: BackgroundTasks,
        current_user: Annotated[User, Depends(get_current_user)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
        use_case: Annotated[
            ArchiveTenderFromBoardUseCase,
            Depends(get_archive_tender_from_board_use_case),
        ],
        notify_use_case: Annotated[
            NotifyKanbanChangeUseCase, Depends(get_notify_kanban_change_use_case)
        ],
    ):
        """Archiva manualmente una tarjeta del tablero del workspace.

        La tarjeta deja de aparecer en el tablero activo y pasa al historial.
        Se puede restaurar mientras la razón sea 'manual' (CA4).
        """
        supplier_id = _require_workspace(workspace_context)
        try:
            card = await use_case.execute(
                supplier_id=supplier_id,
                user_id=current_user.id,
                card_id=card_id,
            )
        except KanbanCardNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        _schedule_notify(
            background_tasks,
            notify_use_case,
            supplier_id,
            current_user.id,
            card.tender_id,
        )
        return card

    @router.get(
        "/archive",
        response_model=list[KanbanArchiveResponse],
        summary="Historial de tarjetas archivadas del workspace",
    )
    async def list_archive(
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
        use_case: Annotated[
            ListArchivedTendersUseCase,
            Depends(get_list_archived_tenders_use_case),
        ],
    ):
        supplier_id = _require_workspace(workspace_context)
        return await use_case.execute(supplier_id=supplier_id)

    @router.post(
        "/archive/{card_id}/restore",
        response_model=KanbanCardResponse,
        summary="Restaurar al tablero una tarjeta archivada manualmente",
        responses={
            404: {"description": "La tarjeta no existe"},
            409: {
                "description": (
                    "La tarjeta fue archivada automáticamente y no se puede restaurar"
                )
            },
        },
    )
    async def restore_card(
        card_id: UUID,
        background_tasks: BackgroundTasks,
        current_user: Annotated[User, Depends(get_current_user)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
        use_case: Annotated[RestoreTenderUseCase, Depends(get_restore_tender_use_case)],
        notify_use_case: Annotated[
            NotifyKanbanChangeUseCase, Depends(get_notify_kanban_change_use_case)
        ],
    ):
        supplier_id = _require_workspace(workspace_context)
        try:
            card = await use_case.execute(
                supplier_id=supplier_id,
                user_id=current_user.id,
                card_id=card_id,
            )
        except KanbanCardNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except ArchiveNotRestorable as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        _schedule_notify(
            background_tasks,
            notify_use_case,
            supplier_id,
            current_user.id,
            card.tender_id,
        )
        return card

    @router.get(
        "/events",
        response_model=list[KanbanEventResponse],
        summary="Historial de eventos del tablero del workspace (HU-18)",
    )
    async def list_events(
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
        use_case: Annotated[
            ListKanbanEventsUseCase, Depends(get_list_kanban_events_use_case)
        ],
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        supplier_id = _require_workspace(workspace_context)
        events = await use_case.execute(
            supplier_id=supplier_id, limit=limit, offset=offset
        )
        return [
            KanbanEventResponse(
                id=e.id,
                supplier_id=e.supplier_id,
                user_id=e.user_id,
                event_type=e.event_type,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                tender_id=e.tender_id,
                tender_title=e.tender_title,
                details=e.details,
                created_at=e.created_at,
            )
            for e in events
        ]

    return router
