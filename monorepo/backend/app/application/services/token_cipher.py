from abc import ABC, abstractmethod


class ITokenCipher(ABC):
    """Cifrado simétrico de los tokens de terceros guardados en la base."""

    @abstractmethod
    def encrypt(self, plaintext: str) -> str: ...

    @abstractmethod
    def decrypt(self, ciphertext: str) -> str: ...
