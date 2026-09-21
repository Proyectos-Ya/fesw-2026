from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.schemas.kanban_schema import (
    KanbanColumnUpdate,
    KanbanColumnResponse,
    KanbanColumnCreate,
    KanbanCardResponse,
    KanbanCardMove,
    KanbanCardCreate,
)
from app.application.use_cases.kanban.add_tender_to_board import AddTenderToBoardUseCase
from app.application.use_cases.kanban.create_kanban_column import CreateKanbanColumnUseCase
from app.application.use_cases.kanban.delete_kanban_column import DeleteKanbanColumnUseCase
from app.application.use_cases.kanban.list_kanban_cards import ListKanbanCardsUseCase
from app.application.use_cases.kanban.list_kanban_columns import ListKanbanColumnsUseCase
from app.application.use_cases.kanban.move_kanban_card import MoveKanbanCardUseCase
from app.application.use_cases.kanban.remove_tender_from_board import RemoveTenderFromBoardUseCase
from app.application.use_cases.kanban.update_kanban_column import UpdateKanbanColumnUseCase

from app.domain.entities.user import User
from app.domain.errors.kanban_errors import (
    KanbanCardNotFound,
    KanbanColumnNotFound,
    TenderAlreadyOnBoard,
)

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
) -> APIRouter:
    router = APIRouter(
        prefix="/kanban",
        tags=["Kanban"],
        dependencies=[Depends(get_current_user)],
    )

    @router.get("/columns", response_model=list[KanbanColumnResponse])
    async def list_columns(
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[ListKanbanColumnsUseCase, Depends(get_list_kanban_columns_use_case)],
    ):
        return await use_case.execute(user_id=current_user.id)

    @router.post("/columns", response_model=KanbanColumnResponse, status_code=status.HTTP_201_CREATED)
    async def create_column(
        body: KanbanColumnCreate,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[CreateKanbanColumnUseCase, Depends(get_create_kanban_column_use_case)],
    ):
        column = await use_case.execute(
            user_id=current_user.id, name=body.name, position=body.position
        )
        return KanbanColumnResponse(
            id=column.id,
            name=column.name,
            position=column.position,
            card_count=0,
            created_at=column.created_at,
        )

    @router.patch(
        "/columns/{column_id}",
        response_model=KanbanColumnResponse,
        responses={404: {"description": "Columna no encontrada"}},
    )
    async def update_column(
        column_id: UUID,
        body: KanbanColumnUpdate,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[UpdateKanbanColumnUseCase, Depends(get_update_kanban_column_use_case)],
        list_use_case: Annotated[ListKanbanColumnsUseCase, Depends(get_list_kanban_columns_use_case)],
    ):
        try:
            await use_case.execute(
                column_id=column_id,
                user_id=current_user.id,
                name=body.name,
                position=body.position,
            )
        except KanbanColumnNotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        columns = await list_use_case.execute(user_id=current_user.id)
        return next(c for c in columns if c.id == column_id)

    @router.delete(
        "/columns/{column_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={404: {"description": "Columna no encontrada"}},
    )
    async def delete_column(
        column_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[DeleteKanbanColumnUseCase, Depends(get_delete_kanban_column_use_case)],
    ):
        try:
            await use_case.execute(column_id=column_id, user_id=current_user.id)
        except KanbanColumnNotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    @router.get("/cards", response_model=list[KanbanCardResponse])
    async def list_cards(
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[ListKanbanCardsUseCase, Depends(get_list_kanban_cards_use_case)],
    ):
        return await use_case.execute(user_id=current_user.id)

    @router.post(
        "/cards",
        response_model=KanbanCardResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            404: {"description": "Columna no encontrada"},
            409: {"description": "La licitación ya está en el tablero"},
        },
    )
    async def add_card(
        body: KanbanCardCreate,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[AddTenderToBoardUseCase, Depends(get_add_tender_to_board_use_case)],
    ):
        try:
            return await use_case.execute(
                user_id=current_user.id,
                tender_id=body.tender_id,
                column_id=body.column_id,
                position=body.position,
            )
        except KanbanColumnNotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        except TenderAlreadyOnBoard as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    @router.patch(
        "/cards/{tender_id}",
        response_model=KanbanCardResponse,
        responses={
            404: {"description": "Tarjeta o columna no encontrada"},
        },
    )
    async def move_card(
        tender_id: UUID,
        body: KanbanCardMove,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[MoveKanbanCardUseCase, Depends(get_move_kanban_card_use_case)],
    ):
        try:
            return await use_case.execute(
                user_id=current_user.id,
                tender_id=tender_id,
                column_id=body.column_id,
                position=body.position,
            )
        except KanbanCardNotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        except KanbanColumnNotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    @router.delete(
        "/cards/{tender_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={404: {"description": "La licitación no está en el tablero"}},
    )
    async def remove_card(
        tender_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[RemoveTenderFromBoardUseCase, Depends(get_remove_tender_from_board_use_case)],
    ):
        try:
            await use_case.execute(user_id=current_user.id, tender_id=tender_id)
        except KanbanCardNotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return router