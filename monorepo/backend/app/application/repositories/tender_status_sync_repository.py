from abc import ABC, abstractmethod

from app.domain.models.cambio_estado import CambioDeEstado, LicitacionConocida


class ITenderStatusSyncRepository(ABC):
    """Lo que el cron de estados necesita de Postgres, y nada más.

    Interfaz aparte de `ITenderRepository` a propósito: esa ya es ancha, y cada
    método nuevo ahí obliga a tocar todos sus dobles de prueba. `TenderRepository`
    implementa las dos.
    """

    @abstractmethod
    async def get_known_by_codes(
        self, codes: list[str]
    ) -> dict[str, LicitacionConocida]:
        """Las licitaciones guardadas de esos códigos, indexadas por código.

        Los códigos que no existen simplemente no aparecen.
        """
        ...

    @abstractmethod
    async def get_or_create_status(self, status_id: int, code: str) -> int:
        """Asegura la fila de `tender_status` (clave foránea de `tender`)."""
        ...

    @abstractmethod
    async def overwrite_statuses(self, cambios: list[CambioDeEstado]) -> int:
        """Escribe estado y cierre de esas licitaciones, en lote.

        Solo toca las filas donde alguno de los dos difiere, así `updated_at` no
        se mueve sin motivo (ver `TenderIngestionUseCase._actualizar`). Devuelve
        cuántas cambiaron de verdad.
        """
        ...
