"""Verificación de los JWT que emite Supabase Auth, contra su JWKS.

El backend no emite sesiones: las valida. La clave con que Supabase firma es
asimétrica, así que acá solo vive la pública —descargada de su JWKS y
cacheada—, y con eso alcanza para comprobar una firma pero no para producirla.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import jwt
from jwt import PyJWK

from app.application.services.token_verifier import IAuthTokenVerifier
from app.domain.entities.auth_principal import AuthPrincipal
from app.domain.errors.auth_errors import InvalidToken

# Fija en código y no leída del header del token. Si se aceptara HS256 junto a
# los asimétricos, cualquiera podría tomar la clave pública —que el JWKS publica
# a quien la pida—, usarla como secreto HMAC y firmar sesiones de cualquier
# usuario. Es el ataque de confusión de algoritmo, y la defensa es esta lista.
ALGORITMOS_ACEPTADOS = ("ES256", "RS256")

# Claims sin los cuales no se decide nada: sin `sub` no se sabe quién es, y sin
# los otros tres el token podría ser de otro sistema, para otra audiencia o de
# hace un año. PyJWT no exige ninguno por su cuenta.
CLAIMS_OBLIGATORIOS = ("sub", "exp", "aud", "iss")

# Un `kid` desconocido obliga a releer el JWKS, porque puede ser una clave recién
# rotada. Sin un piso entre recargas, mandar tokens con `kid` al azar convierte a
# este backend en un ariete contra el servidor de Supabase.
SEGUNDOS_MINIMOS_ENTRE_RECARGAS = 30


class SupabaseJwtService(IAuthTokenVerifier):
    """Comprueba firma, emisor, audiencia y vigencia; devuelve quién es.

    La fuente del JWKS se inyecta en vez de estar cableada al cliente HTTP: es
    lo que permite ejercitar la verificación real en las pruebas sin levantar
    Supabase ni tocar la red.
    """

    def __init__(
        self,
        jwks_source: Callable[[], Awaitable[dict[str, Any]]],
        issuer: str,
        audience: str,
        cache_seconds: int = 600,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._jwks_source = jwks_source
        self._issuer = issuer
        self._audience = audience
        self._cache_seconds = cache_seconds
        self._reloj = reloj

        self._claves: dict[str, PyJWK] = {}
        self._cargado_en: float | None = None
        # Última recarga disparada por un `kid` que no teníamos. Se lleva aparte
        # de `_cargado_en` para que la primera carga no cuente como intento
        # fallido: si contara, una rotación de claves justo después de arrancar
        # quedaría sin detectar durante toda la ventana.
        self._forzado_en: float | None = None
        self._candado = asyncio.Lock()

    async def verify(self, token: str) -> AuthPrincipal:
        """Devuelve la identidad afirmada por el token, o lanza `InvalidToken`.

        Toda excepción de PyJWT se traduce: quien llama no debería tener que
        distinguir entre una firma mala y un `exp` vencido, y el detalle no le
        sirve de nada a quien recibe el 401.
        """
        try:
            cabecera = jwt.get_unverified_header(token)
        except jwt.PyJWTError as e:
            raise InvalidToken("El token no tiene un encabezado legible") from e

        kid = cabecera.get("kid")

        if not kid:
            raise InvalidToken("El token no declara con qué clave fue firmado")

        if (alg := cabecera.get("alg")) not in ALGORITMOS_ACEPTADOS:
            raise InvalidToken(f"Algoritmo de firma no aceptado: {alg}")

        clave = await self._clave_para(kid)

        try:
            claims = jwt.decode(
                token,
                clave.key,
                algorithms=list(ALGORITMOS_ACEPTADOS),
                audience=self._audience,
                issuer=self._issuer,
                options={"require": list(CLAIMS_OBLIGATORIOS)},
            )
        # TypeError y ValueError además de PyJWTError: cuando el algoritmo del
        # token y el tipo de la clave no casan, PyJWT no lanza un error suyo
        # sino un TypeError crudo desde sus utilidades. Sin capturarlo, un token
        # deforme sale como 500 en vez del 401 que corresponde.
        except (jwt.PyJWTError, TypeError, ValueError) as e:
            raise InvalidToken("El token no es válido") from e

        return self._a_principal(claims)

    # -- Claves ------------------------------------------------------------

    async def _clave_para(self, kid: str) -> PyJWK:
        if (clave := self._claves.get(kid)) is not None and not self._cache_vencida():
            return clave

        await self._recargar_si_corresponde(kid)

        if (clave := self._claves.get(kid)) is None:
            raise InvalidToken("El token fue firmado con una clave desconocida")
        return clave

    def _cache_vencida(self) -> bool:
        if self._cargado_en is None:
            return True
        return self._reloj() - self._cargado_en > self._cache_seconds

    async def _recargar_si_corresponde(self, kid: str) -> None:
        async with self._candado:
            # Otra petición pudo recargar mientras esperábamos el candado.
            if kid in self._claves and not self._cache_vencida():
                return

            # Primera carga o caché vencida: recargar es lo esperado.
            if self._cargado_en is None or self._cache_vencida():
                await self._recargar()
                return

            # Caché vigente y un `kid` que no está en ella. Puede ser una clave
            # recién rotada, así que vale la pena mirar una vez; pero solo una
            # por ventana, o cada token con `kid` inventado nos haría descargar.
            if not self._puede_forzar():
                return
            self._forzado_en = self._reloj()
            await self._recargar()

    def _puede_forzar(self) -> bool:
        if self._forzado_en is None:
            return True
        return self._reloj() - self._forzado_en >= SEGUNDOS_MINIMOS_ENTRE_RECARGAS

    async def _recargar(self) -> None:
        documento = await self._jwks_source()
        # El timestamp se actualiza aunque el documento venga vacío o ilegible:
        # si el JWKS está caído, reintentar en cada petición solo agrega carga
        # sobre algo que ya está mal.
        self._cargado_en = self._reloj()
        self._claves = {
            jwk["kid"]: PyJWK.from_dict(jwk)
            for jwk in documento.get("keys", [])
            if jwk.get("kid")
        }

    # -- Claims ------------------------------------------------------------

    def _a_principal(self, claims: dict[str, Any]) -> AuthPrincipal:
        # Una sesión anónima no representa a nadie a quien podamos asociarle un
        # perfil, y `service_role` es una credencial de servidor: ninguna de las
        # dos debería poder actuar como un usuario conectado.
        if claims.get("is_anonymous") is True:
            raise InvalidToken("Las sesiones anónimas no tienen acceso")
        if claims.get("role") != "authenticated":
            raise InvalidToken("El token no corresponde a un usuario conectado")

        email = claims.get("email") or ""
        if not email:
            raise InvalidToken("El token no trae correo electrónico")

        metadata = claims.get("user_metadata") or {}
        app_metadata = claims.get("app_metadata") or {}

        # `email_verified` no se lee del token a propósito. Supabase no lo emite
        # como claim de primer nivel; solo aparece dentro de `user_metadata`, que
        # el propio usuario escribe con `supabase.auth.updateUser({ data: ... })`.
        # Tomarlo de ahí convertiría la verificación de correo en un interruptor
        # que abre quien tiene que pasar por él. Se consulta a
        # `auth.users.email_confirmed_at` (ver `IIdentityDirectory`).
        return AuthPrincipal(
            subject=str(claims["sub"]),
            email=email,
            full_name=_nombre(metadata, email),
            provider=app_metadata.get("provider"),
        )


def _nombre(metadata: dict[str, Any], email: str) -> str:
    """El nombre según lo que el proveedor haya querido entregar.

    Google manda `full_name`; otros mandan `name`; el registro por correo puede
    no mandar ninguno. La parte local del correo es un último recurso feo pero
    estable, y es preferible a un perfil sin nombre.
    """
    for clave in ("full_name", "name"):
        valor = metadata.get(clave)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    return email.split("@", 1)[0]


async def descargar_jwks(url: str, timeout: float = 5.0) -> dict[str, Any]:
    """Fuente por defecto del JWKS: un GET al endpoint de descubrimiento.

    Se usa httpx async y no `jwt.PyJWKClient` porque ese cliente hace la
    descarga con urllib de forma síncrona, y acá se ejecuta dentro del manejo de
    una petición: bloquearía el event loop de todas las demás.
    """
    async with httpx.AsyncClient(timeout=timeout) as cliente:
        respuesta = await cliente.get(url)
        respuesta.raise_for_status()
        return respuesta.json()
