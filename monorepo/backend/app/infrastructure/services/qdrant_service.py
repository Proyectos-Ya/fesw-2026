import logging

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.application.services.vector_database_service import VectorDatabaseService
from app.domain.models.vector import Vector

logger = logging.getLogger(__name__)

# Nombre fijo de la colección donde se guardan los embeddings de proveedores
PROVIDERS_COLLECTION = "providers"

# Dimensiones del modelo BGE-M3 (usado para generar los embeddings en ProyectosYA)
BGE_M3_VECTOR_SIZE = 1024


class QdrantService(VectorDatabaseService):
    """
    Implementación concreta del servicio de base de datos vectorial usando Qdrant.

    Qdrant corre en Docker en el puerto 6333.
    La colección 'providers' se crea automáticamente si no existe.
    """

    def __init__(self, url: str, api_key: str | None = None) -> None:
        """
        Inicializa el cliente asíncrono de Qdrant.

        Args:
            url: URL del contenedor Qdrant (ej: http://qdrant:6333 en Docker Compose).
            api_key: Clave de API opcional para entornos con autenticación.
        """
        self._client = AsyncQdrantClient(url=url, api_key=api_key)

    async def create_provider(self, provider: Vector) -> None:
        """
        Persiste el vector de un proveedor en la colección 'providers' de Qdrant.

        Crea la colección automáticamente si todavía no existe.
        Usa upsert para ser idempotente: si el ID ya existe, lo actualiza.

        Args:
            provider: Vector con el embedding y metadata del proveedor.
        """
        # Garantiza que la colección exista antes de insertar
        await self._ensure_providers_collection()

        # Construye el punto (unidad de dato en Qdrant)
        point = PointStruct(
            id=str(provider.id),
            vector=provider.embedding,
            payload=provider.payload.to_dict(),
        )

        # Upsert: inserta si no existe, actualiza si ya existe
        await self._client.upsert(
            collection_name=PROVIDERS_COLLECTION,
            points=[point],
            wait=True,  # Espera confirmación de escritura antes de retornar
        )

        logger.info(
            "Proveedor guardado en Qdrant | id=%s | company=%s",
            provider.id,
            provider.payload.company_name,
        )

    async def _ensure_providers_collection(self) -> None:
        """
        Crea la colección 'providers' si aún no existe en Qdrant.

        Configuración:
        - Tamaño del vector: 1024 (dimensiones de BGE-M3)
        - Métrica de distancia: Coseno → ideal para similitud semántica
        """
        exists = await self._client.collection_exists(PROVIDERS_COLLECTION)
        if exists:
            return

        logger.info("Creando colección '%s' en Qdrant...", PROVIDERS_COLLECTION)

        await self._client.create_collection(
            collection_name=PROVIDERS_COLLECTION,
            vectors_config=VectorParams(
                size=BGE_M3_VECTOR_SIZE,
                distance=Distance.COSINE,  # Similitud coseno para matching semántico
            ),
        )

        logger.info("Colección '%s' creada exitosamente.", PROVIDERS_COLLECTION)