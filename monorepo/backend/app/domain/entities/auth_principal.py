from pydantic import BaseModel, ConfigDict, field_validator


class AuthPrincipal(BaseModel):
    """Identidad que un emisor de confianza afirma sobre quien hace la petición.

    Es deliberadamente independiente de Supabase: describe *qué* se sabe de
    quien llama, no *cómo* llegó esa información. El mapeo desde los claims de
    un JWT concreto vive en infraestructura, así que cambiar de proveedor de
    identidad —o sumar un segundo— no toca esta entidad ni a quien la consume.

    No es un `User`: no tiene id propio ni existe en nuestra base. Es lo que
    permite decidir a qué usuario corresponde, y crearlo si es la primera vez.
    """

    model_config = ConfigDict(frozen=True)

    # Identificador estable del usuario en el proveedor. Por OIDC es una cadena
    # opaca: no se asume que sea un UUID aunque hoy Supabase emita uno.
    subject: str
    email: str
    full_name: str
    email_verified: bool = False
    # Con qué inició sesión: "google", "email", etc. Informativo.
    provider: str | None = None

    @field_validator("email")
    @classmethod
    def _normalizar_email(cls, value: str) -> str:
        """Mismo criterio que la entidad User, para que ambos lados coincidan."""
        return value.strip().lower()
