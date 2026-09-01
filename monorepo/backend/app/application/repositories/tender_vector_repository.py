from abc import ABC, abstractmethod
from uuid import UUID

from app.application.schemas.tender_schema import TenderFilterCriteria


class ITenderVectorRepository(ABC):
    """
    Interfaz abstracta para el repositorio vectorial de licitaciones (tenders).
    """

    @abstractmethod
    async def ensure_collection(self) -> None:
        """
        Asegura que la colección de licitaciones exista en Qdrant, con los
        índices de payload de los campos por los que se filtra.
        """
        ...

    @abstractmethod
    async def upsert(
        self,
        tender_id: UUID,
        embedding: list[float],
        payload: dict,
    ) -> None:
        """
        Crea o actualiza el vector nombrado (named vector) de una licitación en Qdrant.
        """
        ...

    @abstractmethod
    async def set_payload(self, tender_id: UUID, payload: dict) -> None:
        """Actualiza campos del payload sin tocar el vector.

        Es la operación barata: cambiar el estado o la fecha de cierre de una
        licitación no cambia lo que pide, así que recalcular el embedding sería
        pagar una inferencia para escribir el mismo vector.

        Actualiza solo las claves entregadas; las que no vienen se conservan.
        """
        ...

    @abstractmethod
    async def delete(self, tender_id: UUID) -> None:
        """
        Elimina el vector de una licitación en Qdrant.
        """
        ...

    @abstractmethod
    async def search_by_vector(
        self,
        vector: list[float],
        limit: int,
        offset: int = 0,
        criteria: TenderFilterCriteria | None = None,
    ) -> list[tuple[UUID, float]]:
        """
        Busca las licitaciones más afines a un vector, aplicando los criterios
        como pre-filtro durante el recorrido.

        Una sola operación para tres usos, que solo difieren en de dónde sale el
        vector:

        - dashboard de recomendaciones: vector del proveedor, filtro de estado
        - buscador con texto: vector de la consulta, filtros del usuario
        - buscador sin texto: vector del proveedor, filtros del usuario

        `offset` permite pedir el siguiente bloque cuando el usuario agota el
        primero. Su costo crece con la profundidad —Qdrant recupera y ordena
        `offset + limit` para descartar los primeros—, así que sirve para
        recorrer un catálogo acotado, no para paginar indefinidamente.

        Devuelve una lista de tuplas (tender_id, similarity_score).
        """
        ...

    @abstractmethod
    async def count(self, criteria: TenderFilterCriteria | None = None) -> int:
        """
        Cuenta cuántas licitaciones cumplen los criterios, sin considerar
        similitud ni corte.

        Es el total de coincidencias que ve el usuario: depende solo del conjunto
        elegible, así que no cambia entre páginas.
        """
        ...
