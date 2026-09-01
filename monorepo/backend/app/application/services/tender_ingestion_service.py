from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.infrastructure.services.tenders.tender_ingestion_service import (
        ResultadoListado,
        ResultadoProceso,
    )


class ITenderIngestionService(ABC):
    """Interfaz para el servicio de obtención de datos externos.

    La ingesta es de dos fases: primero se registra la metadata de las
    licitaciones detectadas y luego se procesa el detalle de las pendientes.
    Separarlas permite cortar el ciclo sin perder el rastro de lo que falta.
    """

    @abstractmethod
    async def fetch_tenders_metadata(
        self,
        *,
        dias: int | None = None,
        por_publicacion: bool = False,
        estado: str | None = None,
        limite: int | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> "ResultadoListado":
        """Consulta el listado de la API y guarda la metadata básica.

        Sin argumentos hace lo de siempre: los cambios de las últimas 24 h, que
        es la sincronización diaria. Los parámetros existen para la carga
        inicial, que necesita una ventana ancha, filtrar por estado en el
        servidor y pedir por fecha de publicación en vez de por cambio.

        `desde`/`hasta` mandan sobre `dias` cuando vienen: es como el cron le
        pasa la ventana que salió del cursor.

        Devuelve cuántas quedaron encoladas y —lo que decide si el cursor
        avanza— si alcanzó a recorrer la ventana entera.
        """
        pass

    @abstractmethod
    async def ultima_sincronizacion(self) -> datetime | None:
        """Cuándo se registró metadata por última vez, o None si no hay ninguna.

        Sirve para decidir si conviene descargar al arrancar. Es una aproximación:
        una sincronización que no encuentra licitaciones nuevas no mueve esta
        fecha, así que puede quedar más vieja de lo que fue la última corrida. El
        error va hacia el lado seguro —se descarga de más, nunca de menos—, y
        evita tener que mantener una tabla de estado solo para esto.
        """
        pass

    @abstractmethod
    async def ventana_a_sincronizar(self) -> tuple[datetime, datetime]:
        """De cuándo a cuándo preguntar, según hasta dónde llegó la última buena.

        Reemplaza a `ultima_sincronizacion` para decidir la ventana. Solo cuentan
        las corridas que alcanzaron a listar su ventana entera.
        """
        pass

    @abstractmethod
    async def registrar_inicio(self, desde: datetime, hasta: datetime) -> UUID:
        """Abre una corrida en estado `running` y devuelve su id."""
        pass

    @abstractmethod
    async def registrar_fin(
        self,
        run_id: UUID,
        *,
        status: str,
        listed: int = 0,
        processed: int = 0,
        failed: int = 0,
    ) -> None:
        """Cierra la corrida. Solo `ok` mueve el cursor."""
        pass

    @abstractmethod
    async def process_unprocessed_tenders(
        self, limite: int | None = None
    ) -> "ResultadoProceso":
        """Procesa un lote de licitaciones pendientes, bajando su detalle.

        Procesa a lo más `limite` y vuelve, en vez de vaciar la cola entera:
        quien llama decide si insiste. Devuelve qué pasó en la pasada, y en
        particular si la cuota se agotó — sin ese dato, el bucle de la carga
        inicial vuelve a intentar y gasta los reintentos del cliente contra una
        cuota que ya no existe.
        """
        pass
