from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    MultiVectorComparator,
    MultiVectorConfig,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from app.application.repositories.tender_item_vector_repository import (
    ITenderItemVectorRepository,
)
from app.application.schemas.tender_schema import TenderFilterCriteria
from app.infrastructure.repositories.qdrant_tender_filters import (
    build_filter,
    ensure_payload_indexes,
)


class QdrantTenderItemVectorRepository(ITenderItemVectorRepository):
    """
    Implementación del repositorio de vectores de partidas usando Qdrant.

    Guarda UN punto por licitación con un único vector nombrado 'items' de tipo
    multivector: cada partida es un vector del multivector. Vive en su propia
    colección porque agregar un vector nombrado a una colección existente
    ('tenders') obligaría a recrearla.

    El punto lleva el mismo payload que el de 'tenders' y la colección tiene los
    mismos índices de payload, para que la búsqueda por keywords pueda pre-filtrar
    con los mismos criterios.
    """

    _COLLECTION_NAME = "tender_items"
    _VECTOR_NAME = "items"

    # Tamaño de lote de `retrieve`: acota el largo de la petición y la respuesta
    # cuando se piden los vectores de muchas licitaciones a la vez.
    _RETRIEVE_BATCH_SIZE = 256

    def __init__(
        self,
        client: AsyncQdrantClient,
        vector_size: int,
    ) -> None:
        self._client = client
        self._vector_size = vector_size

    async def ensure_collection(self) -> None:
        """
        Crea la colección en Qdrant si no existe, configurando el multivector
        nombrado 'items' con comparador MAX_SIM, y asegura los índices de payload
        de los campos por los que se filtra.
        """
        result = await self._client.get_collections()
        existing = {c.name for c in result.collections}
        if self._COLLECTION_NAME not in existing:
            await self._client.create_collection(
                collection_name=self._COLLECTION_NAME,
                vectors_config={
                    self._VECTOR_NAME: VectorParams(
                        size=self._vector_size,
                        distance=Distance.COSINE,
                        multivector_config=MultiVectorConfig(
                            comparator=MultiVectorComparator.MAX_SIM
                        ),
                    )
                },
            )

        # Fuera del `if` a propósito: la colección ya existe en los entornos que
        # corrieron el backfill de vectores, y a esos hay que agregarles los
        # índices sin recrearla. Qdrant los trata de forma idempotente.
        await ensure_payload_indexes(self._client, self._COLLECTION_NAME)

    async def upsert(
        self,
        tender_id: UUID,
        item_vectors: list[list[float]],
        payload: dict | None = None,
    ) -> None:
        """
        Reemplaza los vectores de partidas de una licitación, y su payload.

        Con una lista vacía elimina el punto: Qdrant no acepta un multivector sin
        vectores, y una licitación sin partidas no debe conservar los de una
        versión anterior.
        """
        if not item_vectors:
            await self.delete(tender_id)
            return

        # Mismo id -> Qdrant sobrescribe el punto entero, así que el reemplazo es
        # total y no queda ninguna partida vieja. Vale también para el payload:
        # el que ya tuviera el punto se descarta, por eso quien llama entrega el
        # completo.
        point = PointStruct(
            id=str(tender_id),
            vector={self._VECTOR_NAME: item_vectors},
            payload=payload,
        )
        await self._client.upsert(
            collection_name=self._COLLECTION_NAME,
            points=[point],
        )

    async def set_payload(self, tender_id: UUID, payload: dict) -> None:
        """
        Actualiza campos del payload de una licitación sin tocar sus vectores.

        Comprueba antes que el punto exista: no se apoya en cómo trate Qdrant un
        `set_payload` sobre un id ausente, y así el caso "licitación aún sin
        backfill de partidas" es un no-op explícito en vez de un error posible en
        plena ingesta.
        """
        existentes = await self._client.retrieve(
            collection_name=self._COLLECTION_NAME,
            ids=[str(tender_id)],
            with_vectors=False,
            with_payload=False,
        )
        if not existentes:
            return

        await self._client.set_payload(
            collection_name=self._COLLECTION_NAME,
            payload=payload,
            points=[str(tender_id)],
        )

    async def get_many(self, tender_ids: list[UUID]) -> dict[UUID, list[list[float]]]:
        """
        Recupera los vectores de partidas de las licitaciones pedidas, en lotes.

        Los ids que no existen en Qdrant no aparecen en el resultado.
        """
        # `dict.fromkeys` quita repetidos conservando el orden.
        ids = [str(tender_id) for tender_id in dict.fromkeys(tender_ids)]

        vectors_by_tender: dict[UUID, list[list[float]]] = {}
        for start in range(0, len(ids), self._RETRIEVE_BATCH_SIZE):
            batch = ids[start : start + self._RETRIEVE_BATCH_SIZE]
            records = await self._client.retrieve(
                collection_name=self._COLLECTION_NAME,
                ids=batch,
                with_vectors=[self._VECTOR_NAME],
                with_payload=False,
            )
            for record in records:
                found_id = self._as_uuid(record.id)
                vectors = self._extract_item_vectors(record.vector)
                if vectors:
                    vectors_by_tender[found_id] = vectors
        return vectors_by_tender

    async def delete(self, tender_id: UUID) -> None:
        """
        Elimina el punto correspondiente a la licitación en Qdrant.
        """
        await self._client.delete(
            collection_name=self._COLLECTION_NAME,
            points_selector=PointIdsList(points=[str(tender_id)]),
        )

    async def search_by_keywords(
        self,
        keyword_vectors: list[list[float]],
        limit: int,
        criteria: TenderFilterCriteria | None = None,
    ) -> list[tuple[UUID, float]]:
        """
        Busca las licitaciones cuyas partidas mejor calzan con las keywords.

        Una consulta con multivector contra el multivector 'items' (MAX_SIM) que
        Qdrant puntúa como la suma, por cada vector de la consulta, de su mejor
        producto punto contra los vectores del punto. Con vectores normalizados
        (los de coseno lo están) es Σ_keywords max_partidas coseno.
        """
        # Qdrant rechaza un multivector de consulta vacío.
        if not keyword_vectors:
            return []

        response = await self._client.query_points(
            collection_name=self._COLLECTION_NAME,
            query=keyword_vectors,
            using=self._VECTOR_NAME,
            query_filter=build_filter(criteria),
            limit=limit,
            # El payload solo sirve para filtrar dentro de Qdrant; quien llama
            # recupera la licitación completa por id desde SQL.
            with_payload=False,
        )
        return [
            (self._as_uuid(point.id), point.score) for point in response.points
        ]

    @staticmethod
    def _as_uuid(point_id: object) -> UUID:
        """Convierte el id de un punto a UUID.

        Los puntos se insertan siempre con `str(uuid)`; un id entero indicaría
        datos escritos por otra ruta y no es representable como UUID.
        """
        if not isinstance(point_id, str):
            raise ValueError(
                f"ID de punto inesperado en Qdrant: {point_id!r}. "
                f"Se esperaba un UUID en formato string."
            )
        return UUID(point_id)

    def _extract_item_vectors(self, vector: object) -> list[list[float]] | None:
        """Saca el multivector 'items' del vector de un punto, si lo tiene."""
        if not isinstance(vector, dict):
            return None
        items = vector.get(self._VECTOR_NAME)
        return items or None
