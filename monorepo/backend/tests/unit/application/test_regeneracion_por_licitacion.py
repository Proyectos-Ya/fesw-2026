"""El análisis de Gemini tiene que regenerarse cuando cambia la licitación.

`get_or_create_deep_analysis` regeneraba solo si cambiaba **el proveedor**. No
había comparación equivalente contra la licitación, y era inocuo mientras las
licitaciones nunca se actualizaban (6.3).

Deja de serlo en cuanto la ingesta refresca las existentes: una licitación cuyo
alcance cambió seguiría mostrando una justificación escrita sobre el contenido
anterior. Eso no es un dato viejo, es **contenido incorrecto presentado como
vigente**, y el usuario lo lee y le cree. Por eso 6.4 era prerrequisito
obligatorio de 6.3 y va en el mismo cambio.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.use_cases.deep_analysis.get_or_create_deep_analysis import (
    GetOrCreateDeepAnalysisUseCase,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.matching_result import MatchingResult

from .fakes import InMemorySupplierRepository
from .test_get_or_create_deep_analysis import (
    FakeDeepAnalysisService,
    FakeMatchingResultRepositoryForAnalysis,
    FakeTenderRepositoryForAnalysis,
    create_dummy_supplier,
    create_dummy_tender,
)

pytestmark = pytest.mark.asyncio

AHORA = datetime.now(UTC).replace(tzinfo=None)


async def _correr(
    *, tender_updated: datetime, supplier_updated: datetime, analysis_updated: datetime
) -> FakeDeepAnalysisService:
    """Monta el caso de uso con esas tres marcas de tiempo y lo ejecuta."""
    supplier_id, user_id, tender_id = uuid4(), uuid4(), uuid4()

    supplier_repo = InMemorySupplierRepository()
    await supplier_repo.save(
        create_dummy_supplier(supplier_id, user_id, supplier_updated)
    )

    tender_repo = FakeTenderRepositoryForAnalysis()
    tender = create_dummy_tender(tender_id)
    tender.updated_at = tender_updated
    tender_repo.tenders[tender_id] = tender

    matching_result_repo = FakeMatchingResultRepositoryForAnalysis()
    await matching_result_repo.save_bulk(
        [
            MatchingResult(
                supplier_id=supplier_id,
                tender_id=tender_id,
                similarity_score=0.8,
                final_score=0.85,
                model_version="v1",
            )
        ]
    )

    await tender_repo.save_deep_analysis(
        DeepAnalysis(
            tender_id=tender_id,
            supplier_id=supplier_id,
            compatibility_score=85.0,
            recommendation="Evaluar con cautela",
            justification="Escrita sobre el contenido anterior",
            prompt_instruction="Instruccion previa",
            created_at=analysis_updated,
            updated_at=analysis_updated,
        )
    )

    servicio = FakeDeepAnalysisService()
    use_case = GetOrCreateDeepAnalysisUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        matching_result_repo=matching_result_repo,
        deep_analysis_service=servicio,
    )
    await use_case.execute(tender_id=tender_id, user_id=user_id)
    return servicio


class TestRegeneracionPorLicitacion:
    async def test_una_licitacion_mas_nueva_que_el_analisis_lo_regenera(self):
        servicio = await _correr(
            tender_updated=AHORA,
            supplier_updated=AHORA - timedelta(days=2),
            analysis_updated=AHORA - timedelta(days=1),
        )

        assert len(servicio.calls) == 1

    async def test_una_licitacion_mas_vieja_no_regenera_nada(self):
        """Sin esto, la corrida diaria regeneraría todo con Gemini sin motivo."""
        servicio = await _correr(
            tender_updated=AHORA - timedelta(days=2),
            supplier_updated=AHORA - timedelta(days=2),
            analysis_updated=AHORA - timedelta(days=1),
        )

        assert servicio.calls == []

    async def test_sigue_regenerando_cuando_cambia_el_proveedor(self):
        """La condición que ya existía no se pierde al sumar la nueva."""
        servicio = await _correr(
            tender_updated=AHORA - timedelta(days=2),
            supplier_updated=AHORA,
            analysis_updated=AHORA - timedelta(days=1),
        )

        assert len(servicio.calls) == 1

    async def test_conserva_el_prompt_previo_del_usuario(self):
        """La regeneración es silenciosa: no puede perder la personalización."""
        servicio = await _correr(
            tender_updated=AHORA,
            supplier_updated=AHORA - timedelta(days=2),
            analysis_updated=AHORA - timedelta(days=1),
        )

        assert servicio.calls[0][3] == "Instruccion previa"
