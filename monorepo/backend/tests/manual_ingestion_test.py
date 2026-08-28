import asyncio
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine

# Importaciones de tu configuración real
from app.config import settings
from app.infrastructure.seeder import seed_database_metadata
from app.infrastructure.services.tenders.mercado_publico_client import MercadoPublicoClient
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.application.use_cases.tender_ingestion_use_case import TenderIngestionUseCase

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
        repository = TenderRepository(session=session)
        use_case = TenderIngestionUseCase(ingestion_service=client, repository=repository)

        # 6. Ejecutar la ingesta usando el flag 'is_dev' de tus settings
        # Si is_dev=True, limitamos a 5 registros para no saturar las llamadas locales
        limit = 5 if settings.is_dev else None
        print(f"[Ingesta] Iniciando fetch a Mercado Público (Limit: {limit})...")
        
        resultado = await use_case.execute(limit=limit)
        
        print("\n==========================================")
        print("RESULTADO FINAL DE LA INGESTA EN POSTGRES:")
        print(resultado)
        print("==========================================\n")

if __name__ == "__main__":
    asyncio.run(run_test())