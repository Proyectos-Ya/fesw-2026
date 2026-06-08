from app.application.repositories.user_repository import IUserRepository
from app.application.schemas.auth_schema import LoginSchema
from app.application.services.password_hasher import IPasswordHasher
from app.application.services.token_service import ITokenService
from app.domain.entities.user import User
from app.domain.errors.auth_errors import InactiveUser, InvalidCredentials


class LoginUserUseCase:
    def __init__(
        self,
        repo: IUserRepository,
        hasher: IPasswordHasher,
        token_service: ITokenService,
    ):
        self.repo = repo
        self.hasher = hasher
        self.token_service = token_service

    async def execute(self, data: LoginSchema) -> tuple[str, User]:
        user = await self.repo.get_by_email(data.email)
        # Mismo error para email inexistente o password incorrecto: no revelamos cuál falló
        if user is None or not self.hasher.verify(data.password, user.hashed_password):
            raise InvalidCredentials()

        if not user.active:
            raise InactiveUser()

        token = self.token_service.create_access_token(user.id)
        return token, user
