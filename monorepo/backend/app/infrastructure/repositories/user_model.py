from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel


class UserModel(SQLModel, table=True):
    # "users" en vez de "user" porque user es palabra reservada en PostgreSQL
    __tablename__ = "users"  # type: ignore
    id: UUID = Field(primary_key=True)
    # Sin unique: el correo dejó de ser la clave de identidad cuando pasó a
    # serlo `auth_provider_id`. Mantenerlo único abriría una clase de fallos
    # —cambio de correo en el proveedor, dos identidades con el mismo correo—
    # que se manifiestan como un 500 al crear el perfil.
    email: str = Field(index=True)
    auth_provider_id: str | None = Field(default=None, unique=True, index=True)
    hashed_password: str
    full_name: str
    phone: str | None = None
    active: bool = True
    email_verified: bool = False
    created_at: datetime
    updated_at: datetime
