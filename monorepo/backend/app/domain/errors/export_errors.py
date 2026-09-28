class ExportError(Exception):
    """Base de los errores de exportación de licitaciones (HdU 19)."""


class ExportForbidden(ExportError):
    """El rol del usuario en la empresa activa no le permite exportar."""

    def __init__(self) -> None:
        super().__init__("Tu rol en esta empresa no permite exportar licitaciones.")
