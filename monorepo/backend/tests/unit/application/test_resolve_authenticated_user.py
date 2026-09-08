"""Del `sub` del token a la fila de `users`.

Dos cosas se fijan acá y no deberían moverse sin discutirlo: que **no** se
enlaza por correo, y que la verificación sale del padrón del proveedor y no de
lo que diga el token.
"""

import pytest

from app.application.use_cases.auth.resolve_authenticated_user import (
    ResolveAuthenticatedUserUseCase,
)
from app.domain.entities.auth_principal import AuthPrincipal
from app.domain.entities.user import User
from tests.unit.application.fakes import (
    FakeIdentityDirectory,
    InMemoryUserRepository,
)

pytestmark = pytest.mark.asyncio

SUB = "11111111-1111-4111-8111-111111111111"


def _principal(**cambios) -> AuthPrincipal:
    base = {
        "subject": SUB,
        "email": "persona@ejemplo.cl",
        "full_name": "Persona de Prueba",
        "provider": "google",
    }
    return AuthPrincipal(**{**base, **cambios})


def _caso(confirmados: set[str] | None = None):
    repo = InMemoryUserRepository()
    directorio = FakeIdentityDirectory(confirmados or set())
    return repo, directorio, ResolveAuthenticatedUserUseCase(repo, directorio)


class TestPrimeraVez:
    async def test_crea_el_perfil_local(self):
        repo, _, caso = _caso({SUB})

        usuario = await caso.execute(_principal())

        assert usuario.auth_provider_id == SUB
        assert usuario.email == "persona@ejemplo.cl"
        assert usuario.full_name == "Persona de Prueba"
        assert repo.users[usuario.id] == usuario

    async def test_no_guarda_contrasena(self):
        """Quien entra por Supabase no tiene ninguna que guardar."""
        _, _, caso = _caso({SUB})

        assert (await caso.execute(_principal())).hashed_password is None

    async def test_refleja_la_verificacion_del_padron(self):
        _, _, caso = _caso({SUB})
        assert (await caso.execute(_principal())).email_verified is True

    async def test_sin_confirmar_el_perfil_nace_sin_verificar(self):
        _, _, caso = _caso(set())
        assert (await caso.execute(_principal())).email_verified is False


class TestNoEnlazaPorCorreo:
    """Enlazar por correo es la primitiva del secuestro de cuenta previo al registro.

    Con el enlace activo, registrarse en Supabase con la dirección de otra
    persona bastaría para heredar su empresa, sus licitaciones guardadas y su
    historial. Se crea un perfil aparte, aunque el correo coincida.
    """

    async def test_un_correo_repetido_no_toma_el_perfil_ajeno(self):
        repo, directorio, caso = _caso({SUB})
        ajeno = await repo.save(
            User(
                email="persona@ejemplo.cl",
                full_name="Cuenta Anterior",
                auth_provider_id=None,
            )
        )

        nuevo = await caso.execute(_principal())

        assert nuevo.id != ajeno.id
        assert (await repo.get_by_id(ajeno.id)).auth_provider_id is None


class TestYaExiste:
    async def test_devuelve_el_mismo_perfil(self):
        _, _, caso = _caso({SUB})
        primero = await caso.execute(_principal())

        segundo = await caso.execute(_principal())

        assert segundo.id == primero.id

    async def test_no_escribe_cuando_nada_cambio(self):
        repo, _, caso = _caso({SUB})
        usuario = await caso.execute(_principal())
        antes = usuario.updated_at

        assert (await caso.execute(_principal())).updated_at == antes

    async def test_un_correo_cambiado_en_el_proveedor_se_refleja(self):
        """El correo es dato de contacto; la identidad es `auth_provider_id`."""
        _, _, caso = _caso({SUB})
        await caso.execute(_principal())

        actualizado = await caso.execute(_principal(email="nueva@ejemplo.cl"))

        assert actualizado.email == "nueva@ejemplo.cl"

    async def test_confirmar_el_correo_despues_actualiza_el_perfil(self):
        _, directorio, caso = _caso(set())
        await caso.execute(_principal())

        directorio.confirmar(SUB)

        assert (await caso.execute(_principal())).email_verified is True

    async def test_no_pisa_un_nombre_ya_puesto(self):
        repo, _, caso = _caso({SUB})
        usuario = await caso.execute(_principal(full_name="Ana Díaz"))

        actualizado = await caso.execute(_principal(full_name="Otro Nombre"))

        assert actualizado.full_name == "Ana Díaz"
        assert actualizado.id == usuario.id

    async def test_no_reactiva_una_cuenta_desactivada(self):
        """Supabase no publica `banned_until`, así que sincronizar `active`
        significaría ponerlo en True en cada petición."""
        repo, _, caso = _caso({SUB})
        usuario = await caso.execute(_principal())
        await repo.save(usuario.model_copy(update={"active": False}))

        assert (await caso.execute(_principal())).active is False


class TestCarrera:
    async def test_dos_peticiones_simultaneas_no_duplican_el_perfil(self):
        """La perdedora del índice único relee en vez de fallar."""
        repo, directorio, caso = _caso({SUB})
        ganadora = await repo.save(
            User(
                email="persona@ejemplo.cl",
                full_name="Persona de Prueba",
                auth_provider_id=SUB,
            )
        )

        resuelto = await caso._crear(_principal(), verificado=True)

        assert resuelto.id == ganadora.id
        assert len(repo.users) == 1
