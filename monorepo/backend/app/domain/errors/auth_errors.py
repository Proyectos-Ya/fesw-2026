class UserAlreadyExists(Exception):
    def __init__(self, email: str):
        super().__init__(f"Ya existe un usuario con el correo {email}")
        self.email = email


class UserNotFound(Exception):
    def __init__(self, identifier: str):
        super().__init__(f"Usuario {identifier} no encontrado")
        self.identifier = identifier


class InvalidCredentials(Exception):
    def __init__(self) -> None:
        super().__init__("Correo o contraseña incorrectos")


class InactiveUser(Exception):
    def __init__(self) -> None:
        super().__init__("La cuenta de usuario está inactiva")


class InvalidToken(Exception):
    def __init__(self) -> None:
        super().__init__("Token de autenticación inválido o expirado")
