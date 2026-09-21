"""Pruebas del análisis de compatibilidad IA.

Dos reglas mandan acá: el análisis no se limita a las licitaciones que el
sistema recomendó —si falta el puntaje, se calcula y se guarda— y nunca se
genera solo desde la ficha, que consulta con `only_if_exists`.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.services.compatibility_scorer import CompatibilityScorer
from app.application.services.deep_analysis_service import IDeepAnalysisService
from app.application.use_cases.deep_analysis.get_or_create_deep_analysis import (
    GetOrCreateDeepAnalysisUseCase,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_errors import TenderClosedForAnalysis, TenderNotFound
from app.shared.constants import TENDER_STATUSES
from tests.unit.application.fakes import (
    FakeRerankerService,
    FakeWeightingService,
    InMemoryMatchingResultRepository,
    InMemorySupplierRepository,
    InMemoryTenderRepository,
)


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def create_dummy_tender(
    tender_id: UUID,
    updated_at: datetime | None = None,
    cierra_en_horas: int = 48,
    status_code: str = TENDER_STATUSES["PUBLISHED"],
) -> Tender:
    """Licitación de prueba: abierta y sin cambios recientes.

    `updated_at` va deliberadamente en el pasado: desde que el análisis se
    regenera también cuando cambia la licitación (6.4), una licitación con
    `updated_at = now` haría que cualquier análisis anterior se considere
    obsoleto. Los tests que quieren ese escenario lo piden explícitamente.
    """
    now = datetime.now(UTC).replace(tzinfo=None)
    return Tender(
        id=tender_id,
        updated_at=updated_at or (now - timedelta(days=7)),
        code=f"LIC-{tender_id}",
        name="Licitación de Prueba",
        description="Descripción",
        status_id=1,
        status_code=status_code,
        published_at=now - timedelta(days=8),
        closing_at=now + timedelta(hours=cierra_en_horas),
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


@dataclass
class Escenario:
    use_case: GetOrCreateDeepAnalysisUseCase
    tender_repo: InMemoryTenderRepository
    matching_result_repo: InMemoryMatchingResultRepository
    ai_service: FakeDeepAnalysisService
    supplier: Supplier
    user_id: UUID
    tender_id: UUID


async def armar(
    supplier_updated_at: datetime | None = None,
    tender: Tender | None = None,
    con_supplier: bool = True,
    con_tender: bool = True,
) -> Escenario:
    now = datetime.now(UTC).replace(tzinfo=None)
    supplier_id, user_id = uuid4(), uuid4()

    supplier_repo = InMemorySupplierRepository()
    supplier = create_dummy_supplier(
        supplier_id, user_id, supplier_updated_at or (now - timedelta(hours=2))
    )
    if con_supplier:
        await supplier_repo.save(supplier)

    tender_repo = InMemoryTenderRepository()
    licitacion = tender or create_dummy_tender(uuid4())
    if con_tender:
        tender_repo.tenders[licitacion.id] = licitacion

    matching_result_repo = InMemoryMatchingResultRepository()
    ai_service = FakeDeepAnalysisService()

    return Escenario(
        use_case=GetOrCreateDeepAnalysisUseCase(
            supplier_repo=supplier_repo,
            tender_repo=tender_repo,
            matching_result_repo=matching_result_repo,
            deep_analysis_service=ai_service,
            scorer=CompatibilityScorer(
                reranker_service=FakeRerankerService(),
                weighting_service=FakeWeightingService(),
                matching_result_repo=matching_result_repo,
            ),
        ),
        tender_repo=tender_repo,
        matching_result_repo=matching_result_repo,
        ai_service=ai_service,
        supplier=supplier,
        user_id=user_id,
        tender_id=licitacion.id,
    )


async def guardar_match(
    esc: Escenario, final_score: float = 0.85, source: str = "ranking"
) -> MatchingResult:
    match = MatchingResult(
        supplier_id=esc.supplier.id,
        tender_id=esc.tender_id,
        similarity_score=0.80 if source == "ranking" else None,
        final_score=final_score,
        model_version="v1",
        source=source,  # type: ignore[arg-type]
    )
    if source == "ranking":
        await esc.matching_result_repo.save_bulk([match])
    else:
        await esc.matching_result_repo.save_on_demand(match)
    return match


async def guardar_analisis(
    esc: Escenario,
    generado_hace: timedelta,
    marca_tender: datetime | None = None,
    marca_supplier: datetime | None = None,
) -> DeepAnalysis:
    """Deja un análisis guardado.

    Las marcas son las que el análisis vio al generarse; por omisión coinciden
    con las actuales, o sea que nada cambió desde entonces.
    """
    now = datetime.now(UTC).replace(tzinfo=None)
    licitacion = esc.tender_repo.tenders[esc.tender_id]
    analisis = DeepAnalysis(
        tender_id=esc.tender_id,
        supplier_id=esc.supplier.id,
        compatibility_score=85.0,
        recommendation="Evaluar con cautela",
        justification="Ya calculado",
        prompt_instruction="Instruccion previa",
        tender_updated_at=marca_tender or licitacion.updated_at,
        supplier_updated_at=marca_supplier or esc.supplier.updated_at,
        created_at=now - generado_hace,
        updated_at=now - generado_hace,
    )
    return await esc.tender_repo.save_deep_analysis(analisis)


# ---------------------------------------------------------------------------
# Pruebas Unitarias del Caso de Uso
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_supplier_not_found_raises():
    """Lanza SupplierNotFoundForUser si el usuario no tiene perfil de proveedor."""
    esc = await armar(con_supplier=False)

    with pytest.raises(SupplierNotFoundForUser):
        await esc.use_case.execute(tender_id=esc.tender_id, user_id=esc.user_id)


@pytest.mark.asyncio
async def test_tender_not_found_raises():
    """Lanza TenderNotFound si la licitación no existe en la base de datos."""
    esc = await armar(con_tender=False)

    with pytest.raises(TenderNotFound):
        await esc.use_case.execute(tender_id=esc.tender_id, user_id=esc.user_id)


@pytest.mark.asyncio
async def test_sin_fila_de_matching_calcula_el_puntaje_y_lo_persiste():
    """Una licitación fuera del top-N se analiza igual: el puntaje se calcula al vuelo.

    Antes esto era un 404. Como el usuario llega a estas licitaciones desde el
    buscador, el resultado se guarda para que la próxima visita lo encuentre.
    """
    esc = await armar()

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id
    )

    assert resultado.analysis is not None
    assert len(esc.ai_service.calls) == 1
    fila = await esc.matching_result_repo.get_by_proveedor_and_licitacion(
        esc.supplier.id, esc.tender_id
    )
    assert fila is not None
    assert fila.source == "on_demand"
    # El análisis justifica exactamente el puntaje que quedó guardado.
    assert resultado.analysis.compatibility_score == pytest.approx(
        fila.final_score * 100
    )


@pytest.mark.asyncio
async def test_create_new_analysis_success():
    """Crea y persiste un nuevo análisis usando el puntaje ya calculado del ranking."""
    esc = await armar()
    await guardar_match(esc, final_score=0.85)

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id, prompt_instruction="Usar ISO"
    )

    assert resultado.analysis is not None
    assert resultado.analysis.compatibility_score == 85.0  # final_score * 100
    assert resultado.analysis.recommendation == "Postular"
    assert resultado.analysis.prompt_instruction == "Usar ISO"
    assert esc.ai_service.calls == [
        (esc.tender_id, esc.supplier.id, 85.0, "Usar ISO")
    ]

    persisted = await esc.tender_repo.get_deep_analysis(
        esc.tender_id, esc.supplier.id
    )
    assert persisted is not None
    assert persisted.compatibility_score == 85.0


@pytest.mark.asyncio
async def test_return_existing_analysis_no_profile_change():
    """Retorna el análisis existente si nada cambió desde que se generó."""
    esc = await armar()
    await guardar_match(esc)
    await guardar_analisis(esc, generado_hace=timedelta(hours=1))

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id
    )

    assert resultado.analysis is not None
    assert resultado.analysis.recommendation == "Evaluar con cautela"
    assert resultado.analysis.justification == "Ya calculado"
    assert resultado.is_outdated is False
    assert esc.ai_service.calls == []


@pytest.mark.asyncio
async def test_devuelve_el_analisis_guardado_aunque_ya_no_haya_fila_de_matching():
    """Salir del top-N no puede esconder un análisis que el usuario ya generó."""
    esc = await armar()
    await guardar_analisis(esc, generado_hace=timedelta(hours=1))

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id
    )

    assert resultado.analysis is not None
    assert resultado.analysis.justification == "Ya calculado"
    assert esc.ai_service.calls == []


@pytest.mark.asyncio
async def test_regenerate_automatically_on_profile_updated():
    """Regenera solo (manteniendo el prompt previo) si el perfil cambió después."""
    now = datetime.now(UTC).replace(tzinfo=None)
    esc = await armar(supplier_updated_at=now - timedelta(minutes=10))
    await guardar_match(esc)
    await guardar_analisis(
        esc,
        generado_hace=timedelta(minutes=30),
        marca_supplier=now - timedelta(hours=5),
    )

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id
    )

    assert esc.ai_service.calls == [
        (esc.tender_id, esc.supplier.id, 85.0, "Instruccion previa")
    ]
    assert resultado.analysis is not None
    assert resultado.analysis.recommendation == "Postular"
    assert resultado.analysis.prompt_instruction == "Instruccion previa"


@pytest.mark.asyncio
async def test_manual_force_regenerate_overwrites_prompt():
    """Con force_regenerate=True se aplica y guarda el prompt nuevo."""
    esc = await armar()
    await guardar_match(esc)
    await guardar_analisis(esc, generado_hace=timedelta(hours=1))

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id,
        user_id=esc.user_id,
        force_regenerate=True,
        prompt_instruction="Priorizar certificaciones ISO 14001",
    )

    assert esc.ai_service.calls == [
        (
            esc.tender_id,
            esc.supplier.id,
            85.0,
            "Priorizar certificaciones ISO 14001",
        )
    ]
    assert resultado.analysis is not None
    assert resultado.analysis.prompt_instruction == "Priorizar certificaciones ISO 14001"


@pytest.mark.asyncio
async def test_regenerar_no_convierte_una_fila_del_ranking_en_calculo_a_pedido():
    """El puntaje del ranking manda: reescribirlo sacaría la licitación del dashboard."""
    esc = await armar()
    await guardar_match(esc, final_score=0.85, source="ranking")

    await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id, force_regenerate=True
    )

    fila = await esc.matching_result_repo.get_by_proveedor_and_licitacion(
        esc.supplier.id, esc.tender_id
    )
    assert fila is not None
    assert fila.source == "ranking"
    assert fila.final_score == pytest.approx(0.85)
    assert esc.ai_service.calls[0][2] == 85.0


@pytest.mark.asyncio
async def test_regenerar_si_actualiza_un_calculo_a_pedido():
    """El puntaje a pedido no lo refresca nadie más: al regenerar, se recalcula."""
    esc = await armar()
    await guardar_match(esc, final_score=0.10, source="on_demand")

    await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id, force_regenerate=True
    )

    fila = await esc.matching_result_repo.get_by_proveedor_and_licitacion(
        esc.supplier.id, esc.tender_id
    )
    assert fila is not None
    assert fila.source == "on_demand"
    assert fila.final_score != pytest.approx(0.10)


@pytest.mark.asyncio
async def test_only_if_exists_returns_none_when_missing():
    """Sin análisis previo, la ficha no genera nada: devuelve None."""
    esc = await armar()
    await guardar_match(esc)

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id, only_if_exists=True
    )

    assert resultado.analysis is None
    assert esc.ai_service.calls == []


@pytest.mark.asyncio
async def test_only_if_exists_returns_existing_when_present():
    """Con análisis previo y sin cambios, la ficha lo muestra tal cual."""
    esc = await armar()
    await guardar_match(esc)
    await guardar_analisis(esc, generado_hace=timedelta(hours=1))

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id, only_if_exists=True
    )

    assert resultado.analysis is not None
    assert resultado.analysis.justification == "Ya calculado"
    assert resultado.is_outdated is False
    assert esc.ai_service.calls == []


@pytest.mark.asyncio
async def test_only_if_exists_avisa_que_quedo_desactualizado_sin_regenerar():
    """La ficha informa el desfase; regenerar es decisión del usuario, no un efecto de abrirla."""
    now = datetime.now(UTC).replace(tzinfo=None)
    esc = await armar(supplier_updated_at=now - timedelta(minutes=5))
    await guardar_match(esc)
    await guardar_analisis(
        esc,
        generado_hace=timedelta(minutes=30),
        marca_supplier=now - timedelta(hours=5),
    )

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id, only_if_exists=True
    )

    assert resultado.is_outdated is True
    assert resultado.analysis is not None
    assert resultado.analysis.justification == "Ya calculado"
    assert esc.ai_service.calls == []


@pytest.mark.asyncio
async def test_licitacion_cerrada_sin_analisis_no_genera():
    """A una licitación cerrada ya no se postula: generar el análisis no ayuda a decidir."""
    cerrada = create_dummy_tender(uuid4(), cierra_en_horas=-3)
    esc = await armar(tender=cerrada)

    with pytest.raises(TenderClosedForAnalysis):
        await esc.use_case.execute(tender_id=esc.tender_id, user_id=esc.user_id)

    assert esc.ai_service.calls == []


@pytest.mark.asyncio
async def test_licitacion_cerrada_con_analisis_lo_devuelve_sin_regenerar():
    """Lo ya generado sigue visible: es el registro de lo que se evaluó."""
    now = datetime.now(UTC).replace(tzinfo=None)
    cerrada = create_dummy_tender(uuid4(), cierra_en_horas=-3)
    esc = await armar(supplier_updated_at=now - timedelta(minutes=5), tender=cerrada)
    await guardar_analisis(esc, generado_hace=timedelta(minutes=30))

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id, force_regenerate=True
    )

    assert resultado.analysis is not None
    assert resultado.analysis.justification == "Ya calculado"
    # No se marca desactualizado: no hay forma de actualizarlo.
    assert resultado.is_outdated is False
    assert esc.ai_service.calls == []


@pytest.mark.asyncio
async def test_una_licitacion_con_fecha_futura_no_se_marca_desactualizada():
    """Es lo que rompía en local: filas restauradas con la hora adelantada.

    Comparando el orden de las fechas, esa licitación es siempre "más nueva"
    que el análisis —incluso que uno recién generado—, así que el aviso no se
    podía quitar nunca.
    """
    ahora = datetime.now(UTC).replace(tzinfo=None)
    futura = create_dummy_tender(uuid4(), updated_at=ahora + timedelta(days=9))
    esc = await armar(tender=futura)
    await guardar_analisis(esc, generado_hace=timedelta(minutes=1))

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id, only_if_exists=True
    )

    assert resultado.is_outdated is False
    assert esc.ai_service.calls == []


@pytest.mark.asyncio
async def test_al_generar_guarda_contra_que_version_se_escribio():
    """Sin estas marcas, la siguiente visita no tiene con qué comparar."""
    esc = await armar()
    await guardar_match(esc)

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id
    )

    assert resultado.analysis is not None
    licitacion = esc.tender_repo.tenders[esc.tender_id]
    assert resultado.analysis.tender_updated_at == licitacion.updated_at
    assert resultado.analysis.supplier_updated_at == esc.supplier.updated_at


async def guardar_analisis_sin_marcas(
    esc: Escenario, generado_hace: timedelta
) -> DeepAnalysis:
    """Un análisis como los que quedaron antes de existir las marcas."""
    analisis = await guardar_analisis(esc, generado_hace=generado_hace)
    analisis.tender_updated_at = None
    analisis.supplier_updated_at = None
    return await esc.tender_repo.save_deep_analysis(analisis)


@pytest.mark.asyncio
async def test_un_analisis_sin_marcas_sigue_avisando_si_cambio_el_perfil():
    """Los generados antes de la columna no pueden quedarse mudos.

    Del proveedor sí se puede comparar el orden: su `updated_at` lo escribe
    esta misma aplicación, con el mismo reloj que el análisis.
    """
    ahora = datetime.now(UTC).replace(tzinfo=None)
    esc = await armar(supplier_updated_at=ahora)
    await guardar_match(esc)
    await guardar_analisis_sin_marcas(esc, generado_hace=timedelta(hours=1))

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id, only_if_exists=True
    )

    assert resultado.is_outdated is True


@pytest.mark.asyncio
async def test_un_analisis_sin_marcas_no_avisa_si_no_cambio_nada():
    ahora = datetime.now(UTC).replace(tzinfo=None)
    esc = await armar(supplier_updated_at=ahora - timedelta(days=2))
    await guardar_match(esc)
    await guardar_analisis_sin_marcas(esc, generado_hace=timedelta(hours=1))

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id, only_if_exists=True
    )

    assert resultado.is_outdated is False


@pytest.mark.asyncio
async def test_un_analisis_sin_marcas_ignora_la_fecha_de_la_licitacion():
    """Es la fecha que no es confiable: puede venir de datos cargados a mano."""
    ahora = datetime.now(UTC).replace(tzinfo=None)
    futura = create_dummy_tender(uuid4(), updated_at=ahora + timedelta(days=9))
    esc = await armar(supplier_updated_at=ahora - timedelta(days=2), tender=futura)
    await guardar_analisis_sin_marcas(esc, generado_hace=timedelta(hours=1))

    resultado = await esc.use_case.execute(
        tender_id=esc.tender_id, user_id=esc.user_id, only_if_exists=True
    )

    assert resultado.is_outdated is False
