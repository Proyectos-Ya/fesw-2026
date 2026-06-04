import asyncio
from datetime import datetime, timedelta
from app.application.use_cases.tender_ingestion_use_case import TenderIngestionUseCase

class TenderScheduler:
    def __init__(self, use_case: TenderIngestionUseCase, is_dev: bool = True):
        self.use_case = use_case
        self.is_dev = is_dev

    async def start_periodic_ingestion(self) -> None:
        # Loop infinito que ejecuta la ingesta al inicio y luego cada día a las 2am.
        # Caso en caso de estar desarrollando, solo traer 5 licitaciones para pruebas
        # evitando saturación en BD
        print("[Scheduler] Ejecutando ingesta inicial de arranque...")
        limit = 5 if self.is_dev else None
        await self.use_case.execute(limit=limit)

        # Esperar hasta las 2am
        while True:
            ahora = datetime.now()
            manana_am = (ahora + timedelta(days=1)).replace(hour=2, minute=0, second=0, microsecond=0)
            espera = (manana_am - ahora).total_seconds()

            print(f"[Scheduler] Próxima ingesta en {espera/3600:.2f} horas (a las 02:00 AM)")
            await asyncio.sleep(espera)

            print("[Scheduler] Iniciando ingesta programada diaria...")
            await self.use_case.execute(limit=limit)