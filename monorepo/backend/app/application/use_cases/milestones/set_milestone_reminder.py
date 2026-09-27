from uuid import UUID

from app.application.repositories.tender_milestone_repository import (
    ITenderMilestoneRepository,
)
from app.domain.entities.tender_milestone import TenderMilestone
from app.domain.errors.milestone_errors import MilestoneNotFound


class SetMilestoneReminderUseCase:
    """Activa o apaga el recordatorio de un hito (criterio 10)."""

    def __init__(self, milestones: ITenderMilestoneRepository):
        self.milestones = milestones

    async def execute(
        self, user_id: UUID, tender_id: UUID, milestone_id: UUID, days_before: int | None
    ) -> TenderMilestone:
        # Se valida antes de escribir: el repositorio filtra por usuario, pero
        # además el hito tiene que ser de la licitación de la ruta, y no hay que
        # modificar nada para descubrir que no lo es.
        encontrados = await self.milestones.list_by_ids(user_id, [milestone_id])
        if not encontrados or encontrados[0].tender_id != tender_id:
            raise MilestoneNotFound()

        hito = await self.milestones.set_reminder(user_id, milestone_id, days_before)
        if hito is None:
            raise MilestoneNotFound()
        return hito
