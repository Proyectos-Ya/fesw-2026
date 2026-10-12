from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Index
from sqlmodel import Field, SQLModel

from app.shared.datetime_utils import utc_now_naive


class SyncEstadosRunModel(SQLModel, table=True):
    """Una fila por corrida del cron de estados (`scripts/sync_estados.py`).

    Solo sirve para contar cuántas incompletas van seguidas, que es lo que
    decide el código de salida. Tabla propia y no `ingestion_run`: `sync_diaria`
    se niega a correr si ve ahí una corrida en `running`, y compartirla la
    bloquearía cada vez que coincidan.
    """

    __tablename__ = "sync_estados_run"  # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    started_at: datetime = Field(default_factory=utc_now_naive)
    # Si el listado recorrió la ventana entera.
    complete: bool
    listed: int = Field(default=0)

    # La racha se cuenta desde la última completa, por fecha.
    __table_args__ = (Index("ix_sync_estados_run_started_at", "started_at"),)
