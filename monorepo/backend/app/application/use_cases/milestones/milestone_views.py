"""Piezas compartidas por los casos de uso de hitos."""

import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.application.repositories.calendar_repository import (
    ICalendarEventLinkRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.domain.entities.calendar import CalendarProvider
from app.domain.entities.tender import Tender
from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    MilestoneUrgency,
    TenderMilestone,
)
from app.domain.errors.tender_errors import TenderNotFound


@dataclass(frozen=True)
class MilestoneView:
    milestone: TenderMilestone
    urgency: MilestoneUrgency
    synced_providers: list[CalendarProvider] = field(default_factory=list)


@dataclass(frozen=True)
class TenderMilestonesResult:
    milestones: list[MilestoneView]
    documents_count: int
    discarded_count: int = 0


async def get_tender(tenders: ITenderRepository, tender_id: UUID) -> Tender:
    encontradas = await tenders.get_tenders(TenderFilters(ids=[tender_id]))
    if not encontradas:
        raise TenderNotFound(tender_id)
    return encontradas[0]


def mercado_publico_milestones(tender: Tender, user_id: UUID) -> list[TenderMilestone]:
    """Hitos oficiales que siempre vienen en la ficha de Mercado Público."""
    comunes = {
        "user_id": user_id,
        "tender_id": tender.id,
        "source": MilestoneSource.MERCADO_PUBLICO,
        "has_time": True,
    }
    return [
        TenderMilestone(
            kind=MilestoneKind.PUBLICACION,
            title="Publicación en Mercado Público",
            due_at=tender.published_at,
            **comunes,
        ),
        TenderMilestone(
            kind=MilestoneKind.CIERRE_POSTULACION,
            title="Cierre de recepción de ofertas",
            due_at=tender.closing_at,
            **comunes,
        ),
    ]


def _clave(milestone: TenderMilestone) -> tuple[MilestoneKind, str]:
    sin_tildes = unicodedata.normalize("NFKD", milestone.title)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return milestone.kind, " ".join(sin_tildes.casefold().split())


def merge_milestones(
    existing: list[TenderMilestone], candidates: list[TenderMilestone], now: datetime
) -> list[TenderMilestone]:
    """Candidatos que conservan el id del hito equivalente ya guardado.

    Mantener el id es lo que permite actualizar el evento ya sincronizado en vez
    de crear uno nuevo. Dos candidatos equivalentes se quedan con el primero.
    """
    guardados = {_clave(m): m for m in existing}
    resultado: dict[tuple[MilestoneKind, str], TenderMilestone] = {}
    for candidato in candidates:
        clave = _clave(candidato)
        if clave in resultado:
            continue
        previo = guardados.get(clave)
        if previo is not None:
            candidato = candidato.model_copy(
                update={"id": previo.id, "created_at": previo.created_at, "updated_at": now}
            )
        resultado[clave] = candidato
    return list(resultado.values())


def changed(existing: list[TenderMilestone], merged: list[TenderMilestone]) -> list[TenderMilestone]:
    """Los hitos que son nuevos o cambiaron de fecha, título o descripción."""
    por_id = {m.id: m for m in existing}
    campos = ("title", "description", "due_at", "has_time", "source_excerpt", "source_document_id")
    return [
        m for m in merged
        if m.id not in por_id or any(getattr(m, c) != getattr(por_id[m.id], c) for c in campos)
    ]


async def synced_providers_by_milestone(
    event_links: ICalendarEventLinkRepository, milestone_ids: list[UUID]
) -> dict[UUID, list[CalendarProvider]]:
    proveedores: dict[UUID, list[CalendarProvider]] = {}
    for provider in CalendarProvider:
        for link in await event_links.list_by_milestones(milestone_ids, provider):
            proveedores.setdefault(link.milestone_id, []).append(provider)
    return proveedores


async def describe(
    milestones: list[TenderMilestone],
    event_links: ICalendarEventLinkRepository,
    now: datetime,
    documents_count: int,
    discarded_count: int = 0,
) -> TenderMilestonesResult:
    proveedores = await synced_providers_by_milestone(event_links, [m.id for m in milestones])
    return TenderMilestonesResult(
        milestones=[
            MilestoneView(
                milestone=m,
                urgency=m.urgencia(now),
                synced_providers=proveedores.get(m.id, []),
            )
            for m in sorted(milestones, key=lambda m: m.due_at)
        ],
        documents_count=documents_count,
        discarded_count=discarded_count,
    )
