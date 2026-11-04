"""El repositorio SQL de la telemetría del ranking contra Postgres real.

Idempotencia, purga a los 90 días y consultas de la prioridad en sombra.

`db_session` y el esquema limpio los aporta tests/integration/conftest.py, que
apunta a la base de test y no a la de desarrollo.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.infrastructure.repositories.models  # noqa: F401
from app.domain.entities.ranking_telemetry import (
    AttachmentPriorityShadow,
    InteractionKind,
    PurgeCounts,
    RankingImpression,
    RankingMetricDaily,
    TenderInteraction,
)
from app.domain.errors.tender_errors import TenderNotFound
from app.infrastructure.repositories.ranking_telemetry_model import (
    AttachmentPriorityShadowModel,
    RankingImpressionModel,
    RankingMetricDailyModel,
    TenderInteractionModel,
)
from app.infrastructure.repositories.ranking_telemetry_repository import (
    SqlRankingTelemetryRepository,
)
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.tender_chat_model import TenderChatDocumentModel
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    RegionModel,
    TenderModel,
    TenderStatusModel,
)
from app.infrastructure.repositories.user_model import UserModel
from app.shared.regions import CHILE_REGIONS


def ahora_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class Mundo:
    user_id: UUID
    supplier_id: UUID
    abierta: UUID
    pronto: UUID
    cerrada: UUID
    ahora: datetime


async def sembrar(session: AsyncSession) -> Mundo:
    ahora = ahora_utc()
    user_id, supplier_id = uuid4(), uuid4()
    abierta, pronto, cerrada = uuid4(), uuid4(), uuid4()

    session.add(
        UserModel(
            id=user_id,
            email="usuario@example.com",
            full_name="Usuario de Prueba",
            created_at=ahora,
            updated_at=ahora,
        )
    )
    session.add(
        SupplierModel(
            id=supplier_id,
            rut="76.086.428-5",
            legal_name="Empresa Ejemplo SpA",
            created_at=ahora,
            updated_at=ahora,
        )
    )
    session.add(RegionModel(id=13, name=CHILE_REGIONS[13]))
    session.add(TenderStatusModel(id=2, code="publicada", name="Publicada"))
    session.add(TenderStatusModel(id=3, code="cerrada", name="Cerrada"))
    session.add(
        BuyerInstitutionModel(
            rut="12.345.678-9",
            name="Municipalidad de Santiago",
            region_id=13,
            created_at=ahora,
            updated_at=ahora,
        )
    )
    # Abierta (cierra en 48 h), por cerrar (en 1 h) y ya cerrada.
    for indice, (tender_id, status_id, cierra) in enumerate(
        (
            (abierta, 2, ahora + timedelta(hours=48)),
            (pronto, 2, ahora + timedelta(hours=1)),
            (cerrada, 3, ahora + timedelta(hours=48)),
        )
    ):
        session.add(
            TenderModel(
                id=tender_id,
                code=f"1057539-{indice}-COT26",
                name="Materiales Eléctricos",
                description="Compra de cables y enchufes",
                status_id=status_id,
                published_at=ahora,
                closing_at=cierra,
                last_change_at=ahora,
                buyer_rut="12.345.678-9",
                buyer_unit="Operaciones",
                available_amount_clp=500000.0,
                created_at=ahora,
                updated_at=ahora,
            )
        )
    await session.commit()
    return Mundo(user_id, supplier_id, abierta, pronto, cerrada, ahora)


def impresion(
    mundo: Mundo, ranking: UUID, tender: UUID, posicion: int, *, hace=timedelta(0)
) -> RankingImpression:
    return RankingImpression(
        ranking_id=ranking,
        supplier_id=mundo.supplier_id,
        user_id=mundo.user_id,
        tender_id=tender,
        position=posicion,
        score=0.9,
        model_version="m1",
        created_at=mundo.ahora - hace,
    )


def interaccion(
    mundo: Mundo,
    tender: UUID,
    kind: InteractionKind = InteractionKind.DETALLE,
    *,
    ranking: UUID | None = None,
    posicion: int | None = None,
    hace=timedelta(0),
) -> TenderInteraction:
    return TenderInteraction(
        user_id=mundo.user_id,
        supplier_id=mundo.supplier_id,
        tender_id=tender,
        kind=kind,
        ranking_id=ranking,
        position=posicion,
        source="matches",
        created_at=mundo.ahora - hace,
    )


async def contar(session: AsyncSession, modelo) -> int:
    resultado = await session.exec(select(func.count()).select_from(modelo))
    return resultado.one()


@pytest.mark.asyncio
async def test_las_impresiones_guardadas_dos_veces_quedan_una_vez(
    db_session: AsyncSession,
):
    mundo = await sembrar(db_session)
    repo = SqlRankingTelemetryRepository(db_session)
    ranking = uuid4()
    filas = [
        impresion(mundo, ranking, mundo.abierta, 1),
        impresion(mundo, ranking, mundo.pronto, 2),
    ]

    await repo.save_impressions(filas)
    await repo.save_impressions(filas)

    assert await contar(db_session, RankingImpressionModel) == 2
    encontrada = await repo.find_impression(ranking, mundo.pronto)
    assert encontrada is not None
    assert encontrada.position == 2
    assert encontrada.score == pytest.approx(0.9)
    assert await repo.find_impression(ranking, mundo.cerrada) is None


@pytest.mark.asyncio
async def test_una_interaccion_repetida_en_el_mismo_ranking_se_guarda_una_vez(
    db_session: AsyncSession,
):
    mundo = await sembrar(db_session)
    repo = SqlRankingTelemetryRepository(db_session)
    ranking = uuid4()

    primera = await repo.save_interaction(
        interaccion(mundo, mundo.abierta, ranking=ranking, posicion=1)
    )
    segunda = await repo.save_interaction(
        interaccion(mundo, mundo.abierta, ranking=ranking, posicion=1)
    )

    assert (primera, segunda) == (True, False)
    assert await contar(db_session, TenderInteractionModel) == 1


@pytest.mark.asyncio
async def test_dos_interacciones_sin_ranking_se_guardan_las_dos(
    db_session: AsyncSession,
):
    mundo = await sembrar(db_session)
    repo = SqlRankingTelemetryRepository(db_session)

    primera = await repo.save_interaction(interaccion(mundo, mundo.abierta))
    segunda = await repo.save_interaction(interaccion(mundo, mundo.abierta))

    assert (primera, segunda) == (True, True)
    assert await contar(db_session, TenderInteractionModel) == 2


@pytest.mark.asyncio
async def test_una_interaccion_de_una_licitacion_inexistente_lanza_tender_not_found(
    db_session: AsyncSession,
):
    mundo = await sembrar(db_session)
    repo = SqlRankingTelemetryRepository(db_session)

    with pytest.raises(TenderNotFound):
        await repo.save_interaction(interaccion(mundo, uuid4()))

    # La sesión quedó revertida y se puede seguir usando.
    assert await repo.save_interaction(interaccion(mundo, mundo.abierta)) is True


@pytest.mark.asyncio
async def test_purga_a_los_90_dias_conserva_las_metricas(db_session: AsyncSession):
    mundo = await sembrar(db_session)
    repo = SqlRankingTelemetryRepository(db_session)
    for dias, posicion in ((91, 1), (89, 2)):
        hace = timedelta(days=dias)
        await repo.save_impressions(
            [impresion(mundo, uuid4(), mundo.abierta, posicion, hace=hace)]
        )
        await repo.save_interaction(interaccion(mundo, mundo.abierta, hace=hace))
        await repo.save_priority_snapshots(
            [
                AttachmentPriorityShadow(
                    tender_id=mundo.abierta,
                    computed_at=mundo.ahora - hace,
                    priority=1.0,
                    components={"subida_manual": False},
                )
            ]
        )
    await repo.upsert_daily_metric(
        RankingMetricDaily(
            day=date(2026, 3, 1),
            model_version="m1",
            ndcg_at_10=0.5,
            ci_low=0.4,
            ci_high=0.6,
            rankings_evaluated=3,
            rankings_served=10,
        )
    )

    borrado = await repo.purge_before(mundo.ahora - timedelta(days=90))

    assert borrado == PurgeCounts(impressions=1, interactions=1, priority_snapshots=1)
    assert await contar(db_session, RankingImpressionModel) == 1
    assert await contar(db_session, TenderInteractionModel) == 1
    assert await contar(db_session, AttachmentPriorityShadowModel) == 1
    assert await contar(db_session, RankingMetricDailyModel) == 1


@pytest.mark.asyncio
async def test_conteos_de_la_prioridad_distinguen_impresiones_de_interacciones(
    db_session: AsyncSession,
):
    mundo = await sembrar(db_session)
    repo = SqlRankingTelemetryRepository(db_session)
    desde = mundo.ahora - timedelta(days=7)
    await repo.save_interaction(
        interaccion(
            mundo,
            mundo.abierta,
            InteractionKind.IMPRESION,
            ranking=uuid4(),
            posicion=3,
        )
    )
    await repo.save_interaction(
        interaccion(
            mundo,
            mundo.abierta,
            InteractionKind.IMPRESION,
            ranking=uuid4(),
            posicion=11,
        )
    )
    await repo.save_interaction(interaccion(mundo, mundo.abierta, InteractionKind.DETALLE))

    assert await repo.count_top_impressions_by_tender(desde, 10) == {mundo.abierta: 1}
    assert await repo.count_interactions_by_tender(desde) == {mundo.abierta: 1}


@pytest.mark.asyncio
async def test_solo_las_publicadas_que_cierran_despues_del_umbral(
    db_session: AsyncSession,
):
    mundo = await sembrar(db_session)
    repo = SqlRankingTelemetryRepository(db_session)

    abiertas = await repo.open_tenders_closing_after(
        {mundo.abierta, mundo.pronto, mundo.cerrada},
        mundo.ahora + timedelta(hours=2),
    )

    assert set(abiertas) == {mundo.abierta}
    assert await repo.open_tenders_closing_after([], mundo.ahora) == {}


@pytest.mark.asyncio
async def test_el_upsert_de_la_metrica_deja_una_fila_con_los_valores_de_la_segunda(
    db_session: AsyncSession,
):
    repo = SqlRankingTelemetryRepository(db_session)
    dia = date(2026, 10, 2)

    def metrica(ndcg: float) -> RankingMetricDaily:
        return RankingMetricDaily(
            day=dia,
            model_version="m1",
            ndcg_at_10=ndcg,
            ci_low=ndcg - 0.1,
            ci_high=ndcg + 0.1,
            rankings_evaluated=2,
            rankings_served=4,
        )

    await repo.upsert_daily_metric(metrica(0.4))
    await repo.upsert_daily_metric(metrica(0.7))

    filas = (await db_session.exec(select(RankingMetricDailyModel))).all()
    assert len(filas) == 1
    assert filas[0].ndcg_at_10 == pytest.approx(0.7)
    assert filas[0].ci_low == pytest.approx(0.6)


@pytest.mark.asyncio
async def test_subida_manual_mira_los_documentos_del_chat_de_los_ultimos_dias(
    db_session: AsyncSession,
):
    mundo = await sembrar(db_session)
    repo = SqlRankingTelemetryRepository(db_session)
    for tender_id, dias in ((mundo.abierta, 2), (mundo.pronto, 10)):
        db_session.add(
            TenderChatDocumentModel(
                id=uuid4(),
                tender_id=tender_id,
                user_id=mundo.user_id,
                file_name="bases.pdf",
                file_type="pdf",
                file_size_bytes=1024,
                storage_path="storage/bases.pdf",
                created_at=mundo.ahora - timedelta(days=dias),
            )
        )
    await db_session.commit()

    subidas = await repo.tenders_with_manual_upload(mundo.ahora - timedelta(days=7))

    assert subidas == {mundo.abierta}


@pytest.mark.asyncio
async def test_listas_para_el_ndcg_respetan_el_rango_y_los_rankings(
    db_session: AsyncSession,
):
    mundo = await sembrar(db_session)
    repo = SqlRankingTelemetryRepository(db_session)
    ranking, otro = uuid4(), uuid4()
    await repo.save_impressions(
        [
            impresion(mundo, ranking, mundo.abierta, 1, hace=timedelta(hours=2)),
            impresion(mundo, otro, mundo.abierta, 1, hace=timedelta(days=3)),
        ]
    )
    await repo.save_interaction(
        interaccion(mundo, mundo.abierta, ranking=ranking, posicion=1)
    )
    await repo.save_interaction(interaccion(mundo, mundo.abierta))  # sin ranking

    servidas = await repo.list_impressions_between(
        mundo.ahora - timedelta(days=1), mundo.ahora
    )
    atribuidas = await repo.list_attributed_interactions([ranking, otro])

    assert [i.ranking_id for i in servidas] == [ranking]
    assert [i.ranking_id for i in atribuidas] == [ranking]
    assert atribuidas[0].kind == InteractionKind.DETALLE
    assert await repo.list_attributed_interactions([]) == []
