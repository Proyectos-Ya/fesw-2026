"""Consulta a GoTrue si una dirección está confirmada, leyendo su propia tabla.

Se lee `auth.users.email_confirmed_at` en vez de creerle al token porque es el
único lugar donde el dato no lo puede escribir el usuario. La alternativa
—llamar a la API admin de GoTrue— sumaría un salto de red por petición y
obligaría a guardar la `service_role` key en el backend, que es una credencial
con la que se puede hacer cualquier cosa sobre cualquier usuario.

El backend ya habla con esta misma base: `DATABASE_URL` apunta al Postgres de
Supabase, donde el esquema `auth` convive con el `public` de la aplicación.
"""

from uuid import UUID

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.services.identity_directory import IIdentityDirectory

# `email_confirmed_at` es NULL mientras no se confirme y lleva la fecha después.
# Se pregunta por la existencia de la fila y por la columna en la misma consulta
# para no tener que distinguir "no existe" de "existe sin confirmar": las dos
# significan lo mismo para quien llama.
_CONSULTA = text(
    "SELECT email_confirmed_at IS NOT NULL FROM auth.users WHERE id = :sub"
)


class SupabaseIdentityDirectory(IIdentityDirectory):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def email_confirmado(self, subject: str) -> bool:
        try:
            identificador = UUID(subject)
        except ValueError:
            # El `sub` de OIDC es una cadena opaca, pero GoTrue siempre emite un
            # UUID. Si no lo es, el token no lo emitió el Supabase de este
            # proyecto y no hay a quién preguntarle.
            return False

        resultado = await self.session.execute(_CONSULTA, {"sub": identificador})
        return bool(resultado.scalar_one_or_none())
