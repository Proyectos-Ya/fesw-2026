from pydantic import BaseModel, ConfigDict, field_validator


class AuthPrincipal(BaseModel):
    """Identidad que un emisor de confianza afirma sobre quien hace la petición.

    Es deliberadamente independiente de Supabase: describe *qué* se sabe de
    quien llama, no *cómo* llegó esa información. El mapeo desde los claims de
    un JWT concreto vive en infraestructura, así que cambiar de proveedor de
    identidad —o sumar un segundo— no toca esta entidad ni a quien la consume.

    No es un `User`: no tiene id propio ni existe en nuestra base. Es lo que
    permite decidir a qué usuario corresponde, y crearlo si es la primera vez.

    **No lleva si el correo está verificado, y es a propósito.** El token de
    Supabase no trae un claim `email_verified` de primer nivel: el dato solo
    aparece dentro de `user_metadata`, que el propio usuario puede escribir con
    `supabase.auth.updateUser({ data: ... })`. Leerlo de ahí sería dejar que
    cualquiera se declare verificado. La fuente de verdad es
    `auth.users.email_confirmed_at`, y se consulta por `IIdentityDirectory`.
    """

    model_config = ConfigDict(frozen=True)

    # Identificador estable del usuario en el proveedor. Por OIDC es una cadena
    # opaca: no se asume que sea un UUID aunque hoy Supabase emita uno.
    subject: str
    email: str
    full_name: str
    # Con qué inició sesión: "google", "email", etc. Informativo.
    provider: str | None = None

    @field_validator("email")
    @classmethod
    def _normalizar_email(cls, value: str) -> str:
        """Mismo criterio que la entidad User, para que ambos lados coincidan."""
        return value.strip().lower()
