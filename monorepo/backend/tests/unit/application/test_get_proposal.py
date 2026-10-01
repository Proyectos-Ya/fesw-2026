"""Lectura del borrador con su vencimiento calculado al leer (HU-20, B2)."""

from uuid import uuid4

import pytest

from app.application.use_cases.capabilities.answer_capability_question import (
    AnswerCapabilityQuestionUseCase,
)
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.application.use_cases.proposals.get_proposal import GetProposalUseCase
from app.domain.entities.capability import CapabilityOption, CapabilityQuestion
from app.domain.entities.proposal import ProposalDraft, Requirement
from app.domain.entities.supplier import Supplier
from app.domain.errors.proposal_errors import ProposalDraftNotFound
from app.domain.errors.tender_errors import TenderNotFound
from app.shared.constants import TENDER_STATUSES
from tests.unit.application.fakes import (
    InMemoryCapabilityAnswerRepository,
    InMemoryCapabilityEvidenceRepository,
    InMemoryCapabilityQuestionRepository,
    InMemoryProposalDraftRepository,
    InMemorySupplierRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.test_score_tender_on_demand import crear_licitacion

SI_NO = [
    CapabilityOption(label="Sí", polarity="afirmativa"),
    CapabilityOption(label="No", polarity="negativa"),
]
SEC = CapabilityQuestion(
    question="¿Cuenta con SEC?",
    target_field="sec",
    category="general",
    kind="certificacion",
    options=SI_NO,
)
OTRA = CapabilityQuestion(
    question="¿Tiene ISO?", target_field="iso", category="general", options=SI_NO
)
QUESTIONS = InMemoryCapabilityQuestionRepository([SEC, OTRA])
ANSWERS = InMemoryCapabilityAnswerRepository()


async def _escenario(status_code: str = TENDER_STATUSES["PUBLISHED"]):
    suppliers = InMemorySupplierRepository()
    tenders = InMemoryTenderRepository()
    drafts = InMemoryProposalDraftRepository()
    user_id, tender_id = uuid4(), uuid4()
    empresa = await suppliers.save(
        Supplier(user_id=user_id, rut="76086428-5", legal_name="Andes SpA")
    )
    tenders.tenders[tender_id] = crear_licitacion(tender_id, status_code=status_code)
    caso = GetProposalUseCase(
        suppliers,
        tenders,
        drafts,
        QUESTIONS,
        BuildExperienceCatalogUseCase(
            suppliers, QUESTIONS, ANSWERS, InMemoryCapabilityEvidenceRepository()
        ),
    )
    return caso, drafts, user_id, empresa, tender_id


async def test_devuelve_el_borrador_de_la_empresa_activa():
    caso, drafts, user_id, empresa, tender_id = await _escenario()
    borrador = await drafts.save(
        ProposalDraft(supplier_id=empresa.id, tender_id=tender_id)
    )

    vista = await caso.execute(user_id, empresa.id, tender_id)

    assert vista.id == borrador.id
    assert vista.is_expired is False


async def test_un_borrador_de_una_licitacion_cerrada_se_marca_vencido():
    caso, drafts, user_id, empresa, tender_id = await _escenario(
        TENDER_STATUSES["CLOSED"]
    )
    await drafts.save(ProposalDraft(supplier_id=empresa.id, tender_id=tender_id))

    vista = await caso.execute(user_id, empresa.id, tender_id)

    assert vista.is_expired is True
    assert vista.status == "FEASIBILITY"


async def test_sin_borrador_es_no_encontrado():
    caso, _, user_id, empresa, tender_id = await _escenario()

    with pytest.raises(ProposalDraftNotFound):
        await caso.execute(user_id, empresa.id, tender_id)


async def test_licitacion_inexistente():
    caso, _, user_id, empresa, _ = await _escenario()

    with pytest.raises(TenderNotFound):
        await caso.execute(user_id, empresa.id, uuid4())


async def test_trae_las_preguntas_y_el_origen_de_lo_que_cubre_cada_exigencia():
    """La pantalla muestra cada pregunta con sus opciones y explica una pausa."""
    caso, drafts, user_id, empresa, tender_id = await _escenario()
    await AnswerCapabilityQuestionUseCase(
        caso.supplier_repo, QUESTIONS, ANSWERS
    ).execute(user_id=user_id, supplier_id=empresa.id, question_id=SEC.id, answer="No")
    borrador = ProposalDraft(supplier_id=empresa.id, tender_id=tender_id)
    borrador.load_requirements(
        [
            Requirement(
                id="req-1",
                text="Deberá contar con SEC.",
                kind="certificacion",
                mandatory=True,
                origin="Descripción",
                status="no_cumple",
                catalog_item_id=f"capacidad:{SEC.id}",
                capability_question_id=SEC.id,
            )
        ]
    )
    await drafts.save(borrador)

    vista = await caso.execute(user_id, empresa.id, tender_id)

    assert [q.id for q in vista.questions] == [SEC.id]
    [item] = vista.catalog_items
    assert item.id == f"capacidad:{SEC.id}"
    assert item.polarity == "negativa"
    assert item.answered_at is not None
