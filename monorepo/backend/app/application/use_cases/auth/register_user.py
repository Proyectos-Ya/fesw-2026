from app.application.repositories.user_repository import IUserRepository
from app.application.schemas.auth_schema import RegisterSchema
from app.application.services.password_hasher import IPasswordHasher
from app.domain.entities.user import User
from app.domain.errors.auth_errors import UserAlreadyExists


class RegisterUserUseCase:
    def __init__(self, repo: IUserRepository, hasher: IPasswordHasher):
        self.repo = repo
        self.hasher = hasher

    async def execute(self, data: RegisterSchema) -> User:
        # El email se normaliza/valida dentro de la entidad User
        existing = await self.repo.get_by_email(data.email)
        if existing:
            raise UserAlreadyExists(data.email)

        user = User(
            email=data.email,
            hashed_password=self.hasher.hash(data.password),
            full_name=data.full_name,
            phone=data.phone,
        )
        return await self.repo.save(user)
