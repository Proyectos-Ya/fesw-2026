"""Rutas del borrador de postulación sobre la app completa (HU-20, B2).

Token real, cambio de espacio de trabajo y cableado de `bootstrap`; los
repositorios en memoria y una IA falsa.
"""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app import bootstrap
from app.application.services.proposal_ai_service import (
    FeasibilityRequirementDTO,
    FeasibilityResultDTO,
    ProposalAIServiceError,
)
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.application.use_cases.proposals.get_proposal import GetProposalUseCase
from app.application.use_cases.proposals.start_feasibility import (
    StartFeasibilityUseCase,
)
from app.domain.entities.capability import CapabilityOption, CapabilityQuestion
from app.main import app
from app.shared.constants import TENDER_STATUSES
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
    InMemoryProposalDraftRepository,
    InMemoryTenderChatRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.test_score_tender_on_demand import crear_licitacion
from tests.unit.application.test_start_feasibility import FakeProposalAI

# El rubro de las empresas de `_crear_empresa` es "Servicios".
SEC = CapabilityQuestion(
    question="¿Cuenta con certificación SEC?",
    target_field="sec",
    category="servicios",
    kind="certificacion",
    options=[
        CapabilityOption(label="Sí", polarity="afirmativa"),
        CapabilityOption(label="No", polarity="negativa"),
    ],
)


class FalloDeIA(FakeProposalAI):
    async def analyze_feasibility(self, *args, **kwargs):
        raise ProposalAIServiceError("Gemini no responde")


@pytest.fixture
def entorno(api: AsyncClient):
    tenders = InMemoryTenderRepository()
    drafts = InMemoryProposalDraftRepository()
    questions = InMemoryCapabilityQuestionRepository([SEC])
    answers = InMemoryCapabilityAnswerRepository()
    evidences = InMemoryCapabilityEvidenceRepository()
    suppliers = api.proveedores
    ia = {
        "servicio": FakeProposalAI(
            FeasibilityResultDTO(
                requirements=[
                    FeasibilityRequirementDTO(
                        text="Deberá contar con certificación SEC.",
                        kind="certificacion",
                        mandatory=True,
                        origin="Descripción",
                        question_key="sec",
                    )
                ]
            )
        )
    }

    app.dependency_overrides[bootstrap.get_start_feasibility_use_case] = lambda: (
        StartFeasibilityUseCase(
            supplier_repo=suppliers,
            tender_repo=tenders,
            draft_repo=drafts,
            question_repo=questions,
            answer_repo=answers,
            catalog_use_case=BuildExperienceCatalogUseCase(
                suppliers, questions, answers, evidences
            ),
            chat_repo=InMemoryTenderChatRepository(),
            ai_service=ia["servicio"],
        )
    )
    app.dependency_overrides[bootstrap.get_proposal_use_case] = lambda: (
        GetProposalUseCase(suppliers, tenders, drafts)
    )

    tender_id = uuid4()
    tenders.tenders[tender_id] = crear_licitacion(tender_id)
    return tender_id, tenders, drafts, answers, ia


@pytest.fixture
async def empresas(api: AsyncClient):
    """A es MEMBER de la Empresa 2 (activa); C es VIEWER de la 2; B es la dueña."""
    headers_a = _headers(api, SUB_A, "user_a@test.cl")
    headers_b = _headers(api, SUB_B, "user_b@test.cl")
    headers_c = _headers(api, SUB_C, "user_c@test.cl")
    await _crear_empresa(api, headers_a, "76.123.456-0", "Empresa Uno SpA")
    empresa_2 = await _crear_empresa(api, headers_b, "77.654.321-7", "Empresa Dos Ltda")
    await _unir(api, headers_b, headers_a, "user_a@test.cl", empresa_2)
    await _unir(api, headers_b, headers_c, "user_c@test.cl", empresa_2, role="viewer")
    await _cambiar(api, headers_a, empresa_2)
    await _cambiar(api, headers_c, empresa_2)
    return headers_a, headers_b, headers_c, UUID(empresa_2)


@pytest.mark.asyncio
async def test_un_miembro_inicia_la_factibilidad_de_la_empresa_activa(
    api: AsyncClient, entorno, empresas
):
    tender_id, _, drafts, answers, _ = entorno
    headers_a, headers_b, _, empresa_2 = empresas

    resp = await api.post(
        f"/tenders/{tender_id}/proposal/feasibility", headers=headers_a
    )

    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert cuerpo["status"] == "FEASIBILITY"
    assert cuerpo["requirements"][0]["capability_question_id"] == str(SEC.id)
    assert await drafts.get(empresa_2, tender_id) is not None
    assert await answers.get(empresa_2, SEC.id) is not None

    # La dueña ve el mismo borrador: es de la empresa, no de quien lo inició.
    leido = await api.get(f"/tenders/{tender_id}/proposal", headers=headers_b)
    assert leido.status_code == 200, leido.text
    assert leido.json()["id"] == cuerpo["id"]
    assert leido.json()["is_expired"] is False


@pytest.mark.asyncio
async def test_un_viewer_no_inicia_pero_si_lee(api: AsyncClient, entorno, empresas):
    tender_id, *_ = entorno
    headers_a, _, headers_c, _ = empresas

    resp = await api.post(
        f"/tenders/{tender_id}/proposal/feasibility", headers=headers_c
    )
    assert resp.status_code == 403

    await api.post(f"/tenders/{tender_id}/proposal/feasibility", headers=headers_a)
    assert (
        await api.get(f"/tenders/{tender_id}/proposal", headers=headers_c)
    ).status_code == 200


@pytest.mark.asyncio
async def test_sin_postulacion_iniciada_es_404(api: AsyncClient, entorno, empresas):
    tender_id, *_ = entorno
    headers_a, *_ = empresas

    resp = await api.get(f"/tenders/{tender_id}/proposal", headers=headers_a)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_una_licitacion_cerrada_es_409(api: AsyncClient, entorno, empresas):
    tender_id, tenders, *_ = entorno
    headers_a, *_ = empresas
    tenders.tenders[tender_id] = crear_licitacion(
        tender_id, status_code=TENDER_STATUSES["CLOSED"]
    )

    resp = await api.post(
        f"/tenders/{tender_id}/proposal/feasibility", headers=headers_a
    )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_si_la_ia_falla_es_502_y_no_queda_borrador(
    api: AsyncClient, entorno, empresas
):
    tender_id, _, drafts, _, ia = entorno
    headers_a, _, _, empresa_2 = empresas
    ia["servicio"] = FalloDeIA(FeasibilityResultDTO())

    resp = await api.post(
        f"/tenders/{tender_id}/proposal/feasibility", headers=headers_a
    )

    assert resp.status_code == 502
    assert await drafts.get(empresa_2, tender_id) is None
