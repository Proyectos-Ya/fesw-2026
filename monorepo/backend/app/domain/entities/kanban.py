from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime, utc_now_naive


class KanbanColumn(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    name: str
    position: int
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)


class KanbanCard(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    tender_id: UUID
    column_id: UUID
    position: int
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)

