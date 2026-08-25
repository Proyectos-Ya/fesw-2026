import pytest
from pydantic import ValidationError

from app.domain.entities.user import User


def test_create_valid_user():
    user = User(
        email="persona@example.com",
        hashed_password="hashed",
        full_name="Persona Ejemplo",
    )
    assert user.email == "persona@example.com"
    # Defaults de negocio: activo al crear, correo aún sin verificar
    assert user.active is True
    assert user.email_verified is False
    assert user.phone is None
    assert user.id is not None


def test_email_is_normalized_to_lowercase():
    user = User(
        email="Persona@Example.COM",
        hashed_password="hashed",
        full_name="Persona",
    )
    assert user.email == "persona@example.com"


@pytest.mark.parametrize("bad_email", ["no-arroba", "a@b", "@example.com", "x@.com"])
def test_invalid_email_raises(bad_email: str):
    with pytest.raises(ValidationError):
        User(email=bad_email, hashed_password="h", full_name="X")


class TestIdentidadExterna:
    """`auth_provider_id` enlaza el perfil con el usuario de Supabase Auth.

    Es una columna aparte y no el `id` del perfil: `supabase db reset` borra
    `auth.users` en local, y si el id fuera el mismo, todas las licitaciones
    guardadas y los proveedores quedarían colgando de una identidad que ya no
    existe. Además el `sub` de OIDC es una cadena opaca, no un UUID.
    """

    def test_un_perfil_puede_no_tener_identidad_externa_todavia(self):
        """Nullable mientras convivan el login propio y Supabase."""
        user = User(email="a@ejemplo.cl", hashed_password="h", full_name="A")
        assert user.auth_provider_id is None

    def test_guarda_el_identificador_del_proveedor(self):
        user = User(
            email="a@ejemplo.cl",
            hashed_password="h",
            full_name="A",
            auth_provider_id="8f14e45f-ceea-467a-9c8d-0000deadbeef",
        )
        assert user.auth_provider_id == "8f14e45f-ceea-467a-9c8d-0000deadbeef"

    def test_no_se_exige_que_sea_un_uuid(self):
        """Otros proveedores OIDC usan `sub` que no son UUID."""
        user = User(
            email="a@ejemplo.cl",
            hashed_password="h",
            full_name="A",
            auth_provider_id="auth0|1234567890",
        )
        assert user.auth_provider_id == "auth0|1234567890"
