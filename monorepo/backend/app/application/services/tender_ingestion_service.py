from abc import ABC, abstractmethod
from datetime import datetime


class ITenderIngestionService(ABC):
    """Interfaz para el servicio de obtención de datos externos.

    La ingesta es de dos fases: primero se registra la metadata de las
    licitaciones detectadas y luego se procesa el detalle de las pendientes.
    Separarlas permite cortar el ciclo sin perder el rastro de lo que falta.
    """

    @abstractmethod
    async def fetch_tenders_metadata(
        self,
        *,
        dias: int | None = None,
        por_publicacion: bool = False,
        estado: str | None = None,
        limite: int | None = None,
    ) -> int:
        """Consulta el listado de la API y guarda la metadata básica.

        Sin argumentos hace lo de siempre: los cambios de las últimas 24 h, que
        es la sincronización diaria. Los parámetros existen para la carga
        inicial, que necesita una ventana ancha, filtrar por estado en el
        servidor y pedir por fecha de publicación en vez de por cambio.

        Devuelve cuántas licitaciones nuevas quedaron encoladas.
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
