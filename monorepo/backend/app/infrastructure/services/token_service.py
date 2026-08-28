from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from app.application.services.token_service import ITokenService
from app.domain.errors.auth_errors import InvalidToken


class JwtTokenService(ITokenService):
    """Implementación de tokens de acceso con JWT (pyjwt)."""

    def __init__(self, secret_key: str, algorithm: str, expire_minutes: int):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expire_minutes = expire_minutes

    def create_access_token(self, user_id: UUID) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=self.expire_minutes)
        payload = {"sub": str(user_id), "exp": expire}
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> UUID:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return UUID(payload["sub"])
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise InvalidToken() from exc
