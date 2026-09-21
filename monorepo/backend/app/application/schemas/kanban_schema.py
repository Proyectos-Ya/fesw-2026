from uuid import UUID

from pydantic import BaseModel

from app.shared.datetime_utils import UtcDateTime


class KanbanColumnCreate(BaseModel):
    name: str
    position: int | None = None


class KanbanColumnUpdate(BaseModel):
    name: str | None = None
    position: int | None = None


class KanbanColumnResponse(BaseModel):
    id: UUID
    name: str
    position: int
    card_count: int
    created_at: UtcDateTime


class KanbanCardCreate(BaseModel):
    tender_id: UUID
    column_id: UUID
    position: int | None = None


class KanbanCardMove(BaseModel):
    column_id: UUID | None = None
    position: int | None = None


class KanbanCardResponse(BaseModel):
    id: UUID
    tender_id: UUID
    column_id: UUID
    position: int
    created_at: UtcDateTime
    updated_at: UtcDateTime

