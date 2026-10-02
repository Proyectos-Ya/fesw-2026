from abc import ABC, abstractmethod


class ITenderIngestionQueue(ABC):
    """La cola de ingesta (`tender_metadata`), vista desde quien la alimenta."""

    @abstractmethod
    async def reencolar(self, codigos: list[str]) -> int:
        """Devuelve esos códigos a la cola para que el ingest baje su detalle.

        Sirve para licitaciones **ya procesadas**: el listado normal las inserta
        con `ON CONFLICT DO NOTHING` y nunca las vuelve a mirar. Una que ya está
        pendiente queda igual, así que repetir la llamada es seguro. Devuelve
        cuántas filas quedaron pendientes.
        """
        ...
