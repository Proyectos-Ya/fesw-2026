import re
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.shared.datetime_utils import UtcDateTime

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validate_hex_color(v: str | None) -> str | None:
    if v is not None and not _HEX_RE.fullmatch(v):
        raise ValueError("color debe ser un hex de 6 dígitos, ej. #A99A7C")
    return v


class KanbanColumnCreate(BaseModel):
    name: str
    position: int | None = None
    color: str | None = None

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        return _validate_hex_color(v)


class KanbanColumnUpdate(BaseModel):
    name: str | None = None
    position: int | None = None
    color: str | None = None

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        return _validate_hex_color(v)


class KanbanColumnResponse(BaseModel):
    id: UUID
    name: str
    position: int
    color: str
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
    board_entered_at: UtcDateTime
    archived_at: UtcDateTime | None = None
    archived_reason: str | None = None


class KanbanArchiveResponse(BaseModel):
    """Fila del panel de historial (HdU 10, CA4).

    Trae lo que el panel muestra: datos de la licitación, nombre de la
    última columna, cuándo entró, cuándo salió y la razón.
    """

    id: UUID
    tender_id: UUID
    tender_title: str | None = None
    tender_external_id: str | None = None
    column_id: UUID
    column_name: str | None = None
    board_entered_at: UtcDateTime
    archived_at: UtcDateTime
    archived_reason: str
