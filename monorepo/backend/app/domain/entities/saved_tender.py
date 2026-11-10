from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime, utc_now_naive


class SavedTender(BaseModel):
    """Marca de interés sobre una licitación a nivel de workspace (HU-18).

    Antes era personal (`user_id`); desde HU-18 todos los miembros del mismo
    workspace comparten la misma lista. `user_id` queda como auditoría de
    quién la guardó primero.
    """

    id: UUID = Field(default_factory=uuid4)
    supplier_id: UUID  # Workspace propietario de la marca
    user_id: UUID  # Miembro que la guardó (auditoría, no propiedad)
    tender_id: UUID  # ID de la licitación marcada como de interés
    saved_at: UtcDateTime = Field(default_factory=utc_now_naive)  # Fecha del guardado
