import logging
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.application.services.vector_database_service import VectorDatabaseService
from app.domain.models.vector import Vector

logger = logging.getLogger(__name__)

# Nombre fijo de la colección donde se guardan los embeddings de proveedores
SUPPLIER_COLLECTION = "suppliers"

# Dimensiones del modelo BGE-M3 (usado para generar los embeddings en ProyectosYA)
BGE_M3_VECTOR_SIZE = 1024


class QdrantService(VectorDatabaseService):
    """
    Implementación concreta del servicio de base de datos vectorial usando Qdrant.

    Qdrant corre en Docker en el puerto 6333.
    La colección 'suppliers' se crea automáticamente si no existe.
    """

    def __init__(self, url: str, api_key: str | None = None) -> None:
        """
        Inicializa el cliente asíncrono de Qdrant.

        Args:
            url: URL del contenedor Qdrant (ej: http://qdrant:6333 en Docker Compose).
            api_key: Clave de API opcional para entornos con autenticación.
        """
        self._client = AsyncQdrantClient(url=url, api_key=api_key)

    async def create_supplier(self, supplier: Vector) -> None:
        """
        Persiste el vector de un proveedor en la colección 'suppliers' de Qdrant.

        Crea la colección automáticamente si todavía no existe.
        Usa upsert para ser idempotente: si el ID ya existe, lo actualiza.

        Args:
            supplier: Vector con el embedding y metadata del proveedor.
        """
        # Garantiza que la colección exista antes de insertar
        await self._ensure_suppliers_collection()

        # Construye el punto (unidad de dato en Qdrant)
        point = PointStruct(
            id=str(supplier.id),
            vector=supplier.embedding,
            payload=supplier.payload.to_dict(),
        )

        # Upsert: inserta si no existe, actualiza si ya existe
        await self._client.upsert(
            collection_name=SUPPLIER_COLLECTION,
            points=[point],
            wait=True,  # Espera confirmación de escritura antes de retornar
        )

        logger.info(
            "Proveedor guardado en Qdrant | id=%s | company=%s",
            supplier.id,
            supplier.payload.company_name,
        )
    async def initialize_collections(self) -> None:
        """
        Inicializa todas las colecciones necesarias en Qdrant.
        """
        await self._ensure_suppliers_collection()

    async def _ensure_suppliers_collection(self) -> None:
        """
        Crea la colección 'suppliers' si aún no existe en Qdrant.

        Configuración:
        - Tamaño del vector: 1024 (dimensiones de BGE-M3)
        - Métrica de distancia: Coseno → ideal para similitud semántica
        """
        exists = await self._client.collection_exists(SUPPLIER_COLLECTION)
        if exists:
            return

        logger.info("Creando colección '%s' en Qdrant...", SUPPLIER_COLLECTION)

        await self._client.create_collection(
            collection_name=SUPPLIER_COLLECTION,
            vectors_config=VectorParams(
                size=BGE_M3_VECTOR_SIZE,
                distance=Distance.COSINE,  # Similitud coseno para matching semántico
            ),
        )

        logger.info("Colección '%s' creada exitosamente.", SUPPLIER_COLLECTION)

   