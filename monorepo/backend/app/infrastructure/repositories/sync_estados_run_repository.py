from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.repositories.sync_estados_run_model import SyncEstadosRunModel
from app.shared.datetime_utils import utc_now_naive

# Para contar una racha basta con lo reciente. Corre cada hora: sin poda serían
# ~8.800 filas al año que nadie lee.
RETENCION = timedelta(days=30)


class SyncEstadosRunRepository:
    """Historial del cron de estados, para saber cuántas incompletas van seguidas."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def abrir(self, momento: datetime | None = None) -> UUID:
        """Registra la corrida al empezar, como incompleta (plan 305).

        Si la corrida vence el tope o el proceso muere, la fila queda así y
        cuenta para la racha. Antes una corrida que no terminaba no dejaba
        rastro, y la racha no veía las horas que se estaban perdiendo.
        """
        momento = momento or utc_now_naive()
        fila = SyncEstadosRunModel(started_at=momento, complete=False, listed=0)
        # Antes del commit: después, leer el atributo dispararía una consulta.
        corrida = fila.id
        self.session.add(fila)
        await self._podar(momento)
        await self.session.commit()
        return corrida

    async def cerrar(
        self,
        corrida: UUID,
        *,
        completo: bool,
        listadas: int,
        peticiones: int | None,
    ) -> int:
        """Cierra la corrida y devuelve las incompletas seguidas, contándola."""
        fila = await self.session.get(SyncEstadosRunModel, corrida)
        if fila is not None:
            fila.complete = completo
            fila.listed = listadas
            fila.requests = peticiones
            fila.finished_at = utc_now_naive()
            self.session.add(fila)
            await self.session.commit()
        return 0 if completo else await self._incompletas_seguidas()

    async def obtener(self, corrida: UUID) -> SyncEstadosRunModel | None:
        return await self.session.get(SyncEstadosRunModel, corrida)

    async def registrar(
        self, *, completo: bool, listadas: int, momento: datetime | None = None
    ) -> int:
        """Guarda una corrida ya terminada y devuelve las incompletas seguidas.

        0 si esta vino completa. Si no, cuántas incompletas hay desde la última
        completa (por fecha de corrida), esta incluida.
        """
        momento = momento or utc_now_naive()
        self.session.add(
            SyncEstadosRunModel(started_at=momento, complete=completo, listed=listadas)
        )
        await self._podar(momento)
        await self.session.commit()
        return 0 if completo else await self._incompletas_seguidas()

    async def _podar(self, momento: datetime) -> None:
        await self.session.exec(  # type: ignore[call-overload]
            delete(SyncEstadosRunModel).where(
                col(SyncEstadosRunModel.started_at) < momento - RETENCION
            )
        )

    async def _incompletas_seguidas(self) -> int:
        ultima_completa = (
            select(func.max(SyncEstadosRunModel.started_at))
            .where(col(SyncEstadosRunModel.complete).is_(True))
            .scalar_subquery()
        )
        stmt = select(func.count()).where(
            col(SyncEstadosRunModel.complete).is_(False),
            (ultima_completa.is_(None))
            | (col(SyncEstadosRunModel.started_at) > ultima_completa),
        )
        return (await self.session.exec(stmt)).one()

    async def contar(self) -> int:
        stmt = select(func.count()).select_from(SyncEstadosRunModel)
        return (await self.session.exec(stmt)).one()
