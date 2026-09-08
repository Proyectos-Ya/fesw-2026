from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UserPublicSchema(BaseModel):
    """Vista pública del perfil local.

    `id` es el nuestro, no el `sub` de Supabase: es el que el frontend necesita
    para todo lo demás, porque es al que apuntan las claves foráneas.
    """

    id: UUID
    email: str
    full_name: str
    phone: str | None = None
    active: bool
    email_verified: bool
    created_at: datetime
