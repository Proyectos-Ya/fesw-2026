from abc import ABC, abstractmethod


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
    async def process_unprocessed_tenders(self) -> None:
        """
        Procesa las licitaciones marcadas como no procesadas, descargando su
        detalle y ejecutando la ingesta.
        """
        pass
