
class AlreadyHasSupplier(Exception):
    """El usuario ya pertenece (o solicitó unirse) a un proveedor."""

    def __init__(self) -> None:
        super().__init__("El usuario ya pertenece o solicitó unirse a un proveedor")


class MembershipNotFound(Exception):
    def __init__(self) -> None:
        super().__init__("Solicitud o membresía no encontrada")


class NotAuthorized(Exception):
    """El usuario no tiene permisos (rol) para realizar la acción."""

    def __init__(self, message: str = "No autorizado para realizar esta acción"):
        super().__init__(message)
