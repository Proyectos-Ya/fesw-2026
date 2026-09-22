from typing import cast
from uuid import UUID

from qdrant_client import AsyncQdrantClient
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

    Usa el cliente asíncrono, igual que `QdrantTenderRepository`. Con el
    síncrono cada escritura o lectura detenía el event loop mientras esperaba
    la red, y con él todas las demás peticiones del servidor.
    """

    # Nombre de la colección en Qdrant — detalle interno de infraestructura
    _COLLECTION_NAME = "suppliers"

    def __init__(self, client: AsyncQdrantClient) -> None:
        self._client = client

    async def upsert(self, supplier_id: UUID, embedding: list[float]) -> None:
        """
        Crea o actualiza el punto vectorial del proveedor en Qdrant.

        """
        point = PointStruct(
            id=str(supplier_id),
            vector=embedding,
            # Se guarda el ID del proveedor en el payload
            payload={"supplier_id": str(supplier_id)},
        )

        await self._client.upsert(
            collection_name=self._COLLECTION_NAME,
            points=[point],
        )

    async def delete(self, supplier_id: UUID) -> None:
        """
        Elimina el punto vectorial del proveedor de Qdrant.
        """
        await self._client.delete(
            collection_name=self._COLLECTION_NAME,
            points_selector=PointIdsList(points=[str(supplier_id)]),
        )

    async def get_vector(self, supplier_id: UUID) -> list[float] | None:
        """
        Obtiene el vector (embedding) de un proveedor desde Qdrant.
        """
        records = await self._client.retrieve(
            collection_name=self._COLLECTION_NAME,
            ids=[str(supplier_id)],
            with_vectors=True,
        )
        if not records:
            return None
        vector_data = records[0].vector
        if isinstance(vector_data, dict):
            vector_data = next(iter(vector_data.values()), None)
        if vector_data is None:
            return None

        # Qdrant también puede devolver multivectores o vectores dispersos; el
        # contrato de este repositorio es un vector denso simple.
        if not isinstance(vector_data, list) or any(
            not isinstance(value, float) for value in vector_data
        ):
            raise ValueError(
                f"Formato de vector inesperado para el proveedor {supplier_id}: "
                f"se esperaba un vector denso de floats."
            )
        # El isinstance dentro del generador no estrecha el tipo de la lista.
        return cast(list[float], vector_data)
