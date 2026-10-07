"""Piezas compartidas por los casos de uso de hitos."""

import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID

from app.application.repositories.calendar_repository import (
    ICalendarEventLinkRepository,
)
from app.application.repositories.tender_milestone_repository import (
    ITenderMilestoneRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.services.milestone_extraction_background import (
    MilestoneExtractionStatus,
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
from app.shared.datetime_utils import CHILE_TZ

# Los que ya vienen de Mercado Público. Los de la IA con estos tipos aparecían
# duplicados junto al oficial.
OFFICIAL_KINDS = frozenset({MilestoneKind.PUBLICACION, MilestoneKind.CIERRE_POSTULACION})


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
    # Bases subidas cuyo archivo ya no está (el disco del contenedor es efímero).
    unavailable_documents_count: int = 0
    # Si la IA está leyendo en segundo plano las bases recién subidas.
    extraction_status: MilestoneExtractionStatus = MilestoneExtractionStatus.IDLE
    # Bases que todavía no se leen (nuevas, o que fallaron): habilitan el botón.
    pending_documents_count: int = 0
    # Bases que la IA no pudo leer en esta extracción.
    failed_documents_count: int = 0


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


def _dia_en_chile(milestone: TenderMilestone) -> date:
    return milestone.due_at.replace(tzinfo=UTC).astimezone(CHILE_TZ).date()


def _clave_de_dia(milestone: TenderMilestone) -> tuple[MilestoneKind, date] | None:
    # "Otro" agrupa hitos distintos: dos el mismo día no son el mismo hito.
    if milestone.kind is MilestoneKind.OTRO:
        return None
    return milestone.kind, _dia_en_chile(milestone)


def merge_ai_milestones(
    existing: list[TenderMilestone], candidates: list[TenderMilestone], now: datetime
) -> list[TenderMilestone]:
    """Como `merge_milestones`, pero tolerante a cómo la IA nombra un hito.

    Un mismo hito puede volver como "Visita técnica obligatoria" o "Visita a
    terreno": se reconoce primero por tipo y día (en Chile) y después por
    título. Así se deduplican también los candidatos que la IA repite.
    """
    por_dia = {clave: m for m in existing if (clave := _clave_de_dia(m)) is not None}
    por_titulo = {_clave(m): m for m in existing}
    usados: set[UUID] = set()
    vistos: set[object] = set()
    resultado: list[TenderMilestone] = []
    for candidato in candidates:
        de_dia = _clave_de_dia(candidato)
        claves: set[object] = {_clave(candidato)} | ({de_dia} if de_dia is not None else set())
        if claves & vistos:
            continue
        vistos |= claves
        previo = por_dia.get(de_dia) if de_dia is not None else None
        if previo is None or previo.id in usados:
            previo = por_titulo.get(_clave(candidato))
        if previo is not None and previo.id not in usados:
            usados.add(previo.id)
            candidato = candidato.model_copy(
                update={"id": previo.id, "created_at": previo.created_at, "updated_at": now}
            )
        resultado.append(candidato)
    return resultado


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


async def save_official_milestones(
    milestones: ITenderMilestoneRepository,
    event_links: ICalendarEventLinkRepository,
    tender: Tender,
    user_id: UUID,
    now: datetime,
) -> None:
    """Guarda publicación y cierre fusionándolos **solo** contra las filas oficiales.

    Antes se fusionaban contra todos los hitos: uno de la IA con el mismo tipo y
    título que el cierre se quedaba con su id, y la fila cambiaba de origen y
    fecha en cada consulta (hitos duplicados o que desaparecían). Además repara
    lo que eso dejó: filas oficiales repetidas y cierres o publicaciones de la
    IA. Nunca borra un hito que ya está en un calendario.
    """
    existentes = await milestones.list_for_tender(user_id, tender.id)
    oficiales = [m for m in existentes if m.source is MilestoneSource.MERCADO_PUBLICO]
    ia_de_tipo_oficial = [
        m for m in existentes
        if m.source is MilestoneSource.IA_DOCUMENTO and m.kind in OFFICIAL_KINDS
    ]
    revisar = oficiales + ia_de_tipo_oficial
    sincronizados = await synced_providers_by_milestone(event_links, [m.id for m in revisar])
    # Entre dos filas oficiales repetidas gana la sincronizada: en la fusión,
    # la última de la lista se queda con la clave.
    oficiales.sort(key=lambda m: m.id in sincronizados)
    fusion = merge_milestones(oficiales, mercado_publico_milestones(tender, user_id), now)
    cambios = changed(oficiales, fusion)
    if cambios:
        await milestones.save_many(cambios)
    vigentes = {m.id for m in fusion}
    sobrantes = [m.id for m in revisar if m.id not in vigentes and m.id not in sincronizados]
    if sobrantes:
        await milestones.delete_many(user_id, sobrantes)


async def remove_orphan_ai_milestones(
    milestones: ITenderMilestoneRepository,
    event_links: ICalendarEventLinkRepository,
    user_id: UUID,
    tender_id: UUID,
    document_ids: set[UUID],
) -> None:
    """Quita los hitos de IA de documentos que el usuario borró, salvo los sincronizados."""
    huerfanos = [
        m.id
        for m in await milestones.list_for_tender(user_id, tender_id)
        if m.source is MilestoneSource.IA_DOCUMENTO
        and m.source_document_id is not None
        and m.source_document_id not in document_ids
    ]
    if not huerfanos:
        return
    sincronizados = await synced_providers_by_milestone(event_links, huerfanos)
    borrar = [i for i in huerfanos if i not in sincronizados]
    if borrar:
        await milestones.delete_many(user_id, borrar)


async def describe(
    milestones: list[TenderMilestone],
    event_links: ICalendarEventLinkRepository,
    now: datetime,
    documents_count: int,
    discarded_count: int = 0,
    unavailable_documents_count: int = 0,
    extraction_status: MilestoneExtractionStatus = MilestoneExtractionStatus.IDLE,
    pending_documents_count: int = 0,
    failed_documents_count: int = 0,
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
        unavailable_documents_count=unavailable_documents_count,
        extraction_status=extraction_status,
        pending_documents_count=pending_documents_count,
        failed_documents_count=failed_documents_count,
    )
