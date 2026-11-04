"""Schemas HTTP para el historial del tablero kanban (HU-18)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class KanbanEventResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    user_id: UUID
    user_name: str | None = None
    event_type: str
    entity_type: str | None = None
    entity_id: UUID | None = None
    tender_id: UUID | None = None
    tender_title: str | None = None
    details: dict[str, Any]
    created_at: datetime
