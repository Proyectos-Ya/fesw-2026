import asyncio
from datetime import datetime, timedelta

from app.application.services.tender_ingestion_service import ITenderIngestionService
from app.shared.datetime_utils import CHILE_TZ


# Coordinador de tareas programadas en segundo plano
class TenderScheduler:
    def __init__(self, ingestion_service: ITenderIngestionService):
        self.ingestion_service = ingestion_service

    # Tarea en segundo plano para buscar metadatos de licitaciones (cada 24 horas a las 2 AM o al iniciar)
    async def start_metadata_loop(self) -> None:
        print("[Scheduler] Iniciando loop de descarga de metadatos...")
        try:
            await self.ingestion_service.fetch_tenders_metadata()
        except Exception as e:
            print(f"[Scheduler] Error en la descarga inicial de metadatos: {e}")

        while True:
            # La hora se calcula en horario de Chile: las 02:00 tienen que caer de
            # noche acá, no en UTC.
            ahora = datetime.now(CHILE_TZ)
            manana_am = (ahora + timedelta(days=1)).replace(
                hour=2, minute=0, second=0, microsecond=0
            )
            espera = (manana_am - ahora).total_seconds()
            print(
                f"[Scheduler] Próxima descarga de metadatos en {espera / 3600:.2f} horas (a las 02:00 AM)"
            )
            await asyncio.sleep(espera)

            print("[Scheduler] Iniciando descarga programada diaria de metadatos...")
            try:
                await self.ingestion_service.fetch_tenders_metadata()
            except Exception as e:
                print(f"[Scheduler] Error en la descarga diaria de metadatos: {e}")

    # Tarea en segundo plano para procesar detalles de licitaciones pendientes cada 2 segundos
    async def start_processing_loop(self) -> None:
        print(
            "[Scheduler] Iniciando loop de procesamiento de detalles crudos (cada 2 segundos)..."
        )
        while True:
            try:
                await self.ingestion_service.process_unprocessed_tenders()
            except Exception as e:
                print(f"[Scheduler] Error en bucle de procesamiento de detalles: {e}")
            await asyncio.sleep(2)
