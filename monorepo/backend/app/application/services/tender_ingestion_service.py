from abc import ABC, abstractmethod
from datetime import datetime


class ITenderIngestionService(ABC):
    """Interfaz para el servicio de obtención de datos externos.

    La ingesta es de dos fases: primero se registra la metadata de las
    licitaciones detectadas y luego se procesa el detalle de las pendientes.
    Separarlas permite cortar el ciclo sin perder el rastro de lo que falta.
    """

    @abstractmethod
    async def fetch_tenders_metadata(self) -> None:
        """
        Consulta la API externa para obtener el listado reciente de licitaciones
        y guarda la metadata básica.
        """
        pass

    @abstractmethod
    async def ultima_sincronizacion(self) -> datetime | None:
        """Cuándo se registró metadata por última vez, o None si no hay ninguna.

        Sirve para decidir si conviene descargar al arrancar. Es una aproximación:
        una sincronización que no encuentra licitaciones nuevas no mueve esta
        fecha, así que puede quedar más vieja de lo que fue la última corrida. El
        error va hacia el lado seguro —se descarga de más, nunca de menos—, y
        evita tener que mantener una tabla de estado solo para esto.
        """
        pass

    @abstractmethod
    async def process_unprocessed_tenders(self) -> None:
        """
        Procesa las licitaciones marcadas como no procesadas, descargando su
        detalle y ejecutando la ingesta.
        """
        pass
