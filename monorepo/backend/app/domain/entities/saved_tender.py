from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime, utc_now_naive


class SavedTender(BaseModel):
    """Representa la marca de interés de un usuario sobre una licitación."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID  # ID del usuario que guardó la licitación
    tender_id: UUID  # ID de la licitación marcada como de interés
    saved_at: UtcDateTime = Field(default_factory=utc_now_naive)  # Fecha del guardado
