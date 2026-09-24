class MilestoneError(Exception):
    """Base de los errores de hitos de licitación."""


class InvalidMilestoneDate(MilestoneError):
    """La fecha u hora de un hito no es ISO estricta o es imposible."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class MilestoneExtractionUnavailable(MilestoneError):
    def __init__(
        self,
        message: str = "No se pudieron extraer los hitos de las bases en este momento. Intenta nuevamente en unos minutos.",
    ):
        super().__init__(message)
