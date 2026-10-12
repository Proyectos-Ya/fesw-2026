from datetime import datetime, timedelta

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

    async def registrar(
        self, *, completo: bool, listadas: int, momento: datetime | None = None
    ) -> int:
        """Guarda la corrida y devuelve las incompletas seguidas, contándola.

        0 si esta vino completa. Si no, cuántas incompletas hay desde la última
        completa (por fecha de corrida), esta incluida.
        """
        momento = momento or utc_now_naive()
        self.session.add(
            SyncEstadosRunModel(started_at=momento, complete=completo, listed=listadas)
        )
        await self.session.exec(  # type: ignore[call-overload]
            delete(SyncEstadosRunModel).where(
                col(SyncEstadosRunModel.started_at) < momento - RETENCION
            )
        )
        await self.session.commit()
        if completo:
            return 0

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
