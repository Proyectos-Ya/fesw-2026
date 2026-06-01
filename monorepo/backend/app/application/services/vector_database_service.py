from abc import ABC, abstractmethod

from app.domain.models.vector import Vector


class VectorDatabaseService(ABC):
    """
    Interfaz abstracta para el servicio de base de datos vectorial.

    Vive en la capa de aplicación para que los casos de uso puedan depender
    de esta abstracción sin conocer el detalle de infraestructura (Qdrant).
    """

    @abstractmethod
    async def create_supplier(self, supplier: Vector) -> None:
        """
        Persiste el vector de un proveedor en la base de datos vectorial.

        Args:
            supplier: Vector con el embedding y metadata del proveedor.
        """
        ...