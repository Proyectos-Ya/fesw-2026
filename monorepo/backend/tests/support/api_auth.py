"""Cómo se autentica una petición en los tests de la API.

El verificador que corre es el **real**: lo único sustituido es de dónde salen
las claves públicas (un JWKS de prueba en memoria) y el padrón de correos
confirmados. Así cada test de endpoint sigue ejercitando firma, emisor,
audiencia y vigencia, en vez de un doble que diría que sí a cualquier cosa.
"""

from uuid import UUID

from httpx import AsyncClient

from app import bootstrap
from app.infrastructure.services.supabase_token_service import SupabaseJwtService
from tests.support.supabase_tokens import AUDIENCIA, EMISOR, ClavesDePrueba
from tests.unit.application.fakes import FakeIdentityDirectory

# `sub` por defecto de las pruebas. Es un UUID porque es lo que emite GoTrue.
SUB_POR_DEFECTO = "11111111-1111-4111-8111-111111111111"


def preparar_auth(app, cliente: AsyncClient) -> None:
    """Sustituye el origen de las claves y el padrón, y los deja en el cliente.

    Van colgados del cliente y no como fixtures aparte para que los ayudantes
    de cada archivo de test —que solo reciben `api`— puedan emitir tokens sin
    arrastrar dos parámetros más por cada llamada.
    """
    claves = ClavesDePrueba()
    directorio = FakeIdentityDirectory()

    app.dependency_overrides[bootstrap.get_token_verifier] = lambda: SupabaseJwtService(
        jwks_source=claves.fuente_jwks,
        issuer=EMISOR,
        audience=AUDIENCIA,
    )
    app.dependency_overrides[bootstrap.get_identity_directory] = lambda: directorio

    cliente.claves = claves
    cliente.directorio_de_identidad = directorio


async def autenticar(
    api: AsyncClient,
    *,
    sub: str = SUB_POR_DEFECTO,
    email: str = "persona@ejemplo.cl",
    full_name: str = "Persona de Prueba",
    verificado: bool = True,
) -> UUID:
    """Deja al cliente autenticado y devuelve el id **local** del perfil.

    El id local no es el `sub`: es el de la fila de `users`, que es a la que
    apuntan todas las claves foráneas del esquema. Se obtiene de `/auth/me`,
    que además es donde se aprovisiona el perfil la primera vez.
    """
    if verificado:
        api.directorio_de_identidad.confirmar(sub)

    token = api.claves.token(
        sub=sub, email=email, user_metadata={"full_name": full_name}
    )
    api.headers["Authorization"] = f"Bearer {token}"

    me = await api.get("/auth/me")
    assert me.status_code == 200, me.text
    return UUID(me.json()["id"])
