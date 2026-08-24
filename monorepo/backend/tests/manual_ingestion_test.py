import asyncio

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# Importaciones de tu configuración real
from app.config import settings
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.seeder import seed_database_metadata
from app.infrastructure.services.bge_m3_embedding_service import BgeM3EmbeddingService
from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)


async def run_test():
    print("[Test] Inicializando entorno de prueba relacional para ProyectosYA...")

    # 1. Crear el motor asíncrono dinámicamente usando tu property 'database_url'
    # Usamos echo=True para ver en la consola las queries SQL reales que se ejecutan
    engine = create_async_engine(settings.database_url, echo=True)
    print(f"[DB] Conectado a URL: {settings.database_url}")

    # 2. Crear las tablas físicamente en el contenedor de Docker si no existen
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    print("[DB] Tablas creadas/verificadas con éxito en PostgreSQL (Docker).")

    # 3. Abrir la sesión asíncrona para interactuar con los modelos
    async with AsyncSession(engine) as session:
        # 4. Sembrar la metadata obligatoria (Estados y Regiones de Chile)
        print("[Seeder] Comprobando y sembrando metadata inicial...")
        await seed_database_metadata(session)
        print("[Seeder] Base de datos sembrada y lista.")

        # 5. Instanciar tus servicios e inyectar las dependencias reales
        client = MercadoPublicoClient(api_key=settings.mercado_publico_api_key)
        embedding_service = BgeM3EmbeddingService(model_name=settings.embedding_model)
        tender_vector_repo = QdrantTenderRepository(
            client=AsyncQdrantClient(url=settings.qdrant_url),
            vector_size=settings.embedding_vector_size,
        )
        # Este script corre standalone, sin el lifespan de la API que normalmente
        # crea la colección. Sin esto, cada upsert falla y el caso de uso se traga
        # el error: la licitación queda en Postgres sin vector y nunca se reintenta.
        await tender_vector_repo.ensure_collection()

        ingestion_service = TenderIngestionService(
            engine=engine,
            client=client,
            embedding_service=embedding_service,
            tender_vector_repo=tender_vector_repo,
        )

        # 6. Sincronizar metadatos de las licitaciones en la base de datos.
        # Cuántas se traen lo define MERCADOPUBLICO_FETCHING_LIMIT en el .env.
        print("[Ingesta] Descargando y sincronizando metadatos...")
        await ingestion_service.fetch_tenders_metadata()

        # 7. Procesar los detalles pendientes de las licitaciones no procesadas
        print("[Ingesta] Descargando detalles y procesando licitaciones pendientes...")
        await ingestion_service.process_unprocessed_tenders()

        print("\n==========================================")
        print("INGESTA EN DOS FASES COMPLETADA.")
        print("==========================================\n")


if __name__ == "__main__":
    asyncio.run(run_test())
