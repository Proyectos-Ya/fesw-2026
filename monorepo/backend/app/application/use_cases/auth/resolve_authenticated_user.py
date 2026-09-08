"""Del token a la fila de `users`: quién es quien llama, en nuestros términos.

El backend dejó de emitir sesiones. Lo que llega es una identidad afirmada por
Supabase (`AuthPrincipal`), y todo el esquema —proveedores, licitaciones
guardadas, chats, alertas— cuelga de `users.id`, que es nuestro. Este caso de
uso es el puente: encuentra el perfil local de esa identidad, o lo crea la
primera vez.

**No enlaza por correo.** Si la identidad no tiene perfil, se crea uno nuevo
aunque el correo coincida con otra fila. Enlazar por correo es la primitiva del
secuestro de cuenta previo al registro: bastaría con registrarse en Supabase con
la dirección de otro para heredar su perfil, y verificar la dirección solo lo
mitiga si el dato de verificación es fiable. La decisión de producto fue borrar
las cuentas anteriores, así que no hay nada que enlazar.
"""

from app.application.repositories.user_repository import IUserRepository
from app.application.services.identity_directory import IIdentityDirectory
from app.domain.entities.auth_principal import AuthPrincipal
from app.domain.entities.user import User
from app.domain.errors.auth_errors import UserAlreadyExists, UserNotFound
from app.shared.datetime_utils import utc_now_naive


class ResolveAuthenticatedUserUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        identity_directory: IIdentityDirectory,
    ) -> None:
        self.user_repo = user_repo
        self.identity_directory = identity_directory

    async def execute(self, principal: AuthPrincipal) -> User:
        verificado = await self.identity_directory.email_confirmado(principal.subject)

        usuario = await self.user_repo.get_by_auth_provider_id(principal.subject)
        if usuario is not None:
            return await self._sincronizar(usuario, principal, verificado)

        return await self._crear(principal, verificado)

    async def _crear(self, principal: AuthPrincipal, verificado: bool) -> User:
        nuevo = User(
            email=principal.email,
            auth_provider_id=principal.subject,
            hashed_password=None,
            full_name=principal.full_name,
            email_verified=verificado,
        )
        try:
            return await self.user_repo.save(nuevo)
        except UserAlreadyExists:
            # Dos peticiones simultáneas de una identidad nueva llegan las dos
            # hasta acá; el índice único deja pasar una. La perdedora relee en
            # vez de fallar: para quien llama no hubo carrera.
            existente = await self.user_repo.get_by_auth_provider_id(principal.subject)
            if existente is None:
                raise UserNotFound(principal.subject) from None
            return existente

    async def _sincronizar(
        self, usuario: User, principal: AuthPrincipal, verificado: bool
    ) -> User:
        """Refleja en el perfil local lo que cambió del lado del proveedor.

        Solo escribe si algo cambió. Sin esa guarda, cada petición autenticada
        haría un UPDATE y un commit sobre la misma fila.

        `active` **no** se sincroniza: es una decisión nuestra, no del
        proveedor. Supabase no publica `banned_until` en el token, así que
        "sincronizarlo" significaría poner `active = True` en cada petición y
        reactivar en silencio toda cuenta desactivada a mano.
        """
        cambios: dict[str, object] = {}

        if usuario.email_verified != verificado:
            cambios["email_verified"] = verificado
        if usuario.email != principal.email:
            # El correo puede cambiar en el proveedor. Es un dato de contacto,
            # no la identidad: la identidad es `auth_provider_id`.
            cambios["email"] = principal.email
        if not usuario.full_name and principal.full_name:
            # Solo se rellena si está vacío: un nombre editado por el usuario
            # en nuestra aplicación no se pisa con el del proveedor.
            cambios["full_name"] = principal.full_name

        if not cambios:
            return usuario

        cambios["updated_at"] = utc_now_naive()
        return await self.user_repo.save(usuario.model_copy(update=cambios))
