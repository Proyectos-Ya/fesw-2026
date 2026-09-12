class MembershipError(Exception):
    """Excepción base para errores relacionados a membresías de empresas."""


class MembershipNotFound(MembershipError):
    def __init__(self, message: str = "Membresía no encontrada"):
        super().__init__(message)


class UserAlreadyMember(MembershipError):
    def __init__(self, message: str = "El usuario ya es miembro de esta empresa"):
        super().__init__(message)


class UnauthorizedWorkspaceAction(MembershipError):
    def __init__(self, message: str = "No tienes permisos para realizar esta acción"):
        super().__init__(message)


class InvitationError(Exception):
    """Excepción base para errores de invitaciones."""


class InvitationNotFound(InvitationError):
    def __init__(self, message: str = "Invitación no encontrada"):
        super().__init__(message)


class InvitationExpired(InvitationError):
    def __init__(self, message: str = "La invitación ha expirado"):
        super().__init__(message)


class InvitationAlreadyProcessed(InvitationError):
    def __init__(self, message: str = "La invitación ya fue procesada previamente"):
        super().__init__(message)


class InvitationEmailMismatch(InvitationError):
    def __init__(
        self,
        message: str = "El correo de la invitación no coincide con el usuario autenticado",
    ):
        super().__init__(message)
