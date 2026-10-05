"""Entidad de instalación de extensión de navegador (Plan 233, Decisión 7)."""

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime, utc_now_naive

BrowserType = Literal["chrome", "firefox", "edge", "safari", "other"]


class ExtensionInstallation(BaseModel):
    """Instalación individual de la extensión en el navegador de un usuario."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    workspace_id: UUID | None = None
    browser: BrowserType
    browser_version: str | None = None
    extension_version: str
    is_active: bool = True
    last_heartbeat_at: UtcDateTime | None = None
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)
