import asyncio
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine

# Importaciones de tu configuración real
from app.config import settings
from app.infrastructure.seeder import seed_database_metadata
from app.infrastructure.services.tenders.mercado_publico_client import MercadoPublicoClient
from app.infrastructure.services.tenders.tender_ingestion_service import TenderIngestionService
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.application.use_cases.tender_ingestion_use_case import TenderIngestionUseCase
from tests.unit.application.fakes import FakeEmbeddingService, FakeTenderVectorRepository

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
        embedding_service = FakeEmbeddingService()
        tender_vector_repo = FakeTenderVectorRepository()
        
        ingestion_service = TenderIngestionService(
            engine=engine,
            client=client,
            embedding_service=embedding_service,
            qdrant_client=None,
            tender_vector_repo=tender_vector_repo
        )
        
        # 6. Sincronizar metadatos de las licitaciones en la base de datos
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