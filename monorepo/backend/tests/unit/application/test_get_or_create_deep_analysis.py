from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.schemas.tender_schema import TenderFilterCriteria
from app.application.services.deep_analysis_service import IDeepAnalysisService
from app.application.use_cases.deep_analysis.get_or_create_deep_analysis import (
    GetOrCreateDeepAnalysisUseCase,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.errors.matching_errors import ScoreMatchingNoEncontrado
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_errors import TenderNotFound
from tests.unit.application.fakes import InMemorySupplierRepository

# ---------------------------------------------------------------------------
# Fakes específicos para la prueba del caso de uso
# ---------------------------------------------------------------------------


class FakeTenderRepositoryForAnalysis(ITenderRepository):
    def __init__(self):
        self.tenders: dict[UUID, Tender] = {}
        self.analyses: dict[tuple[UUID, UUID], DeepAnalysis] = {}

    async def get_tenders(self, filters: TenderFilters) -> list[Tender]:
        results = []
        for t in self.tenders.values():
            if filters.ids and t.id not in filters.ids:
                continue
            results.append(t)
        return results

    async def search_tenders(
        self,
        criteria: TenderFilterCriteria,
        limit: int,
        offset: int = 0,
        q: str | None = None,
    ) -> tuple[list[Tender], int]:  # noqa: ARG002
        return ([], 0)

    async def get_by_code(self, code: str) -> Any | None:
        return None

    async def get_or_create_buyer(
        self,
        rut: str,
        name: str,
        region_id: int,
        comuna_id: int | None = None,
        comuna_resolution_source: str | None = None,
    ) -> str:
        return rut

    async def get_comuna_id_by_name(self, name: str) -> int | None:
        return None

    async def get_provincia_id_by_comuna_id(self, comuna_id: int) -> int | None:
        return None

    async def save_complex_tender(self, tender_model: Any, items: list[Any]) -> None:
        pass

    async def get_or_create_status(self, status_id: int, code: str) -> int:
        return status_id

    async def rollback(self) -> None:
        pass

    async def get_deep_analysis(
        self, tender_id: UUID, supplier_id: UUID
    ) -> DeepAnalysis | None:
        return self.analyses.get((tender_id, supplier_id))

    async def save_deep_analysis(self, deep_analysis: DeepAnalysis) -> DeepAnalysis:
        self.analyses[(deep_analysis.tender_id, deep_analysis.supplier_id)] = (
            deep_analysis
        )
        return deep_analysis

    async def get_latest_tender_created_at(self) -> datetime | None:
        if not self.tenders:
            return None
        return max(
            (t.created_at for t in self.tenders.values() if t.created_at is not None),
            default=None,
        )


class FakeMatchingResultRepositoryForAnalysis(IMatchingResultRepository):
    def __init__(self):
        self.results: dict[tuple[UUID, UUID], MatchingResult] = {}

    async def save_bulk(self, results: list[MatchingResult]) -> None:
        for r in results:
            self.results[(r.supplier_id, r.tender_id)] = r

    async def get_by_supplier_id(self, supplier_id: UUID) -> list[MatchingResult]:
        return [r for r in self.results.values() if r.supplier_id == supplier_id]

    async def delete_by_supplier_id(self, supplier_id: UUID) -> None:
        pass

    async def get_by_proveedor_and_licitacion(
        self, proveedor_id: UUID, licitacion_id: UUID
    ) -> MatchingResult | None:
        return self.results.get((proveedor_id, licitacion_id))


class FakeDeepAnalysisService(IDeepAnalysisService):
    def __init__(self):
        self.calls = []

    async def analyze_compatibility(
        self,
        tender: Tender,
        supplier: Supplier,
        matching_score: float,
        prompt_instruction: str | None = None,
    ) -> DeepAnalysis:
        self.calls.append((tender.id, supplier.id, matching_score, prompt_instruction))
        now = datetime.now(UTC).replace(tzinfo=None)
        return DeepAnalysis(
            tender_id=tender.id,
            supplier_id=supplier.id,
            compatibility_score=matching_score,
            recommendation="Postular",
            justification="Cumple con todo.",
            prompt_instruction=prompt_instruction,
            created_at=now,
            updated_at=now,
        )


# Helper para crear objetos de prueba
def create_dummy_tender(tender_id: UUID) -> Tender:
    now = datetime.now(UTC).replace(tzinfo=None)
    return Tender(
        id=tender_id,
        code=f"LIC-{tender_id}",
        name="Licitación de Prueba",
        description="Descripción",
        status_id=1,
        status_code="publicada",
        published_at=now,
        closing_at=now,
        last_change_at=now,
        buyer_rut="11.111.111-1",
        buyer_name="Buyer",
        buyer_unit="Unit",
        items=[],
    )


def create_dummy_supplier(
    supplier_id: UUID, user_id: UUID, updated_at: datetime
) -> Supplier:
    return Supplier(
        id=supplier_id,
        user_id=user_id,
        rut="76086428-5",
        legal_name="Supplier SpA",
        created_at=updated_at - timedelta(days=2),
        updated_at=updated_at,
    )


# ---------------------------------------------------------------------------
# Pruebas Unitarias del Caso de Uso
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_supplier_not_found_raises():
    """Lanza SupplierNotFoundForUser si el usuario no tiene perfil de proveedor."""
    use_case = GetOrCreateDeepAnalysisUseCase(
        supplier_repo=InMemorySupplierRepository(),
        tender_repo=FakeTenderRepositoryForAnalysis(),
        matching_result_repo=FakeMatchingResultRepositoryForAnalysis(),
        deep_analysis_service=FakeDeepAnalysisService(),
    )
    with pytest.raises(SupplierNotFoundForUser):
        await use_case.execute(tender_id=uuid4(), user_id=uuid4())


@pytest.mark.asyncio
async def test_tender_not_found_raises():
    """Lanza TenderNotFound si la licitación no existe en la base de datos."""
    supplier_id = uuid4()
    user_id = uuid4()
    supplier_repo = InMemorySupplierRepository()
    await supplier_repo.save(
        create_dummy_supplier(
            supplier_id, user_id, datetime.now(UTC).replace(tzinfo=None)
        )
    )

    use_case = GetOrCreateDeepAnalysisUseCase(
        supplier_repo=supplier_repo,
        tender_repo=FakeTenderRepositoryForAnalysis(),
        matching_result_repo=FakeMatchingResultRepositoryForAnalysis(),
        deep_analysis_service=FakeDeepAnalysisService(),
    )
    with pytest.raises(TenderNotFound):
        await use_case.execute(tender_id=uuid4(), user_id=user_id)


@pytest.mark.asyncio
async def test_matching_score_not_found_raises():
    """Lanza ScoreMatchingNoEncontrado si no existe una recomendación precalculada (matching) para ese par."""
    supplier_id = uuid4()
    user_id = uuid4()
    tender_id = uuid4()

    supplier_repo = InMemorySupplierRepository()
    await supplier_repo.save(
        create_dummy_supplier(
            supplier_id, user_id, datetime.now(UTC).replace(tzinfo=None)
        )
    )

    tender_repo = FakeTenderRepositoryForAnalysis()
    tender_repo.tenders[tender_id] = create_dummy_tender(tender_id)

    use_case = GetOrCreateDeepAnalysisUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        matching_result_repo=FakeMatchingResultRepositoryForAnalysis(),
        deep_analysis_service=FakeDeepAnalysisService(),
    )
    with pytest.raises(ScoreMatchingNoEncontrado):
        await use_case.execute(tender_id=tender_id, user_id=user_id)


@pytest.mark.asyncio
async def test_create_new_analysis_success():
    """Crea y persiste un nuevo análisis de compatibilidad usando Gemini si no existía previamente."""
    supplier_id = uuid4()
    user_id = uuid4()
    tender_id = uuid4()

    supplier_repo = InMemorySupplierRepository()
    supplier = create_dummy_supplier(
        supplier_id, user_id, datetime.now(UTC).replace(tzinfo=None)
    )
    await supplier_repo.save(supplier)

    tender_repo = FakeTenderRepositoryForAnalysis()
    tender = create_dummy_tender(tender_id)
    tender_repo.tenders[tender_id] = tender

    matching_result_repo = FakeMatchingResultRepositoryForAnalysis()
    matching_result = MatchingResult(
        supplier_id=supplier_id,
        tender_id=tender_id,
        similarity_score=0.80,
        final_score=0.85,
        model_version="v1",
    )
    await matching_result_repo.save_bulk([matching_result])

    ai_service = FakeDeepAnalysisService()
    use_case = GetOrCreateDeepAnalysisUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        matching_result_repo=matching_result_repo,
        deep_analysis_service=ai_service,
    )

    # Ejecutar
    result = await use_case.execute(
        tender_id=tender_id, user_id=user_id, prompt_instruction="Usar ISO"
    )

    # Aserciones
    assert result is not None
    assert result.compatibility_score == 85.0  # final_score * 100
    assert result.recommendation == "Postular"
    assert result.prompt_instruction == "Usar ISO"
    assert len(ai_service.calls) == 1
    assert ai_service.calls[0] == (tender_id, supplier_id, 85.0, "Usar ISO")

    # Verificar persistencia en repo
    persisted = await tender_repo.get_deep_analysis(tender_id, supplier_id)
    assert persisted is not None
    assert persisted.compatibility_score == 85.0


@pytest.mark.asyncio
async def test_return_existing_analysis_no_profile_change():
    """Retorna el análisis existente de inmediato si no hay cambios en el perfil del proveedor y no se fuerza regeneración."""
    supplier_id = uuid4()
    user_id = uuid4()
    tender_id = uuid4()

    # Simulamos que el proveedor se actualizó hace 2 horas y el análisis se generó hace 1 hora (no hay cambios de perfil desde entonces)
    now = datetime.now(UTC).replace(tzinfo=None)
    supplier_repo = InMemorySupplierRepository()
    supplier = create_dummy_supplier(supplier_id, user_id, now - timedelta(hours=2))
    await supplier_repo.save(supplier)

    tender_repo = FakeTenderRepositoryForAnalysis()
    tender_repo.tenders[tender_id] = create_dummy_tender(tender_id)

    matching_result_repo = FakeMatchingResultRepositoryForAnalysis()
    matching_result = MatchingResult(
        supplier_id=supplier_id,
        tender_id=tender_id,
        similarity_score=0.80,
        final_score=0.85,
        model_version="v1",
    )
    await matching_result_repo.save_bulk([matching_result])

    existing_analysis = DeepAnalysis(
        tender_id=tender_id,
        supplier_id=supplier_id,
        compatibility_score=85.0,
        recommendation="Evaluar con cautela",
        justification="Ya calculado",
        prompt_instruction="Instruccion previa",
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
    )
    await tender_repo.save_deep_analysis(existing_analysis)

    ai_service = FakeDeepAnalysisService()
    use_case = GetOrCreateDeepAnalysisUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        matching_result_repo=matching_result_repo,
        deep_analysis_service=ai_service,
    )

    # Ejecutar
    result = await use_case.execute(tender_id=tender_id, user_id=user_id)

    # Debe retornar el existente directamente sin llamar a Gemini
    assert result is not None
    assert result.recommendation == "Evaluar con cautela"
    assert result.justification == "Ya calculado"
    assert len(ai_service.calls) == 0


@pytest.mark.asyncio
async def test_regenerate_automatically_on_profile_updated():
    """Regenera automáticamente y de forma silenciosa el análisis (manteniendo el prompt previo) si supplier.updated_at > deep_analysis.updated_at."""
    supplier_id = uuid4()
    user_id = uuid4()
    tender_id = uuid4()

    # Proveedor actualizado hace 10 minutos
    now = datetime.now(UTC).replace(tzinfo=None)
    supplier_repo = InMemorySupplierRepository()
    supplier = create_dummy_supplier(supplier_id, user_id, now - timedelta(minutes=10))
    await supplier_repo.save(supplier)

    tender_repo = FakeTenderRepositoryForAnalysis()
    tender_repo.tenders[tender_id] = create_dummy_tender(tender_id)

    matching_result_repo = FakeMatchingResultRepositoryForAnalysis()
    matching_result = MatchingResult(
        supplier_id=supplier_id,
        tender_id=tender_id,
        similarity_score=0.80,
        final_score=0.85,
        model_version="v1",
    )
    await matching_result_repo.save_bulk([matching_result])

    # Análisis generado hace 30 minutos (antiguo con respecto a la última actualización del proveedor)
    existing_analysis = DeepAnalysis(
        tender_id=tender_id,
        supplier_id=supplier_id,
        compatibility_score=85.0,
        recommendation="Evaluar con cautela",
        justification="Ya calculado",
        prompt_instruction="Instruccion previa guardada",
        created_at=now - timedelta(minutes=30),
        updated_at=now - timedelta(minutes=30),
    )
    await tender_repo.save_deep_analysis(existing_analysis)

    ai_service = FakeDeepAnalysisService()
    use_case = GetOrCreateDeepAnalysisUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        matching_result_repo=matching_result_repo,
        deep_analysis_service=ai_service,
    )

    # Ejecutar sin forzar regeneración
    result = await use_case.execute(tender_id=tender_id, user_id=user_id)

    # Debe haber regenerado porque el perfil cambió después, reutilizando el prompt anterior
    assert len(ai_service.calls) == 1
    assert ai_service.calls[0] == (
        tender_id,
        supplier_id,
        85.0,
        "Instruccion previa guardada",
    )
    assert result is not None
    assert result.recommendation == "Postular"
    assert result.prompt_instruction == "Instruccion previa guardada"


@pytest.mark.asyncio
async def test_manual_force_regenerate_overwrites_prompt():
    """Regenera manualmente si force_regenerate=True, aplicando y guardando el nuevo prompt_instruction."""
    supplier_id = uuid4()
    user_id = uuid4()
    tender_id = uuid4()

    now = datetime.now(UTC).replace(tzinfo=None)
    supplier_repo = InMemorySupplierRepository()
    supplier = create_dummy_supplier(supplier_id, user_id, now - timedelta(hours=2))
    await supplier_repo.save(supplier)

    tender_repo = FakeTenderRepositoryForAnalysis()
    tender_repo.tenders[tender_id] = create_dummy_tender(tender_id)

    matching_result_repo = FakeMatchingResultRepositoryForAnalysis()
    matching_result = MatchingResult(
        supplier_id=supplier_id,
        tender_id=tender_id,
        similarity_score=0.80,
        final_score=0.85,
        model_version="v1",
    )
    await matching_result_repo.save_bulk([matching_result])

    existing_analysis = DeepAnalysis(
        tender_id=tender_id,
        supplier_id=supplier_id,
        compatibility_score=85.0,
        recommendation="Evaluar con cautela",
        justification="Ya calculado",
        prompt_instruction="Instruccion previa",
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
    )
    await tender_repo.save_deep_analysis(existing_analysis)

    ai_service = FakeDeepAnalysisService()
    use_case = GetOrCreateDeepAnalysisUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        matching_result_repo=matching_result_repo,
        deep_analysis_service=ai_service,
    )

    # Ejecutar forzando regeneración y pasando un nuevo prompt
    result = await use_case.execute(
        tender_id=tender_id,
        user_id=user_id,
        force_regenerate=True,
        prompt_instruction="Priorizar certificaciones ISO 14001",
    )

    # Debe haber llamado a Gemini con el nuevo prompt
    assert len(ai_service.calls) == 1
    assert ai_service.calls[0] == (
        tender_id,
        supplier_id,
        85.0,
        "Priorizar certificaciones ISO 14001",
    )
    assert result is not None
    assert result.prompt_instruction == "Priorizar certificaciones ISO 14001"


@pytest.mark.asyncio
async def test_only_if_exists_returns_none_when_missing():
    """Retorna None si only_if_exists=True y no hay análisis generado previamente."""
    supplier_id = uuid4()
    user_id = uuid4()
    tender_id = uuid4()

    supplier_repo = InMemorySupplierRepository()
    supplier = create_dummy_supplier(
        supplier_id, user_id, datetime.now(UTC).replace(tzinfo=None)
    )
    await supplier_repo.save(supplier)

    tender_repo = FakeTenderRepositoryForAnalysis()
    tender_repo.tenders[tender_id] = create_dummy_tender(tender_id)

    matching_result_repo = FakeMatchingResultRepositoryForAnalysis()
    matching_result = MatchingResult(
        supplier_id=supplier_id,
        tender_id=tender_id,
        similarity_score=0.80,
        final_score=0.85,
        model_version="v1",
    )
    await matching_result_repo.save_bulk([matching_result])

    ai_service = FakeDeepAnalysisService()
    use_case = GetOrCreateDeepAnalysisUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        matching_result_repo=matching_result_repo,
        deep_analysis_service=ai_service,
    )

    # Ejecutar con only_if_exists=True
    result = await use_case.execute(
        tender_id=tender_id, user_id=user_id, only_if_exists=True
    )

    # Debe retornar None y no llamar al LLM
    assert result is None
    assert len(ai_service.calls) == 0


@pytest.mark.asyncio
async def test_only_if_exists_returns_existing_when_present():
    """Retorna el análisis existente si only_if_exists=True y ya existía previamente."""
    supplier_id = uuid4()
    user_id = uuid4()
    tender_id = uuid4()

    now = datetime.now(UTC).replace(tzinfo=None)
    supplier_repo = InMemorySupplierRepository()
    supplier = create_dummy_supplier(supplier_id, user_id, now - timedelta(hours=2))
    await supplier_repo.save(supplier)

    tender_repo = FakeTenderRepositoryForAnalysis()
    tender_repo.tenders[tender_id] = create_dummy_tender(tender_id)

    matching_result_repo = FakeMatchingResultRepositoryForAnalysis()
    matching_result = MatchingResult(
        supplier_id=supplier_id,
        tender_id=tender_id,
        similarity_score=0.80,
        final_score=0.85,
        model_version="v1",
    )
    await matching_result_repo.save_bulk([matching_result])

    existing_analysis = DeepAnalysis(
        tender_id=tender_id,
        supplier_id=supplier_id,
        compatibility_score=85.0,
        recommendation="Evaluar con cautela",
        justification="Ya calculado",
        prompt_instruction="Instruccion previa",
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
    )
    await tender_repo.save_deep_analysis(existing_analysis)

    ai_service = FakeDeepAnalysisService()
    use_case = GetOrCreateDeepAnalysisUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        matching_result_repo=matching_result_repo,
        deep_analysis_service=ai_service,
    )

    # Ejecutar con only_if_exists=True
    result = await use_case.execute(
        tender_id=tender_id, user_id=user_id, only_if_exists=True
    )

    # Debe retornar el análisis existente
    assert result is not None
    assert result.recommendation == "Evaluar con cautela"
    assert result.justification == "Ya calculado"
    assert len(ai_service.calls) == 0
