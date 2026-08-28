"""Tareas en segundo plano de las alertas de licitaciones (HdU 08).

Mismo enfoque que `TenderScheduler`: bucles `asyncio` dentro del lifespan de la
aplicación, sin broker ni cron externo. El scheduler solo decide *cuándo*; el
*qué* son las funciones que recibe, cada una responsable de abrir y cerrar su
propia sesión de base de datos.

Como el de ingesta, esto asume **una sola instancia** de la API. Con dos
réplicas ambas escanearían y el usuario recibiría correos duplicados.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from app.shared.datetime_utils import CHILE_TZ

# Cuánto espera el bucle de entrega entre barridos de la cola. Corto a
# propósito: es lo que hace que, al volver el servicio de correo, lo pendiente
# salga en segundos y no en la próxima hora.
DELIVERY_LOOP_SECONDS = 30


class NotificationScheduler:
    def __init__(
        self,
        scan_all: Callable[[], Awaitable[int]],
        dispatch_pending: Callable[[], Awaitable[int]],
        build_digest: Callable[[], Awaitable[int]],
        scan_interval_seconds: int = 300,
        digest_hour: int = 8,
    ) -> None:
        self.scan_all = scan_all
        self.dispatch_pending = dispatch_pending
        self.build_digest = build_digest
        self.scan_interval_seconds = scan_interval_seconds
        self.digest_hour = digest_hour

    async def start_scan_loop(self) -> None:
        """Busca licitaciones compatibles nuevas para cada proveedor."""
        print("[Alertas] Iniciando loop de detección de licitaciones compatibles...")
        while True:
            try:
                nuevos = await self.scan_all()
                if nuevos:
                    print(f"[Alertas] {nuevos} avisos nuevos generados")
            except Exception as e:
                # Un fallo del escaneo no puede matar el bucle: la próxima
                # vuelta vuelve a intentarlo.
                print(f"[Alertas] Error en el escaneo de compatibilidad: {e}")
            await asyncio.sleep(self.scan_interval_seconds)

    async def start_delivery_loop(self) -> None:
        """Vacía la cola de correos pendientes."""
        print(
            f"[Alertas] Iniciando loop de entrega de correos "
            f"(cada {DELIVERY_LOOP_SECONDS} segundos)..."
        )
        while True:
            try:
                enviados = await self.dispatch_pending()
                if enviados:
                    print(f"[Alertas] {enviados} correos de alerta enviados")
            except Exception as e:
                print(f"[Alertas] Error en el envío de correos: {e}")
            await asyncio.sleep(DELIVERY_LOOP_SECONDS)

    async def start_digest_loop(self) -> None:
        """Arma el resumen diario a la hora configurada, en horario de Chile."""
        print(
            f"[Alertas] Iniciando loop de resumen diario "
            f"(a las {self.digest_hour:02d}:00 hora de Chile)..."
        )
        while True:
            # La hora se calcula en zona de Chile, no en UTC: "las 8 de la
            # mañana" tiene que caer de mañana acá.
            ahora = datetime.now(CHILE_TZ)
            proxima = ahora.replace(
                hour=self.digest_hour, minute=0, second=0, microsecond=0
            )
            if proxima <= ahora:
                proxima += timedelta(days=1)
            espera = (proxima - ahora).total_seconds()
            print(f"[Alertas] Próximo resumen diario en {espera / 3600:.2f} horas")
            await asyncio.sleep(espera)

            try:
                encoladas = await self.build_digest()
                if encoladas:
                    print(f"[Alertas] {encoladas} resúmenes diarios encolados")
            except Exception as e:
                print(f"[Alertas] Error al armar el resumen diario: {e}")
