"""Entidad del historial del tablero kanban por workspace (HU-18).

Cada mutación de columnas o tarjetas genera un `KanbanEvent` que queda en
`kanban_event`. La tabla es append-only: la UI solo lee, nunca borra. El
`tender_title` se desnormaliza para que el panel de historial no necesite
joinear con `tender` ni dependa de que la licitación siga existiendo.

El evento se escribe sincrónicamente dentro del mismo caso de uso que
dispara la mutación: si falla el evento, falla la operación entera. La
notificación a otros miembros, en cambio, se emite en `BackgroundTasks` y
no bloquea.
"""

from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime, utc_now_naive

KanbanEventType = Literal[
    "column_created",
    "column_renamed",
    "column_recolored",
    "column_reordered",
    "column_deleted",
    "card_added",
    "card_moved",
    "card_archived",
    "card_restored",
    "card_removed",
]

KanbanEntityType = Literal["column", "card"]


class KanbanEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    supplier_id: UUID
    user_id: UUID
    event_type: KanbanEventType
    entity_type: KanbanEntityType | None = None
    entity_id: UUID | None = None
    tender_id: UUID | None = None
    tender_title: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
