"""Interfaces de repositorio para la extensión de navegador (Plan 233, Decisión 7)."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.entities.extension_fetch_job import ExtensionFetchJob
from app.domain.entities.extension_installation import ExtensionInstallation


class IExtensionInstallationRepository(ABC):
    """Acceso a datos de instalaciones registradas de la extensión."""

    @abstractmethod
    async def get_by_id(self, installation_id: UUID) -> ExtensionInstallation | None:
        """Obtiene una instalación por su identificador único."""
        ...

    @abstractmethod
    async def get_by_user_and_browser(
        self, user_id: UUID, browser: str
    ) -> ExtensionInstallation | None:
        """Busca una instalación activa previa para el usuario y navegador."""
        ...

    @abstractmethod
    async def save(self, installation: ExtensionInstallation) -> ExtensionInstallation:
        """Crea o actualiza una instalación."""
        ...

    @abstractmethod
    async def update_heartbeat(
        self, installation_id: UUID, heartbeat_at: datetime
    ) -> bool:
        """Actualiza el último latido registrado de la instalación."""
        ...

    @abstractmethod
    async def deactivate(self, installation_id: UUID) -> bool:
        """Desactiva una instalación."""
        ...


class IExtensionFetchJobRepository(ABC):
    """Acceso a datos de la cola distribuida de extracción de anexos."""

    @abstractmethod
    async def create_job(self, job: ExtensionFetchJob) -> ExtensionFetchJob:
        """Encola una nueva tarea de extracción si no existe una activa para esa licitación."""
        ...

    @abstractmethod
    async def get_by_id(self, job_id: UUID) -> ExtensionFetchJob | None:
        """Obtiene una tarea por su identificador."""
        ...

    @abstractmethod
    async def get_by_tender_id(self, tender_id: UUID) -> ExtensionFetchJob | None:
        """Obtiene la tarea asociada a una licitación si existe."""
        ...

    @abstractmethod
    async def lease_next_job(
        self, installation_id: UUID, lease_duration_seconds: int = 300
    ) -> ExtensionFetchJob | None:
        """Arrienda la siguiente tarea disponible usando SKIP LOCKED."""
        ...

    @abstractmethod
    async def complete_job(
        self, job_id: UUID, result_summary: dict[str, Any] | None = None
    ) -> ExtensionFetchJob | None:
        """Marca una tarea como completada exitosamente."""
        ...

    @abstractmethod
    async def fail_job(
        self,
        job_id: UUID,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> ExtensionFetchJob | None:
        """Registra un fallo en la ejecución de la tarea."""
        ...

    @abstractmethod
    async def count_recent_jobs_by_installation(
        self, installation_id: UUID, since: datetime
    ) -> int:
        """Cuenta cuántas tareas completó una instalación desde un instante dado."""
        ...
