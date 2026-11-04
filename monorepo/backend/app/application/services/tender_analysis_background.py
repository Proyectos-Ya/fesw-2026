"""Puerto para analizar los anexos en segundo plano apenas se suben (plan 233).

Quien lo implementa mantiene viva la tarea, abre una sesión de base de datos
propia (la de la subida ya se cerró) y no corre dos análisis a la vez sobre la
misma empresa y licitación.
"""

from typing import Protocol
from uuid import UUID


class TenderAnalysis(Protocol):
    async def execute(self, workspace_id: UUID, tender_id: UUID) -> object: ...


class ITenderAnalysisBackground(Protocol):
    def schedule(self, workspace_id: UUID, tender_id: UUID) -> None: ...

    def is_running(self, workspace_id: UUID, tender_id: UUID) -> bool: ...
