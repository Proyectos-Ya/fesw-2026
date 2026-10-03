"""Atribución de una interacción a un ranking servido (plan 233, decisión 8)."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.use_cases.ranking_telemetry.record_tender_interaction import (
    InteractionRecordResult,
    RecordTenderInteractionUseCase,
)
from app.domain.entities.ranking_telemetry import InteractionKind, RankingImpression
from app.domain.errors.tender_errors import TenderNotFound
from tests.unit.application.fakes import InMemoryRankingTelemetryRepository

AHORA = datetime(2026, 10, 3, 12, 0)


class Escenario:
    """Una impresión sembrada: ranking R, usuario U, empresa S, licitación T, posición 2."""

    def __init__(self, *, hace: timedelta = timedelta(hours=1)) -> None:
        self.ranking = uuid4()
        self.user = uuid4()
        self.supplier = uuid4()
        self.tender = uuid4()
        self.repo = InMemoryRankingTelemetryRepository()
        self.repo.impressions.append(
            RankingImpression(
                ranking_id=self.ranking,
                supplier_id=self.supplier,
                user_id=self.user,
                tender_id=self.tender,
                position=2,
                model_version="m1",
                created_at=AHORA - hace,
            )
        )
        self.caso = RecordTenderInteractionUseCase(self.repo, now=lambda: AHORA)

    async def registrar(
        self,
        *,
        kind: InteractionKind = InteractionKind.DETALLE,
        user: UUID | None = None,
        supplier: UUID | None = ...,  # type: ignore[assignment]
        tender: UUID | None = None,
        ranking: UUID | None = ...,  # type: ignore[assignment]
        position: int | None = 1,
    ) -> InteractionRecordResult:
        return await self.caso.execute(
            user_id=user or self.user,
            supplier_id=self.supplier if supplier is ... else supplier,
            tender_id=tender or self.tender,
            kind=kind,
            source="matches",
            ranking_id=self.ranking if ranking is ... else ranking,
            position=position,
        )


@pytest.mark.asyncio
async def test_se_atribuye_con_el_mismo_usuario_y_la_misma_empresa():
    e = Escenario()

    resultado = await e.registrar(position=1)

    assert resultado == InteractionRecordResult(recorded=True, attributed=True)
    (guardada,) = e.repo.interactions
    assert guardada.ranking_id == e.ranking
    assert guardada.position == 1  # la mostrada, no la servida (2)
    assert guardada.supplier_id == e.supplier
    assert guardada.created_at == AHORA


@pytest.mark.asyncio
async def test_sin_empresa_en_el_contexto_tambien_se_atribuye():
    e = Escenario()

    resultado = await e.registrar(supplier=None)

    assert resultado.attributed is True
    assert e.repo.interactions[0].supplier_id == e.supplier


@pytest.mark.asyncio
async def test_un_ranking_de_otro_usuario_se_guarda_sin_atribuir():
    e = Escenario()

    resultado = await e.registrar(user=uuid4())

    assert resultado == InteractionRecordResult(recorded=True, attributed=False)
    (guardada,) = e.repo.interactions
    assert guardada.ranking_id is None
    assert guardada.position is None


@pytest.mark.asyncio
async def test_un_ranking_de_otra_empresa_no_se_atribuye():
    e = Escenario()

    resultado = await e.registrar(supplier=uuid4())

    assert resultado.attributed is False
    assert e.repo.interactions[0].ranking_id is None


@pytest.mark.asyncio
async def test_una_licitacion_que_no_estaba_en_ese_ranking_no_se_atribuye():
    e = Escenario()

    resultado = await e.registrar(tender=uuid4())

    assert resultado == InteractionRecordResult(recorded=True, attributed=False)
    assert e.repo.interactions[0].ranking_id is None


@pytest.mark.asyncio
async def test_un_ranking_de_hace_mas_de_7_dias_no_se_atribuye():
    e = Escenario(hace=timedelta(days=8))

    resultado = await e.registrar()

    assert resultado.attributed is False
    assert e.repo.interactions[0].ranking_id is None


@pytest.mark.asyncio
async def test_sin_ranking_la_posicion_se_descarta():
    e = Escenario()

    await e.registrar(ranking=None, position=3)

    (guardada,) = e.repo.interactions
    assert guardada.ranking_id is None
    assert guardada.position is None


@pytest.mark.asyncio
async def test_una_impresion_sin_atribucion_no_se_guarda():
    e = Escenario()

    resultado = await e.registrar(kind=InteractionKind.IMPRESION, ranking=None)

    assert resultado == InteractionRecordResult(recorded=False, attributed=False)
    assert e.repo.interactions == []


@pytest.mark.asyncio
async def test_una_impresion_repetida_en_el_mismo_ranking_no_se_duplica():
    e = Escenario()

    primera = await e.registrar(kind=InteractionKind.IMPRESION, position=2)
    segunda = await e.registrar(kind=InteractionKind.IMPRESION, position=2)

    assert primera == InteractionRecordResult(recorded=True, attributed=True)
    assert segunda == InteractionRecordResult(recorded=False, attributed=True)
    assert len(e.repo.interactions) == 1


@pytest.mark.asyncio
async def test_una_licitacion_inexistente_propaga_tender_not_found():
    e = Escenario()
    e.repo.missing_tenders.add(e.tender)

    with pytest.raises(TenderNotFound):
        await e.registrar()
