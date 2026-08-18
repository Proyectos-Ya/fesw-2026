from abc import ABC, abstractmethod

# Interfaz para el servicio de obtención de datos externos
class ITenderIngestionService(ABC):
    @abstractmethod
    async def fetch_tenders_metadata(self) -> None:
        """
        Consulta la API externa para obtener el listado reciente de licitaciones y guarda la metadata básica.
        """
        pass

    @abstractmethod
    async def process_unprocessed_tenders(self) -> None:
        """
        Procesa las licitaciones marcadas como no procesadas, descargando su detalle y ejecutando la ingesta.
        """
        pass