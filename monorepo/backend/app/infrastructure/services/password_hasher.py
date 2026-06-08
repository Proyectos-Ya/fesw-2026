import bcrypt

from app.application.services.password_hasher import IPasswordHasher

# bcrypt opera sobre como máximo 72 bytes; recortamos para evitar el ValueError
# que lanza bcrypt 5.x con entradas más largas.
_MAX_BCRYPT_BYTES = 72


class BcryptPasswordHasher(IPasswordHasher):
    """Implementación de hashing con bcrypt (sin passlib)."""

    def hash(self, plain_password: str) -> str:
        password_bytes = plain_password.encode("utf-8")[:_MAX_BCRYPT_BYTES]
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        password_bytes = plain_password.encode("utf-8")[:_MAX_BCRYPT_BYTES]
        try:
            return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
        except ValueError:
            # Hash mal formado almacenado en BD
            return False
