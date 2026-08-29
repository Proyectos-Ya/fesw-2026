import asyncio
from datetime import datetime, timedelta

from app.application.services.tender_ingestion_service import ITenderIngestionService
from app.shared.datetime_utils import CHILE_TZ

# Hora local de Chile a la que corre la sincronización diaria. De noche a
# propósito: la API de Mercado Público responde mejor y a nadie le afecta que
# tarde.
HORA_SINCRONIZACION = 2

# Cuán vieja tiene que estar la metadata para justificar una descarga al
# arrancar. Con un valor alto, un despliegue tras una caída larga se queda con
# datos rancios hasta las 02:00; con uno bajo, una tanda de despliegues seguidos
# vuelve a golpear la API una y otra vez. Seis horas deja pasar como mucho cuatro
# descargas al día en el peor caso, y cubre el caso normal —desplegar varias
# veces en una tarde— con una sola.
VENTANA_FRESCURA = timedelta(hours=6)


def _proxima_ejecucion(ahora: datetime) -> datetime:
    """Siguiente ocurrencia de HORA_SINCRONIZACION, hoy o mañana.

    Se fija la hora sobre el día de hoy y solo se salta a mañana si ya pasó. La
    versión anterior sumaba un día *antes* de fijar la hora, así que arrancando a
    las 00:30 esperaba 25,5 horas en vez de 1,5.
    """
    proxima = ahora.replace(
        hour=HORA_SINCRONIZACION, minute=0, second=0, microsecond=0
    )
    if proxima <= ahora:
        proxima += timedelta(days=1)
    return proxima


def _hace_falta_sincronizar(ultima: datetime | None, ahora: datetime) -> bool:
    """Si conviene descargar metadata al arrancar, según lo fresca que esté.

    Sin esto, cada arranque del proceso disparaba una descarga completa. En un
    entorno gestionado eso es cada despliegue y cada reinicio, y en un bucle de
    caídas se convierte en un martilleo contra la API de Mercado Público.
    """
    if ultima is None:
        return True
    return (ahora - ultima) >= VENTANA_FRESCURA


# Coordinador de tareas programadas en segundo plano
class TenderScheduler:
    def __init__(self, ingestion_service: ITenderIngestionService):
        self.ingestion_service = ingestion_service

    async def start_metadata_loop(self) -> None:
        """Sincroniza la metadata al arrancar si hace falta, y luego a diario."""
        print("[Scheduler] Iniciando loop de descarga de metadatos...")

        ahora = datetime.now(CHILE_TZ)
        try:
            ultima = await self.ingestion_service.ultima_sincronizacion()
        except Exception as e:
            # Si no se puede saber cuán fresca está, se sincroniza: quedarse con
            # datos viejos es peor que una descarga de más.
            print(f"[Scheduler] No se pudo consultar la última sincronización: {e}")
            ultima = None

        if _hace_falta_sincronizar(ultima, ahora):
            try:
                await self.ingestion_service.fetch_tenders_metadata()
            except Exception as e:
                print(f"[Scheduler] Error en la descarga inicial de metadatos: {e}")
        else:
            antiguedad = (ahora - ultima).total_seconds() / 3600  # type: ignore[operator]
            print(
                f"[Scheduler] Metadata sincronizada hace {antiguedad:.1f} h, "
                "por debajo del umbral: no se descarga al arrancar."
            )

        while True:
            ahora = datetime.now(CHILE_TZ)
            espera = (_proxima_ejecucion(ahora) - ahora).total_seconds()
            print(
                f"[Scheduler] Próxima descarga de metadatos en {espera / 3600:.2f} "
                f"horas (a las {HORA_SINCRONIZACION:02d}:00)"
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
