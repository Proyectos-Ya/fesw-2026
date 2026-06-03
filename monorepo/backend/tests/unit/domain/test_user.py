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
