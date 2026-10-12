"""Puerto para extraer los hitos de las bases apenas se suben (HU-16, criterio 1).

Quien lo implementa se ocupa de lo que los casos de uso no deben saber: mantener
viva la tarea, abrir una sesión de base de datos propia —la de la subida ya se
cerró— y no correr dos extracciones a la vez sobre la misma licitación.
"""

from enum import StrEnum
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    # Solo para los tipos: `milestone_views` importa el estado de este módulo.
    from app.application.use_cases.milestones.milestone_views import (
        TenderMilestonesResult,
    )


class MilestoneExtractionStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    # La última extracción automática falló; el usuario puede reintentar a mano.
    FAILED = "failed"


class MilestoneExtraction(Protocol):
    async def execute(self, user_id: UUID, tender_id: UUID) -> "TenderMilestonesResult": ...


class IMilestoneExtractionBackground(Protocol):
    def schedule(self, user_id: UUID, tender_id: UUID) -> None: ...

    def status(self, user_id: UUID, tender_id: UUID) -> MilestoneExtractionStatus: ...

    async def run_now(
        self, user_id: UUID, tender_id: UUID, extraction: MilestoneExtraction
    ) -> "TenderMilestonesResult":
        """Extrae ya (el botón manual), esperando a la automática si está en curso."""
        ...
