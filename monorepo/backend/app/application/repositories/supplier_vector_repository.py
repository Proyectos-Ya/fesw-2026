from abc import ABC, abstractmethod
from uuid import UUID


class ISupplierVectorRepository(ABC):
    """
    Interfaz abstracta para el repositorio vectorial de proveedores.

    Define el contrato para almacenar y eliminar representaciones
    vectoriales de proveedores. La implementación concreta decide
    qué motor de base de datos vectorial utilizar (ej: Qdrant).
    """

    @abstractmethod
    def upsert(self, supplier_id: UUID, embedding: list[float]) -> None:
        """
        Crea o actualiza el vector de un proveedor en la base vectorial.

        Si ya existe un vector para el supplier_id dado, lo reemplaza.
        Si no existe, lo crea. El embedding debe tener exactamente
        1024 dimensiones (generado por BGE-M3).
        """
        ...

    @abstractmethod
    def delete(self, supplier_id: UUID) -> None:
        """
        Elimina el vector asociado a un proveedor.

        Debe llamarse cuando un proveedor es eliminado del sistema
        para mantener consistencia entre PostgreSQL y la base vectorial.

        """
        ...

    @abstractmethod
    def get_vector(self, supplier_id: UUID) -> list[float] | None:
        """
        Obtiene el vector (embedding) de un proveedor dado su ID.

        Devuelve una lista de floats con el embedding si existe, o None si no.
        """
        ...
