import pytest

from app.application.schemas.auth_schema import LoginSchema, RegisterSchema
from app.application.use_cases.auth.login_user import LoginUserUseCase
from app.application.use_cases.auth.register_user import RegisterUserUseCase
from app.domain.errors.auth_errors import (
    InactiveUser,
    InvalidCredentials,
    UserAlreadyExists,
)
from tests.unit.application.fakes import (
    FakePasswordHasher,
    FakeTokenService,
    InMemoryUserRepository,
)


@pytest.fixture
def user_repo() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def hasher() -> FakePasswordHasher:
    return FakePasswordHasher()


async def test_register_creates_user_with_hashed_password(user_repo, hasher):
    data = RegisterSchema(
        email="nuevo@example.com", password="supersecret", full_name="Nuevo"
    )
    user = await RegisterUserUseCase(user_repo, hasher).execute(data)

    assert user.email == "nuevo@example.com"
    # La contraseña nunca se guarda en claro
    assert user.hashed_password == "hashed::supersecret"
    assert user.hashed_password != "supersecret"
    assert await user_repo.get_by_email("nuevo@example.com") is not None


async def test_register_duplicate_email_raises(user_repo, hasher):
    data = RegisterSchema(
        email="dup@example.com", password="supersecret", full_name="Dup"
    )
    await RegisterUserUseCase(user_repo, hasher).execute(data)

    with pytest.raises(UserAlreadyExists):
        await RegisterUserUseCase(user_repo, hasher).execute(data)


async def test_login_returns_token(user_repo, hasher):
    await RegisterUserUseCase(user_repo, hasher).execute(
        RegisterSchema(email="log@example.com", password="supersecret", full_name="L")
    )
    token, user = await LoginUserUseCase(user_repo, hasher, FakeTokenService()).execute(
        LoginSchema(email="log@example.com", password="supersecret")
    )
    assert token == f"token::{user.id}"


async def test_login_wrong_password_raises(user_repo, hasher):
    await RegisterUserUseCase(user_repo, hasher).execute(
        RegisterSchema(email="log@example.com", password="supersecret", full_name="L")
    )
    with pytest.raises(InvalidCredentials):
        await LoginUserUseCase(user_repo, hasher, FakeTokenService()).execute(
            LoginSchema(email="log@example.com", password="wrong-pass")
        )


async def test_login_unknown_email_raises(user_repo, hasher):
    with pytest.raises(InvalidCredentials):
        await LoginUserUseCase(user_repo, hasher, FakeTokenService()).execute(
            LoginSchema(email="ghost@example.com", password="whatever1")
        )


async def test_login_inactive_user_raises(user_repo, hasher):
    user = await RegisterUserUseCase(user_repo, hasher).execute(
        RegisterSchema(email="off@example.com", password="supersecret", full_name="O")
    )
    user.active = False
    await user_repo.save(user)

    with pytest.raises(InactiveUser):
        await LoginUserUseCase(user_repo, hasher, FakeTokenService()).execute(
            LoginSchema(email="off@example.com", password="supersecret")
        )
