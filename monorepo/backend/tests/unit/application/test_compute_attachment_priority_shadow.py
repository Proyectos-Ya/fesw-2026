"""Prioridad de anexos en sombra, con números calculados a mano."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.services.attachment_priority_shadow_service import (
    AttachmentPriorityShadowService,
)
from app.application.use_cases.ranking_telemetry.compute_attachment_priority_shadow import (
    ComputeAttachmentPriorityShadowUseCase,
)
from app.domain.entities.ranking_telemetry import InteractionKind, TenderInteraction
from tests.unit.application.fakes import InMemoryRankingTelemetryRepository

AHORA = datetime(2026, 10, 3, 12, 0)


def _ev(
    repo: InMemoryRankingTelemetryRepository,
    tender: UUID,
    kind: InteractionKind,
    *,
    position: int | None = None,
    hace: timedelta = timedelta(0),
) -> None:
    repo.interactions.append(
        TenderInteraction(
            user_id=uuid4(),
            tender_id=tender,
            kind=kind,
            ranking_id=uuid4() if position is not None else None,
            position=position,
            source="matches",
            created_at=AHORA - hace,
        )
    )


def _caso(
    repo: InMemoryRankingTelemetryRepository,
) -> ComputeAttachmentPriorityShadowUseCase:
    return ComputeAttachmentPriorityShadowUseCase(
        repo, AttachmentPriorityShadowService(), now=lambda: AHORA
    )


@pytest.mark.asyncio
async def test_prioridad_de_una_licitacion_abierta_con_senales():
    repo = InMemoryRankingTelemetryRepository()
    a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
    # C no está abierta; B cierra en 1 h (bajo el mínimo de 2 h); D no tiene señales.
    repo.open_tenders = {
        a: AHORA + timedelta(hours=48),
        b: AHORA + timedelta(hours=1),
        d: AHORA + timedelta(hours=48),
    }
    # A: 3 impresiones top-10 en rankings distintos...
    for posicion in (1, 2, 10):
        _ev(
            repo,
            a,
            InteractionKind.IMPRESION,
            position=posicion,
            hace=timedelta(days=1),
        )
    # ...una en la posición 11 (no cuenta), una de hace 8 días (no cuenta)...
    _ev(repo, a, InteractionKind.IMPRESION, position=11, hace=timedelta(days=1))
    _ev(repo, a, InteractionKind.IMPRESION, position=1, hace=timedelta(days=8))
    # ...y un detalle sin ranking de hace 2 días.
    _ev(repo, a, InteractionKind.DETALLE, hace=timedelta(days=2))
    repo.manual_uploads = [(a, AHORA - timedelta(days=1))]
    _ev(repo, b, InteractionKind.DETALLE)
    _ev(repo, c, InteractionKind.DETALLE)

    guardadas = await _caso(repo).execute()

    # 3·ln(1+3) + 2·ln(1+1) + 2 (subida manual) + 1 (urgencia a 48 h)
    assert guardadas == 1
    (snapshot,) = repo.snapshots
    assert snapshot.tender_id == a
    assert snapshot.priority == pytest.approx(8.545177444479563)
    assert snapshot.components["horas_al_cierre"] == 48.0
    assert snapshot.computed_at == AHORA


@pytest.mark.asyncio
async def test_sin_senales_no_guarda_nada():
    repo = InMemoryRankingTelemetryRepository()

    assert await _caso(repo).execute() == 0
    assert repo.snapshots == []
