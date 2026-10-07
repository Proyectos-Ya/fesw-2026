from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime, utc_now_naive

DEFAULT_COLUMNS = ["Por revisar", "En revisión", "Postulando", "Descartada"]

DEFAULT_COLUMN_COLORS = [
    "#A99A7C",  # Por revisar
    "#BF6E4A",  # En revisión
    "#5C7A52",  # Postulando
    "#35645B",  # Descartada
    "#E08E2B",  # columna 5
    "#A65A2E",  # columna 6
    "#244024",  # columna 7
]


class KanbanColumn(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    name: str
    position: int
    color: str = DEFAULT_COLUMN_COLORS[0]
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)


ARCHIVE_REASON_MANUAL = "manual"
ARCHIVE_REASON_AUTO = "auto_3m"


class KanbanCard(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    tender_id: UUID
    column_id: UUID
    position: int
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)
    # Archivado (HdU 10, CA4). `board_entered_at` se setea una vez al crear la
    # tarjeta y no cambia al moverla entre columnas; es la referencia para el
    # auto-archivado a los 90 días.
    board_entered_at: UtcDateTime = Field(default_factory=utc_now_naive)
    archived_at: UtcDateTime | None = None
    archived_reason: str | None = None
