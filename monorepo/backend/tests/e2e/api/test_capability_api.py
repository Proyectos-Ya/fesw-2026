"""El banco de capacidades opera sobre la empresa activa y respeta el rol (HU-20, B0b).

Recorre la app completa —token real, cambio de espacio de trabajo, cableado de
`bootstrap`— con los repositorios del banco en memoria.
"""

from uuid import UUID

import pytest
from httpx import AsyncClient

from app.application.use_cases.capabilities.add_capability_evidence import (
    AddCapabilityEvidenceUseCase,
)
from app.application.use_cases.capabilities.answer_capability_question import (
    AnswerCapabilityQuestionUseCase,
)
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.bootstrap.capabilities import (
    get_add_capability_evidence_use_case,
    get_answer_capability_question_use_case,
    get_build_experience_catalog_use_case,
)
from app.domain.entities.capability import CapabilityOption, CapabilityQuestion
from app.main import app
from tests.e2e.api.test_empresa_activa_api import (
    SUB_A,
    SUB_B,
    SUB_C,
    _cambiar,
    _crear_empresa,
    _headers,
    _unir,
)
from tests.unit.application.fakes import (
    InMemoryCapabilityAnswerRepository,
    InMemoryCapabilityEvidenceRepository,
    InMemoryCapabilityQuestionRepository,
)

VIALES = CapabilityQuestion(
    question="¿Tiene experiencia en obras viales?",
    target_field="experiencia:obras-viales",
    category="construccion",
    kind="experiencia_proyecto",
    work_type="obras viales",
    options=[
        CapabilityOption(label="No", polarity="negativa"),
        CapabilityOption(label="Sí", polarity="afirmativa"),
    ],
)


@pytest.fixture
def banco(api: AsyncClient):
    questions = InMemoryCapabilityQuestionRepository([VIALES])
    answers = InMemoryCapabilityAnswerRepository()
    evidences = InMemoryCapabilityEvidenceRepository()
    suppliers = api.proveedores

    app.dependency_overrides[get_build_experience_catalog_use_case] = lambda: (
        BuildExperienceCatalogUseCase(suppliers, questions, answers, evidences)
    )
    app.dependency_overrides[get_answer_capability_question_use_case] = (
        lambda: AnswerCapabilityQuestionUseCase(suppliers, questions, answers)
    )
    app.dependency_overrides[get_add_capability_evidence_use_case] = lambda: (
        AddCapabilityEvidenceUseCase(suppliers, questions, answers, evidences)
    )
    return answers, evidences


@pytest.fixture
async def empresas(api: AsyncClient):
    """A es dueño de la Empresa 1 y MEMBER de la 2 (activa); C es VIEWER de la 2."""
    headers_a = _headers(api, SUB_A, "user_a@test.cl")
    headers_b = _headers(api, SUB_B, "user_b@test.cl")
    headers_c = _headers(api, SUB_C, "user_c@test.cl")
    empresa_1 = await _crear_empresa(api, headers_a, "76.123.456-0", "Empresa Uno SpA")
    empresa_2 = await _crear_empresa(api, headers_b, "77.654.321-7", "Empresa Dos Ltda")
    await _unir(api, headers_b, headers_a, "user_a@test.cl", empresa_2)
    await _unir(api, headers_b, headers_c, "user_c@test.cl", empresa_2, role="viewer")
    await _cambiar(api, headers_a, empresa_2)
    await _cambiar(api, headers_c, empresa_2)
    return headers_a, headers_b, headers_c, UUID(empresa_1), UUID(empresa_2)


async def _ids_del_catalogo(api: AsyncClient, headers: dict[str, str]) -> set[str]:
    resp = await api.get("/capabilities/catalog", headers=headers)
    assert resp.status_code == 200, resp.text
    return {item["id"] for item in resp.json()["items"]}


@pytest.mark.asyncio
async def test_un_miembro_responde_por_la_empresa_activa_y_la_duena_lo_ve(
    api: AsyncClient, banco, empresas
):
    answers, _ = banco
    headers_a, headers_b, _, empresa_1, empresa_2 = empresas

    resp = await api.post(
        f"/capabilities/questions/{VIALES.id}/answer",
        json={"answer": "Sí"},
        headers=headers_a,
    )

    assert resp.status_code == 200, resp.text
    assert await answers.get(empresa_2, VIALES.id) is not None
    assert await answers.get(empresa_1, VIALES.id) is None
    assert f"capacidad:{VIALES.id}" in await _ids_del_catalogo(api, headers_b)


@pytest.mark.asyncio
async def test_el_proyecto_queda_en_la_empresa_activa(
    api: AsyncClient, banco, empresas
):
    _, evidences = banco
    headers_a, headers_b, _, _, empresa_2 = empresas
    await api.post(
        f"/capabilities/questions/{VIALES.id}/answer",
        json={"answer": "Sí"},
        headers=headers_a,
    )

    resp = await api.post(
        f"/capabilities/questions/{VIALES.id}/evidence",
        json={"title": "Pavimentación calle Los Aromos", "year": 2024},
        headers=headers_a,
    )

    assert resp.status_code == 201, resp.text
    [evidencia] = evidences.filas
    assert evidencia.supplier_id == empresa_2
    assert f"evidencia:{evidencia.id}" in await _ids_del_catalogo(api, headers_b)


@pytest.mark.asyncio
async def test_un_viewer_ve_el_catalogo_pero_no_responde(
    api: AsyncClient, banco, empresas
):
    answers, _ = banco
    _, _, headers_c, _, empresa_2 = empresas

    resp = await api.post(
        f"/capabilities/questions/{VIALES.id}/answer",
        json={"answer": "Sí"},
        headers=headers_c,
    )

    assert resp.status_code == 403
    assert await answers.get(empresa_2, VIALES.id) is None
    assert (
        await api.get("/capabilities/catalog", headers=headers_c)
    ).status_code == 200
