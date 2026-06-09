from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.models import PointIdsList, PointStruct

from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)


class QdrantSupplierRepository(ISupplierVectorRepository):
    """
    Implementación concreta del repositorio vectorial de proveedores.

    Usa Qdrant como motor de búsqueda vectorial. Todos los detalles
    específicos de Qdrant (colección, formato de puntos, payload)
    están encapsulados aquí — ninguna otra capa los conoce.
    """

    # Nombre de la colección en Qdrant — detalle interno de infraestructura
    _COLLECTION_NAME = "suppliers"

    def __init__(self, client: QdrantClient) -> None:
        self._client = client

    def upsert(self, supplier_id: UUID, embedding: list[float]) -> None:
        """
        Crea o actualiza el punto vectorial del proveedor en Qdrant.

        """
        point = PointStruct(
            id=str(supplier_id),
            vector=embedding,
            # Se guarda el ID del proveedor en el payload
            payload={"supplier_id": str(supplier_id)},
        )

        self._client.upsert(
            collection_name=self._COLLECTION_NAME,
            points=[point],
        )

    def delete(self, supplier_id: UUID) -> None:
        """
        Elimina el punto vectorial del proveedor de Qdrant.
        """
        self._client.delete(
            collection_name=self._COLLECTION_NAME,
            points_selector=PointIdsList(points=[str(supplier_id)]),
        )

    def get_vector(self, supplier_id: UUID) -> list[float] | None:
        """
        Obtiene el vector (embedding) de un proveedor desde Qdrant.
        """
        records = self._client.retrieve(
            collection_name=self._COLLECTION_NAME,
            ids=[str(supplier_id)],
            with_vectors=True,
        )
        if not records:
            return None
        vector_data = records[0].vector
        if isinstance(vector_data, dict):
            return next(iter(vector_data.values()))
        return vector_data

