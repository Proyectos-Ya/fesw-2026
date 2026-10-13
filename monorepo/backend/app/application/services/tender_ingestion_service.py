from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.infrastructure.services.tenders.tender_ingestion_service import (
        ResultadoListado,
        ResultadoProceso,
    )


class ModoCola(StrEnum):
    """Qué parte de la cola de ingesta toma una pasada (plan 305)."""

    # Todo lo pendiente, como antes de los modos. Lo usa la carga inicial.
    TODAS = "todas"
    # Lo que nunca falló, con las `nueva` antes que las `actualizar`. Lo que
    # corre cada 2 h: una que falla queda para la noche.
    NUEVAS = "nuevas"
    # Lo que ya falló antes de que empezara la corrida. Lo que corre de noche,
    # con un reintento nocturno por fila.
    REINTENTOS = "reintentos"


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
    async def ventana_a_sincronizar(self) -> tuple[datetime, datetime]:
        """De cuándo a cuándo preguntar, según hasta dónde llegó la última buena.

        Solo cuentan las corridas que alcanzaron a listar su ventana entera.
        """
        pass

    @abstractmethod
    async def registrar_inicio(
        self, desde: datetime, hasta: datetime, *, kind: str = "tramo"
    ) -> UUID:
        """Abre una corrida en estado `running` y devuelve su id.

        `kind` (plan 305): `tramo` para cada tramo listado de la nocturna, que
        son los únicos que mueven el cursor; `nocturna` para la corrida nocturna
        entera y `frecuente` para la que solo vacía la cola.
        """
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
        requests: int | None = None,
    ) -> None:
        """Cierra la corrida. Solo un tramo `ok` mueve el cursor."""
        pass

    @abstractmethod
    async def cerrar_corridas_colgadas(self, antes_de: datetime) -> int:
        """Pasa a `failed` las corridas en `running` que empezaron antes del corte.

        Una corrida cuyo proceso murió —un Remove en Railway, un OOM— queda en
        `running` para siempre. Devuelve cuántas cerró.
        """
        pass

    @abstractmethod
    async def hay_corrida_en_curso(self) -> bool:
        """Si alguna corrida figura en `running`."""
        pass

    @abstractmethod
    async def process_unprocessed_tenders(
        self,
        limite: int | None = None,
        *,
        modo: ModoCola = ModoCola.TODAS,
        antes_de: datetime | None = None,
    ) -> "ResultadoProceso":
        """Procesa un lote de licitaciones pendientes, bajando su detalle.

        `modo` elige qué parte de la cola. `antes_de` acota `REINTENTOS` a lo
        que falló antes de ese momento, normalmente el inicio de la corrida.

        Procesa a lo más `limite` y vuelve, en vez de vaciar la cola entera:
        quien llama decide si insiste. Devuelve qué pasó en la pasada, y en
        particular si la cuota se agotó — sin ese dato, el bucle de la carga
        inicial vuelve a intentar y gasta los reintentos del cliente contra una
        cuota que ya no existe.
        """
        pass
