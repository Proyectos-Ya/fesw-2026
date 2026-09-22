from abc import ABC, abstractmethod

from app.domain.entities.auth_principal import AuthPrincipal


class IAuthTokenVerifier(ABC):
    """Comprueba un token de sesión y dice de quién es.

    El backend ya no emite sesiones, solo las valida. Este puerto existe para
    que `get_current_user` dependa de la capa de aplicación y no del verificador
    concreto de Supabase, y para poder sustituirlo en las pruebas sin levantar
    un proveedor de identidad.
    """

    @abstractmethod
    async def verify(self, token: str) -> AuthPrincipal:
        """Devuelve la identidad afirmada por el token.

        Lanza `InvalidToken` ante cualquier problema —firma, emisor, audiencia,
        vencimiento, claims faltantes— sin distinguir cuál: quien recibe el 401
        no debería poder averiguar en qué falló.
        """
        raise NotImplementedError
