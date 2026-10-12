class ShareLinkError(Exception):
    """Base de los errores de enlaces compartidos (HdU 19)."""


class ShareLinkNotFound(ShareLinkError):
    """El enlace no existe, o quien lo pide no tiene por qué saber que existe."""

    def __init__(self) -> None:
        super().__init__("El enlace no existe.")


class ShareLinkExpired(ShareLinkError):
    """Se cumplieron los 7 días de vigencia (criterio 6)."""

    def __init__(self) -> None:
        super().__init__("El enlace caducó.")


class ShareLinkRevoked(ShareLinkError):
    """Quien lo generó lo revocó antes de que venciera (criterio 7)."""

    def __init__(self) -> None:
        super().__init__("El enlace fue revocado.")


class ShareLinkForbidden(ShareLinkError):
    """El rol del usuario en la empresa activa no le permite compartir."""

    def __init__(self) -> None:
        super().__init__("Tu rol en esta empresa no permite compartir licitaciones.")
