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
    """El token no permite afirmar quién hace la petición.

    El motivo es opcional y sirve para diagnosticar: la respuesta HTTP sigue
    siendo un 401 sin detalle, porque decirle a quien prueba tokens si falló la
    firma, el emisor o la vigencia le ahorra el trabajo de averiguarlo.
    """

    def __init__(self, motivo: str | None = None) -> None:
        super().__init__(motivo or "Token de autenticación inválido o expirado")
        self.motivo = motivo
