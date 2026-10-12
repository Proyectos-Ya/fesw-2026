"""Responder, decidir y reanudar dentro de la postulación (HU-20, B3).

La máquina de estados vive en el dominio (B1). Acá se prueba el cableado: la
respuesta queda en el banco de la empresa **y** mueve el borrador; nada se
guarda si la acción no corresponde al estado; y una licitación cerrada ya no
acepta cambios.
"""

from uuid import uuid4

import pytest

from app.application.use_cases.capabilities.answer_capability_question import (
    AnswerCapabilityQuestionUseCase,
)
from app.application.use_cases.proposals.answer_proposal_question import (
    AnswerProposalQuestionUseCase,
)
from app.application.use_cases.proposals.decide_discrepancy import (
    DecideDiscrepancyUseCase,
)
from app.application.use_cases.proposals.resume_proposal import ResumeProposalUseCase
from app.domain.entities.capability import CapabilityOption, CapabilityQuestion
from app.domain.entities.proposal import ProposalDraft, Requirement
from app.domain.entities.supplier import Supplier
from app.domain.errors.capability_errors import InvalidCapabilityAnswer
from app.domain.errors.proposal_errors import (
    InvalidProposalTransition,
    ProposalDraftNotFound,
    QuestionNotInProposal,
)
from app.domain.errors.tender_errors import TenderClosedForProposal
from app.shared.constants import TENDER_STATUSES
from tests.unit.application.fakes import (
    InMemoryCapabilityAnswerRepository,
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
    question="¿Cuenta con certificación SEC?",
    target_field="sec",
    category="servicios",
    kind="certificacion",
    options=SI_NO,
)
VIALES = CapabilityQuestion(
    question="¿Tiene experiencia en obras viales?",
    target_field="experiencia:obras-viales",
    category="servicios",
    kind="experiencia_proyecto",
    work_type="obras viales",
    options=SI_NO,
)
AJENA = CapabilityQuestion(
    question="¿Tiene ISO 27001?",
    target_field="iso_27001",
    category="servicios",
    kind="certificacion",
    options=SI_NO,
)


class Escenario:
    def __init__(self) -> None:
        self.suppliers = InMemorySupplierRepository()
        self.questions = InMemoryCapabilityQuestionRepository([SEC, VIALES, AJENA])
        self.answers = InMemoryCapabilityAnswerRepository()
        self.tenders = InMemoryTenderRepository()
        self.drafts = InMemoryProposalDraftRepository()
        self.user_id = uuid4()
        self.tender_id = uuid4()
        self.tenders.tenders[self.tender_id] = crear_licitacion(self.tender_id)

    async def preparar(self) -> "Escenario":
        self.empresa = await self.suppliers.save(
            Supplier(user_id=self.user_id, rut="76086428-5", legal_name="Andes SpA")
        )
        borrador = ProposalDraft(supplier_id=self.empresa.id, tender_id=self.tender_id)
        borrador.load_requirements(
            [
                Requirement(
                    id="req-sec",
                    text="Deberá contar con certificación SEC.",
                    kind="certificacion",
                    mandatory=True,
                    origin="Descripción",
                    capability_question_id=SEC.id,
                ),
                Requirement(
                    id="req-viales",
                    text="Se valorará experiencia en obras viales.",
                    kind="experiencia",
                    mandatory=False,
                    origin="Descripción",
                    capability_question_id=VIALES.id,
                ),
            ]
        )
        await self.drafts.save(borrador)
        return self

    async def borrador(self) -> ProposalDraft:
        leido = await self.drafts.get(self.empresa.id, self.tender_id)
        assert leido is not None
        return leido

    def cerrar(self) -> None:
        self.tenders.tenders[self.tender_id] = crear_licitacion(
            self.tender_id, status_code=TENDER_STATUSES["CLOSED"]
        )

    def _deps(self) -> dict:
        return dict(
            supplier_repo=self.suppliers,
            tender_repo=self.tenders,
            draft_repo=self.drafts,
        )

    async def responder(self, pregunta: CapabilityQuestion, answer: str, **kw):
        return await AnswerProposalQuestionUseCase(
            **self._deps(),
            question_repo=self.questions,
            answer_use_case=AnswerCapabilityQuestionUseCase(
                self.suppliers, self.questions, self.answers
            ),
        ).execute(
            user_id=self.user_id,
            supplier_id=self.empresa.id,
            tender_id=self.tender_id,
            question_id=pregunta.id,
            answer=answer,
            **kw,
        )

    async def decidir(self, action: str, requirement_id: str = "req-sec"):
        return await DecideDiscrepancyUseCase(**self._deps()).execute(
            user_id=self.user_id,
            supplier_id=self.empresa.id,
            tender_id=self.tender_id,
            requirement_id=requirement_id,
            action=action,
        )

    async def reanudar(self):
        return await ResumeProposalUseCase(**self._deps()).execute(
            user_id=self.user_id, supplier_id=self.empresa.id, tender_id=self.tender_id
        )


class TestResponder:
    async def test_guarda_en_el_banco_con_la_licitacion_y_mueve_el_borrador(self):
        e = await Escenario().preparar()

        borrador = await e.responder(SEC, "Sí")

        assert borrador.requirements[0].status == "cumple"
        assert (await e.borrador()).requirements[0].status == "cumple"
        respuesta = await e.answers.get(e.empresa.id, SEC.id)
        assert respuesta is not None
        assert respuesta.answer == "Sí"
        assert respuesta.tender_id == e.tender_id
        assert respuesta.answered_by_user_id == e.user_id

    async def test_un_no_a_una_excluyente_pausa_el_borrador(self):
        e = await Escenario().preparar()

        borrador = await e.responder(SEC, "No")

        assert borrador.status == "PAUSED"
        assert borrador.paused_requirement_id == "req-sec"
        assert (await e.borrador()).status == "PAUSED"

    async def test_en_pausa_otra_pregunta_no_se_guarda_en_ningun_lado(self):
        """Se valida contra el borrador antes de escribir en el banco."""
        e = await Escenario().preparar()
        await e.responder(SEC, "No")

        with pytest.raises(InvalidProposalTransition):
            await e.responder(VIALES, "Sí")

        assert await e.answers.get(e.empresa.id, VIALES.id) is None
        assert (await e.borrador()).requirements[1].status == "desconocido"

    async def test_en_pausa_se_actualiza_la_respuesta_pausada(self):
        e = await Escenario().preparar()
        await e.responder(SEC, "No")

        borrador = await e.responder(SEC, "Sí")

        assert borrador.status == "FEASIBILITY"
        respuesta = await e.answers.get(e.empresa.id, SEC.id)
        assert respuesta is not None and respuesta.answer == "Sí"

    async def test_una_pregunta_que_no_es_de_la_postulacion(self):
        e = await Escenario().preparar()

        with pytest.raises(QuestionNotInProposal):
            await e.responder(AJENA, "Sí")
        assert await e.answers.get(e.empresa.id, AJENA.id) is None

    async def test_una_respuesta_que_no_es_opcion(self):
        e = await Escenario().preparar()

        with pytest.raises(InvalidCapabilityAnswer):
            await e.responder(SEC, "Tal vez")
        assert await e.answers.get(e.empresa.id, SEC.id) is None

    async def test_con_la_licitacion_cerrada_no_se_responde(self):
        e = await Escenario().preparar()
        e.cerrar()

        with pytest.raises(TenderClosedForProposal):
            await e.responder(SEC, "Sí")
        assert await e.answers.get(e.empresa.id, SEC.id) is None

    async def test_sin_borrador(self):
        e = await Escenario().preparar()
        e.drafts.filas.clear()

        with pytest.raises(ProposalDraftNotFound):
            await e.responder(SEC, "Sí")


class TestDecidir:
    async def test_continuar_guarda_la_decision_y_la_advertencia(self):
        e = await Escenario().preparar()
        await e.responder(SEC, "No")

        borrador = await e.decidir("continue")

        assert borrador.status == "FEASIBILITY"
        [decision] = borrador.discrepancy_decisions
        assert decision.user_id == e.user_id
        assert (await e.borrador()).warnings

    async def test_detener_deja_el_borrador_detenido(self):
        e = await Escenario().preparar()
        await e.responder(SEC, "No")

        borrador = await e.decidir("stop")

        assert borrador.status == "STOPPED"
        assert (await e.borrador()).status == "STOPPED"

    async def test_decidir_sobre_otra_exigencia_que_la_pausada_es_conflicto(self):
        """El usuario decidió mirando una pausa que ya cambió: no se aplica."""
        e = await Escenario().preparar()
        await e.responder(SEC, "No")

        with pytest.raises(InvalidProposalTransition):
            await e.decidir("continue", requirement_id="req-viales")
        assert (await e.borrador()).status == "PAUSED"

    async def test_sin_pausa_no_hay_nada_que_decidir(self):
        e = await Escenario().preparar()

        with pytest.raises(InvalidProposalTransition):
            await e.decidir("continue")

    async def test_con_la_licitacion_cerrada_no_se_decide(self):
        e = await Escenario().preparar()
        await e.responder(SEC, "No")
        e.cerrar()

        with pytest.raises(TenderClosedForProposal):
            await e.decidir("stop")


class TestReanudar:
    async def test_vuelve_a_factibilidad(self):
        e = await Escenario().preparar()
        await e.responder(SEC, "No")
        await e.decidir("stop")

        borrador = await e.reanudar()

        assert borrador.status == "FEASIBILITY"
        assert (await e.borrador()).status == "FEASIBILITY"

    async def test_solo_se_reanuda_lo_detenido(self):
        e = await Escenario().preparar()

        with pytest.raises(InvalidProposalTransition):
            await e.reanudar()

    async def test_con_la_licitacion_cerrada_no_se_reanuda(self):
        e = await Escenario().preparar()
        await e.responder(SEC, "No")
        await e.decidir("stop")
        e.cerrar()

        with pytest.raises(TenderClosedForProposal):
            await e.reanudar()
