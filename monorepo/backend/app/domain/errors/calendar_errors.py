from uuid import UUID


class CalendarError(Exception):
    """Base de los errores de sincronización con calendarios externos."""


_NOMBRES = {"google": "Google Calendar"}


class CalendarNotConfigured(CalendarError):
    def __init__(self, provider: str):
        nombre = _NOMBRES.get(str(provider), str(provider))
        super().__init__(f"La sincronización con {nombre} no está disponible en este momento.")
        self.provider = provider


class InvalidOAuthState(CalendarError):
    def __init__(
        self,
        message: str = "La autorización no es válida o expiró. Vuelve a intentar la sincronización desde la licitación.",
    ):
        super().__init__(message)


class CalendarAuthExpired(CalendarError):
    def __init__(
        self,
        message: str = "El acceso a tu calendario expiró o fue revocado. Vuelve a conectar tu cuenta.",
    ):
        super().__init__(message)


class CalendarPermissionMissing(CalendarError):
    def __init__(
        self,
        message: str = "No autorizaste el acceso a tu calendario. Vuelve a conectar y marca el permiso de Google Calendar.",
    ):
        super().__init__(message)


class CalendarProviderUnavailable(CalendarError):
    def __init__(
        self,
        message: str = "El servicio de calendario no respondió. Intenta nuevamente en unos minutos.",
    ):
        super().__init__(message)


class MilestoneTimeRequired(CalendarError):
    """Hay hitos sin hora exacta: el usuario debe confirmar una hora por defecto."""

    def __init__(self, milestone_ids: list[UUID]):
        super().__init__(
            "Algunos hitos no tienen hora exacta. Confirma una hora por defecto antes de sincronizar."
        )
        self.milestone_ids = milestone_ids
