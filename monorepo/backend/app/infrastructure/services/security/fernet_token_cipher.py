from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.application.services.token_cipher import ITokenCipher


class TokenDecryptionError(Exception):
    """El texto no se cifró con ninguna de las llaves configuradas."""


class FernetTokenCipher(ITokenCipher):
    """Cifrado autenticado (AES-128-CBC + HMAC) de tokens de terceros.

    `keys` admite varias llaves separadas por coma para rotarlas: la primera
    cifra y todas descifran.
    """

    def __init__(self, keys: str):
        llaves = [llave.strip() for llave in keys.split(",") if llave.strip()]
        if not llaves:
            raise ValueError("TOKEN_ENCRYPTION_KEY está vacía.")
        self._fernet = MultiFernet([Fernet(llave) for llave in llaves])

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            raise TokenDecryptionError(
                "No se pudo descifrar el token con las llaves configuradas."
            ) from None
