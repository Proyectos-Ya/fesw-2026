from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RegisterSchema(BaseModel):
    email: str = Field(max_length=255)
    # bcrypt trunca a 72 bytes; acotamos el largo para evitar sorpresas silenciosas.
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(max_length=255)
    phone: str | None = Field(default=None, max_length=20)


class LoginSchema(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=72)


class TokenSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPublicSchema(BaseModel):
    """Vista pública del usuario — nunca expone el hash de la contraseña."""

    id: UUID
    email: str
    full_name: str
    phone: str | None = None
    active: bool
    email_verified: bool
    created_at: datetime
