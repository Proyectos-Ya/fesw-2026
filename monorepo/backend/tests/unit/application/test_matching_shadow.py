"""Pruebas unitarias para el matching enriquecido en sombra (Plan 233, Decisión 9)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.repositories.matching_shadow_repository import (
    IMatchingShadowRepository,
)
from app.application.services.ranking_metrics_service import RankingMetricsService
from app.application.services.text_builder import TextBuilder
from app.application.use_cases.matching_shadow import (
    ComputeShadowScoreUseCase,
    ReplayShadowRankingUseCase,
)
from app.config import Settings
from app.domain.entities.matching_shadow import (
    MatchingShadowScore,
    TenderAttachmentItem,
)
from app.domain.entities.ranking_telemetry import (
    RankingImpression,
    TenderInteraction,
)
from app.domain.entities.tender_digest import (
    ItemConsolidado,
    RequisitoConsolidado,
    ResumenDeAnexo,
    TenderDigest,
    TenderDigestData,
)
from tests.unit.application.test_compatibility_scorer import (
    crear_licitacion,
    crear_proveedor,
    crear_scorer,
)


class InMemoryMatchingShadowRepository(IMatchingShadowRepository):
    def __init__(self) -> None:
        self.scores: list[MatchingShadowScore] = []
        self.items: list[TenderAttachmentItem] = []

    async def save_shadow_scores(self, scores: list[MatchingShadowScore]) -> None:
        self.scores.extend(scores)

    async def get_shadow_scores_by_ranking(
        self, ranking_id
    ) -> list[MatchingShadowScore]:
        return [s for s in self.scores if s.ranking_id == ranking_id]

    async def get_shadow_scores_by_supplier(
        self, supplier_id, variant="att-text-v1", limit=50
    ) -> list[MatchingShadowScore]:
        return [
            s
            for s in self.scores
            if s.supplier_id == supplier_id and s.variant == variant
        ][:limit]

    async def save_attachment_items(self, items: list[TenderAttachmentItem]) -> None:
        self.items.extend(items)

    async def get_attachment_items(self, tender_id) -> list[TenderAttachmentItem]:
        return [i for i in self.items if i.tender_id == tender_id]


def armar_digest(tender_id, resumen_texto: str, items_desc: list[str] | None = None) -> TenderDigest:
    ahora = datetime.now(UTC).replace(tzinfo=None)
    data = TenderDigestData.vacio()
    data.resumenes = [
        ResumenDeAnexo(
            anexo_id=uuid4(),
            documento="Bases.pdf",
            texto=resumen_texto,
            citas=[],
        )
    ]
    if items_desc:
        data.items = [
            ItemConsolidado(descripcion=desc, citas=[]) for desc in items_desc
        ]
    data.requisitos = [
        RequisitoConsolidado(
            descripcion="Certificado ISO 9001 vigente",
            tipo="administrativo",
            citas=[],
        )
    ]

    return TenderDigest(
        id=uuid4(),
        tender_id=tender_id,
        version=1,
        extraction_set_hash="hash-123",
        is_current=True,
        source_count=1,
        data=data,
        api_snapshot={},
        created_at=ahora,
    )


# --- 1. Test signals() idéntico a score_many cuando digest es None ---


@pytest.mark.asyncio
async def test_signals_identico_a_score_many_sin_digest():
    scorer, _ = crear_scorer()
    tender_id = uuid4()
    tender = crear_licitacion(
        tender_id,
        nombre="Adquisición de insumos de aseo y desinfección",
        descripcion="Cloro, jabón y papel higiénico para oficinas",
        partidas=[("Cloro", "Bidón de 5L"), ("Jabón", "Jabón líquido 1L")],
    )
    supplier = crear_proveedor(
        keywords=["insumos de aseo", "cloro", "artículos de limpieza"],
        sectors=["Comercio mayorista de productos de limpieza"],
    )

    # 1. Ejecutar score_many
    scored = await scorer.score_many(supplier, [tender], limit=1)
    assert len(scored) == 1
    baseline = scored[0]

    # 2. Ejecutar signals sin digest
    signals = await scorer.signals(supplier, tender, digest=None)
    assert signals is not None

    # Verificación de equivalencia matemática estricta
    assert signals.reranker_score == pytest.approx(baseline.reranker_score, abs=1e-5)
    assert signals.final_score == pytest.approx(baseline.final_score, abs=1e-5)


# --- 2. Test recorte de texto de anexos a 512 tokens ---


def test_build_from_tender_with_digest_recorta_estrictamente_a_512_tokens():
    tb = TextBuilder()
    tender_id = uuid4()
    tender = crear_licitacion(
        tender_id,
        nombre="Construcción de puente modular",
        descripcion="Puente vehicular de acero galvanizado",
    )

    # Resumen gigante (> 4.000 caracteres)
    texto_gigante = "Bases administrativas especiales y especificaciones técnicas: " * 70
    digest = armar_digest(tender_id, resumen_texto=texto_gigante)

    resultado = tb.build_from_tender_with_digest(
        tender=tender, items=tender.items, digest=digest, max_tokens=512
    )

    # Máximo 512 tokens * 4 = 2048 caracteres
    assert len(resultado) <= 512 * 4
    # Preserva la información primaria de la licitación
    assert "Construcción de puente modular" in resultado
    assert "Puente vehicular de acero galvanizado" in resultado
    # Lo que se recortó fue el texto del digest
    assert "Anexos:" in resultado
    assert len(resultado) < len(texto_gigante)


# --- 3. Test signals() con digest en att-text-v1 y att-items-v1 ---


@pytest.mark.asyncio
async def test_signals_con_digest_variante_att_text_y_att_items():
    scorer, _ = crear_scorer()
    tender_id = uuid4()
    tender = crear_licitacion(tender_id, nombre="Servicio de jardinería", partidas=[])
    supplier = crear_proveedor(keywords=["mantención de áreas verdes", "poda"])

    digest = armar_digest(
        tender_id,
        resumen_texto="Requiere mantención semanal de césped y poda de árboles.",
        items_desc=["Corte de césped", "Poda en altura"],
    )

    # att-text-v1
    signals_text = await scorer.signals(
        supplier, tender, digest=digest, variant="att-text-v1"
    )
    assert signals_text is not None
    assert signals_text.reranker_score is not None
    assert 0.0 <= signals_text.final_score <= 1.0

    # att-items-v1
    signals_items = await scorer.signals(
        supplier, tender, digest=digest, variant="att-items-v1"
    )
    assert signals_items is not None
    assert 0.0 <= signals_items.final_score <= 1.0


# --- 4. Test Feature Flag MATCHING_SHADOW_ENABLED ---


@pytest.mark.asyncio
async def test_compute_shadow_score_con_flag_apagado_no_escribe_nada(monkeypatch):
    scorer, _ = crear_scorer()
    shadow_repo = InMemoryMatchingShadowRepository()
    settings = Settings(
        supabase_url="https://supabase-test.local",
        supabase_publishable_key="pub-key",
        supabase_jwt_secret="jwt-secret",
        postgres_password="pass",
        gemini_api_key="gemini-key",
        gemini_model="gemini-flash",
        mercado_publico_api_key="mp-key",
        matching_shadow_enabled=False,
    )

    use_case = ComputeShadowScoreUseCase(
        scorer=scorer, shadow_repo=shadow_repo, settings=settings
    )

    tender = crear_licitacion(uuid4(), nombre="Suministro de computadores")
    supplier = crear_proveedor(keywords=["laptops", "computadores"])
    digest = armar_digest(tender.id, "Notebooks i7 16GB")

    res = await use_case.execute(supplier, tender, digest=digest)
    assert res is None
    assert len(shadow_repo.scores) == 0


@pytest.mark.asyncio
async def test_compute_shadow_score_con_flag_encendido_persiste_registro():
    scorer, matching_repo = crear_scorer()
    shadow_repo = InMemoryMatchingShadowRepository()
    settings = Settings(
        supabase_url="https://supabase-test.local",
        supabase_publishable_key="pub-key",
        supabase_jwt_secret="jwt-secret",
        postgres_password="pass",
        gemini_api_key="gemini-key",
        gemini_model="gemini-flash",
        mercado_publico_api_key="mp-key",
        matching_shadow_enabled=True,
    )

    use_case = ComputeShadowScoreUseCase(
        scorer=scorer, shadow_repo=shadow_repo, settings=settings
    )

    tender = crear_licitacion(uuid4(), nombre="Suministro de computadores")
    supplier = crear_proveedor(keywords=["laptops", "computadores"])
    digest = armar_digest(tender.id, "Notebooks i7 16GB")
    ranking_id = uuid4()

    res = await use_case.execute(
        supplier, tender, digest=digest, ranking_id=ranking_id, variant="att-text-v1"
    )

    assert res is not None
    assert res.ranking_id == ranking_id
    assert res.supplier_id == supplier.id
    assert res.tender_id == tender.id
    assert res.variant == "att-text-v1"
    assert len(shadow_repo.scores) == 1

    # matching_result de producción NO debe haber sido alterado
    assert len(matching_repo.results) == 0


# --- 5. Test ReplayShadowRankingUseCase con cálculo de NDCG@10 ---


def test_replay_shadow_ranking_calcula_ndcg_y_delta():
    metrics = RankingMetricsService(k=10)
    replay_uc = ReplayShadowRankingUseCase(metrics_service=metrics)

    ranking_id = uuid4()
    t1 = uuid4()
    t2 = uuid4()
    t3 = uuid4()
    user_id = uuid4()

    # Ranking original servido:
    # Posición 1: t1
    # Posición 2: t2
    # Posición 3: t3
    impressions = [
        RankingImpression(
            id=uuid4(),
            ranking_id=ranking_id,
            supplier_id=uuid4(),
            user_id=user_id,
            tender_id=t1,
            position=1,
            score=0.85,
            model_version="v1",
        ),
        RankingImpression(
            id=uuid4(),
            ranking_id=ranking_id,
            supplier_id=uuid4(),
            user_id=user_id,
            tender_id=t2,
            position=2,
            score=0.75,
            model_version="v1",
        ),
        RankingImpression(
            id=uuid4(),
            ranking_id=ranking_id,
            supplier_id=uuid4(),
            user_id=user_id,
            tender_id=t3,
            position=3,
            score=0.65,
            model_version="v1",
        ),
    ]

    # Interacciones reales del usuario:
    # t3 tuvo la interacción más valiosa (análisis = ganancia 3)
    # t2 tuvo ver detalle (ganancia 1)
    # t1 no tuvo interacciones (ganancia 0)
    interactions = [
        TenderInteraction(
            id=uuid4(),
            tender_id=t3,
            kind="analisis",
            user_id=uuid4(),
            ranking_id=ranking_id,
            position=3,
            source="matches",
        ),
        TenderInteraction(
            id=uuid4(),
            tender_id=t2,
            kind="detalle",
            user_id=uuid4(),
            ranking_id=ranking_id,
            position=2,
            source="matches",
        ),
    ]

    # Variante en sombra con anexos:
    # Sombra descubrió que t3 era el más afín (score 0.95), seguido de t2 (0.80), y t1 (0.60)
    shadow_scores = {
        (ranking_id, t3): 0.95,
        (ranking_id, t2): 0.80,
        (ranking_id, t1): 0.60,
    }

    result = replay_uc.execute(impressions, interactions, shadow_scores)

    assert result.rankings_evaluated == 1
    # Con el reordenamiento de sombra, t3 (ganancia 3) pasa a la posición 1,
    # por lo que el NDCG de sombra debe ser significativamente mayor que el baseline
    assert result.shadow_ndcg_at_10 > result.baseline_ndcg_at_10
    assert result.delta_ndcg > 0.0
