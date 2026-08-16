import asyncio
from datetime import datetime, timedelta

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.services.embedding_service import IEmbeddingService
from app.application.services.tender_ingestion_service import ITenderIngestionService
from app.application.use_cases.tender_ingestion_use_case import TenderIngestionUseCase
from app.config import settings
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.shared.datetime_utils import CHILE_TZ


class TenderScheduler:
    def __init__(
        self,
        engine: AsyncEngine,
        ingestion_service: ITenderIngestionService,
        embedding_service: IEmbeddingService,
        qdrant_client: AsyncQdrantClient,
        is_dev: bool = True,
    ):
        self._engine = engine
        self._ingestion_service = ingestion_service
        self._embedding_service = embedding_service
        self._qdrant_client = qdrant_client
        self.is_dev = is_dev

    async def _execute_once(self, limit: int | None) -> None:
        # Sesión nueva por cada ciclo: evita usar una sesión expirada del lifespan.
        async with AsyncSession(self._engine) as session:
            repo = TenderRepository(session)
            tender_vector_repo = QdrantTenderRepository(
                client=self._qdrant_client,
                vector_size=settings.embedding_vector_size,
            )
            use_case = TenderIngestionUseCase(
                ingestion_service=self._ingestion_service,
                repository=repo,
                embedding_service=self._embedding_service,
                tender_vector_repo=tender_vector_repo,
            )
            await use_case.execute(limit=limit)

    async def start_periodic_ingestion(self) -> None:
        limit = 5 if self.is_dev else None
        print("[Scheduler] Ejecutando ingesta inicial de arranque...")
        await self._execute_once(limit)

        while True:
            ahora = datetime.now(CHILE_TZ)
            manana_am = (ahora + timedelta(days=1)).replace(
                hour=2, minute=0, second=0, microsecond=0
            )
            espera = (manana_am - ahora).total_seconds()
            print(
                f"[Scheduler] Próxima ingesta en {espera / 3600:.2f} horas (a las 02:00 AM)"
            )
            await asyncio.sleep(espera)
            print("[Scheduler] Iniciando ingesta programada diaria...")
            await self._execute_once(limit)
