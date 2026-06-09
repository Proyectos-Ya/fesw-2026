from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender


class IWeightingService(ABC):
    """
    Interfaz abstracta para el servicio de ponderación de campos.
    """

    @abstractmethod
    def calculate_scores(
        self,
        candidates: list[tuple[Tender, float]],
        supplier: Supplier,
    ) -> list[tuple[UUID, float]]:
        """
        Pondera los scores de similitud de las licitaciones (candidates) usando
        la información detallada de los campos del proveedor.

        Devuelve un listado de tuplas (tender_id, score_final) ordenadas de mayor a menor.
        """
        ...
