from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.export_job import ExportJob


class IExportJobRepository(ABC):
    @abstractmethod
    async def save(self, job: ExportJob) -> ExportJob:
        """Crea el trabajo o actualiza el existente con el mismo id."""

    @abstractmethod
    async def get(self, job_id: UUID, with_content: bool = True) -> ExportJob | None:
        """Con `with_content=False` no trae el archivo: alcanza para consultar el estado."""


    @abstractmethod
    async def fail_stale(self, now: datetime, created_before: datetime) -> int:
        """Marca fallidos los que siguen en proceso y se crearon antes de `created_before`.

        El corte evita tocar lo que una instancia anterior, todavía viva durante un
        despliegue, está generando en este momento.
        """

    @abstractmethod
    async def purge_expired(self, now: datetime) -> int:
        """Borra el contenido de los archivos vencidos; la fila queda como registro."""
