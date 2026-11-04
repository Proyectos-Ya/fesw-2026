"""Errores de dominio para la extensión de navegador (Plan 233, Decisión 7)."""

from typing import ClassVar


class ExtensionError(Exception):
    """Error base del módulo de extensión."""

    code: ClassVar[str] = "extension_error"

    def __init__(self, message: str, **extra: object) -> None:
        super().__init__(message)
        self.message = message
        self.extra = extra


class ExtensionDisabledError(ExtensionError):
    code = "extension_disabled"

    def __init__(self) -> None:
        super().__init__("La extensión de navegador se encuentra deshabilitada temporalmente.")


class InvalidPairingTicketError(ExtensionError):
    code = "invalid_pairing_ticket"

    def __init__(self) -> None:
        super().__init__("El ticket de emparejamiento no es válido o ya fue utilizado.")


class PairingTicketExpiredError(ExtensionError):
    code = "pairing_ticket_expired"

    def __init__(self) -> None:
        super().__init__("El ticket de emparejamiento ha expirado.")


class ExtensionInstallationNotFound(ExtensionError):
    code = "extension_installation_not_found"

    def __init__(self) -> None:
        super().__init__("La instalación de la extensión no fue encontrada o está inactiva.")


class DailyFetchQuotaExceeded(ExtensionError):
    code = "daily_fetch_quota_exceeded"

    def __init__(self) -> None:
        super().__init__("Se ha alcanzado la cuota diaria máxima de tareas de extracción para este cliente.")


class ExtensionJobNotFound(ExtensionError):
    code = "extension_job_not_found"

    def __init__(self) -> None:
        super().__init__("La tarea de extracción no fue encontrada.")
