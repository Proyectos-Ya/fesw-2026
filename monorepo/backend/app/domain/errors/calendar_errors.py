from uuid import UUID


class CalendarError(Exception):
    """Base de los errores de sincronización con calendarios externos."""


class MilestoneTimeRequired(CalendarError):
    """Hay hitos sin hora exacta: el usuario debe confirmar una hora por defecto."""

    def __init__(self, milestone_ids: list[UUID]):
        super().__init__(
            "Algunos hitos no tienen hora exacta. Confirma una hora por defecto antes de sincronizar."
        )
        self.milestone_ids = milestone_ids
