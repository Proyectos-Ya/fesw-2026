from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.application.use_cases.milestones.extract_tender_milestones import (
    ExtractTenderMilestonesUseCase,
)
from app.application.use_cases.milestones.get_tender_milestones import (
    GetTenderMilestonesUseCase,
)
from app.application.use_cases.milestones.milestone_views import TenderMilestonesResult
from app.application.use_cases.milestones.set_milestone_reminder import (
    SetMilestoneReminderUseCase,
)
from app.domain.entities.calendar import CalendarProvider
from app.domain.entities.tender_milestone import (
    REMINDER_DAYS_OPTIONS,
    MilestoneKind,
    MilestoneSource,
    MilestoneUrgency,
)
from app.domain.entities.user import User
from app.domain.errors.milestone_errors import (
    MilestoneExtractionUnavailable,
    MilestoneNotFound,
)
from app.domain.errors.tender_errors import TenderNotFound
from app.shared.datetime_utils import UtcDateTime


class MilestoneResponse(BaseModel):
    id: UUID
    kind: MilestoneKind
    title: str
    description: str | None
    source: MilestoneSource
    source_excerpt: str | None
    due_at: UtcDateTime
    has_time: bool
    urgency: MilestoneUrgency
    synced_providers: list[CalendarProvider]
    # Nulo = el usuario no activó el recordatorio de este hito.
    reminder_days_before: int | None = None


class MilestoneListResponse(BaseModel):
    milestones: list[MilestoneResponse]
    documents_count: int
    discarded_count: int


def _respuesta(resultado: TenderMilestonesResult) -> MilestoneListResponse:
    return MilestoneListResponse(
        milestones=[
            MilestoneResponse(
                id=v.milestone.id,
                kind=v.milestone.kind,
                title=v.milestone.title,
                description=v.milestone.description,
                source=v.milestone.source,
                source_excerpt=v.milestone.source_excerpt,
                due_at=v.milestone.due_at,
                has_time=v.milestone.has_time,
                urgency=v.urgency,
                synced_providers=v.synced_providers,
                reminder_days_before=v.milestone.reminder_days_before,
            )
            for v in resultado.milestones
        ],
        documents_count=resultado.documents_count,
        discarded_count=resultado.discarded_count,
    )


class SetReminderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Nulo apaga el recordatorio; el resto se valida contra las opciones ofrecidas.
    days_before: int | None = None


def create_milestones_router(
    get_current_user: Callable,
    get_tender_milestones_use_case: Callable,
    get_extract_tender_milestones_use_case: Callable,
    get_set_milestone_reminder_use_case: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/tenders", tags=["Milestones"])

    @router.get("/{tender_id}/milestones", response_model=MilestoneListResponse)
    async def list_milestones(
        tender_id: UUID,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[GetTenderMilestonesUseCase, Depends(get_tender_milestones_use_case)],
    ):
        try:
            return _respuesta(await use_case.execute(user.id, tender_id))
        except TenderNotFound as error:
            raise HTTPException(404, "La licitación no existe.") from error

    @router.post("/{tender_id}/milestones/extract", response_model=MilestoneListResponse)
    async def extract_milestones(
        tender_id: UUID,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            ExtractTenderMilestonesUseCase, Depends(get_extract_tender_milestones_use_case)
        ],
    ):
        try:
            return _respuesta(await use_case.execute(user.id, tender_id))
        except TenderNotFound as error:
            raise HTTPException(404, "La licitación no existe.") from error
        except MilestoneExtractionUnavailable as error:
            raise HTTPException(503, str(error)) from error

    @router.patch("/{tender_id}/milestones/{milestone_id}/reminder")
    async def set_reminder(
        tender_id: UUID,
        milestone_id: UUID,
        body: SetReminderRequest,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            SetMilestoneReminderUseCase, Depends(get_set_milestone_reminder_use_case)
        ],
    ):
        if body.days_before is not None and body.days_before not in REMINDER_DAYS_OPTIONS:
            raise HTTPException(
                422,
                "La anticipación debe ser una de "
                f"{', '.join(str(d) for d in REMINDER_DAYS_OPTIONS)} días, o nula.",
            )
        try:
            hito = await use_case.execute(user.id, tender_id, milestone_id, body.days_before)
        except MilestoneNotFound as error:
            raise HTTPException(404, str(error)) from error
        return {"milestone_id": hito.id, "reminder_days_before": hito.reminder_days_before}

    return router
