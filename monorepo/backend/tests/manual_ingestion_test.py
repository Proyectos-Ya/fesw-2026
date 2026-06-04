import asyncio
from app.infrastructure.services.tenders.mercado_publico_client import MercadoPublicoClient
from app.infrastructure.repositories.mock_tenders_repository import MockTendersRepository
from app.application.use_cases.tender_ingestion_use_case import TenderIngestionUseCase
from app.config import settings

async def main():
    print("Iniciando prueba de ingesta...")
    
    # Asegurarse de tener MERCADO_PUBLICO_API_KEY en tu .env
    client = MercadoPublicoClient(api_key=settings.mercado_publico_api_key)
    repo = MockTendersRepository()
    use_case = TenderIngestionUseCase(client, repo)
    
    # límite de 5 para no saturar
    result = await use_case.execute(limit=5)

    print(f"\n Resultado: {result}")
    print(f" Licitaciones en el Mock DB: {len(repo.storage)}")

if __name__ == "__main__":
    asyncio.run(main())