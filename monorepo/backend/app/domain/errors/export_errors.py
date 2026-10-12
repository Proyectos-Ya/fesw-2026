from typing import Literal


class ExportError(Exception):
    """Base de los errores de exportación de licitaciones (HdU 19)."""


class ExportForbidden(ExportError):
    """El rol del usuario en la empresa activa no le permite exportar."""

    def __init__(self) -> None:
        super().__init__("Tu rol en esta empresa no permite exportar licitaciones.")


class ExportSectionsRequired(ExportError):
    """Un Excel sin ninguna sección marcada no tendría nada (criterio 5)."""

    def __init__(self) -> None:
        super().__init__("Elige al menos una sección para el Excel.")


class ExportGenerationFailed(ExportError):
    """El archivo no se pudo generar."""

    def __init__(self) -> None:
        super().__init__("No se pudo generar el archivo. Inténtalo de nuevo.")


class ExportJobNotFound(ExportError):
    """No existe, o es de otro usuario: a él no le corresponde saberlo."""

    def __init__(self) -> None:
        super().__init__("La exportación no existe.")


UnavailableReason = Literal["processing", "failed", "expired"]

_MENSAJES: dict[UnavailableReason, str] = {
    "processing": "El archivo todavía se está generando.",
    "failed": "No se pudo generar el archivo. Vuelve a exportarlo desde la licitación.",
    "expired": "El archivo ya no está disponible: vence a los 7 días. Vuelve a exportarlo.",
}


class ExportFileUnavailable(ExportError):
    """Todavía no está listo, falló o ya venció."""

    def __init__(self, reason: UnavailableReason) -> None:
        super().__init__(_MENSAJES[reason])
        self.reason = reason
