"""Caso de uso: Obtener capacidades operativas y banderas de la extensión."""

from app.application.schemas.extension_schema import (
    ExtensionCapabilitiesResponse,
)
from app.config import Settings, settings as default_settings


class GetExtensionCapabilitiesUseCase:
    """Retorna los parámetros de configuración y flags operativos para la extensión."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or default_settings

    def execute(self) -> ExtensionCapabilitiesResponse:
        is_enabled = bool(self.settings.extension_enabled)
        return ExtensionCapabilitiesResponse(
            enabled=is_enabled,
            min_version=self.settings.extension_min_version,
            latest_version=self.settings.extension_latest_version,
            mp_adapter_enabled=is_enabled,
            fetch_jobs_enabled=is_enabled and (self.settings.extension_max_daily_fetches > 0),
            postulation_enabled=False,
            max_daily_fetches=self.settings.extension_max_daily_fetches if is_enabled else 0,
            polling_interval_seconds=self.settings.extension_polling_interval_seconds,
            supported_mp_hosts=[
                "buscador.mercadopublico.cl",
                "adjunto.mercadopublico.cl",
            ],
            message=None if is_enabled else "Servicio temporalmente deshabilitado",
        )
