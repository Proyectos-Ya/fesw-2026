from abc import ABC, abstractmethod


class IIdentityDirectory(ABC):
    """Lo que hay que preguntarle al proveedor de identidad, porque no va en el token.

    Existe por un caso concreto: **si el correo está confirmado**. Supabase no
    emite un claim `email_verified` de primer nivel; el dato solo aparece dentro
    de `user_metadata`, que el propio usuario escribe con
    `supabase.auth.updateUser({ data: ... })`. Confiar en el token para esto
    sería dejar que quien tiene que pasar por la verificación se la salte.
    """

    @abstractmethod
    async def email_confirmado(self, subject: str) -> bool:
        """True si el proveedor tiene la dirección de ese usuario como confirmada.

        `subject` es el `sub` del token. Un usuario que el proveedor no conoce
        —o que no se puede identificar— cuenta como no confirmado: ante la duda,
        el estado seguro es el que no habilita nada.
        """
        raise NotImplementedError
