"""Respuestas del banco corregidas fuera de la postulación (HU-20).

La lectura del borrador avisa qué exigencias usan una respuesta que cambió, y
`SyncProposalAnswersUseCase` la aplica: vuelve a redactar si puede, o pausa ante
un "No" excluyente, igual que la factibilidad.
"""

import pytest

from app.application.use_cases.capabilities.answer_capability_question import (
    AnswerCapabilityQuestionUseCase,
)
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.application.use_cases.proposals.get_proposal import GetProposalUseCase
from app.application.use_cases.proposals.sync_proposal_answers import (
    SyncProposalAnswersUseCase,
)
from app.domain.entities.capability import CapabilityOption, CapabilityQuestion
from app.domain.entities.proposal import Requirement
from app.domain.errors.tender_errors import TenderClosedForProposal
from app.shared.constants import TENDER_STATUSES
from tests.unit.application.test_generate_proposal import (
    Escenario,
    _parrafo,
    _redaccion,
    _seccion,
)
from tests.unit.application.test_score_tender_on_demand import crear_licitacion

SEC = CapabilityQuestion(
    question="¿Cuenta con certificación SEC?",
    target_field="sec",
    category="general",
    kind="certificacion",
    options=[
        CapabilityOption(label="Sí", polarity="afirmativa"),
        CapabilityOption(label="No", polarity="negativa"),
    ],
)


def _exigencia_sec() -> Requirement:
    return Requirement(
        id="req-sec",
        text="Deberá contar con certificación SEC.",
        kind="certificacion",
        mandatory=True,
        origin="Descripción",
        status="cumple",
        catalog_item_id=f"capacidad:{SEC.id}",
        capability_question_id=SEC.id,
    )


async def _responder(e: Escenario, respuesta: str) -> None:
    await AnswerCapabilityQuestionUseCase(e.suppliers, e.questions, e.answers).execute(
        user_id=e.user_id,
        supplier_id=e.empresa.id,
        question_id=SEC.id,
        answer=respuesta,
    )


async def _redactado() -> Escenario:
    """Borrador redactado con SEC respondida "Sí" antes de redactar."""
    e = Escenario()
    await e.questions.add(SEC)
    await e.preparar(otras=[_exigencia_sec()])
    await _responder(e, "Sí")
    await e.redactar()
    return e


def _lectura(e: Escenario) -> GetProposalUseCase:
    return GetProposalUseCase(
        e.suppliers,
        e.tenders,
        e.drafts,
        e.questions,
        BuildExperienceCatalogUseCase(e.suppliers, e.questions, e.answers, e.evidences),
    )


async def _leer(e: Escenario):
    return await _lectura(e).execute(e.user_id, e.empresa.id, e.tender_id)


async def _sincronizar(e: Escenario):
    return await SyncProposalAnswersUseCase(
        e.suppliers,
        e.tenders,
        e.drafts,
        BuildExperienceCatalogUseCase(e.suppliers, e.questions, e.answers, e.evidences),
        e.caso(),
    ).execute(user_id=e.user_id, supplier_id=e.empresa.id, tender_id=e.tender_id)


class TestAvisoAlLeer:
    async def test_sin_cambios_no_avisa(self):
        e = await _redactado()

        vista = await _leer(e)

        assert vista.changed_requirement_ids == []

    async def test_avisa_la_respuesta_corregida_despues_de_redactar(self):
        e = await _redactado()
        await _responder(e, "No")

        vista = await _leer(e)

        assert vista.changed_requirement_ids == ["req-sec"]
        # Trae la respuesta vigente para mostrar "ahora es No".
        [item] = [i for i in vista.catalog_items if i.id == f"capacidad:{SEC.id}"]
        assert item.detail == "No"

    async def test_leer_no_modifica_el_borrador(self):
        e = await _redactado()
        await _responder(e, "No")
        antes = await e.borrador()

        await _leer(e)

        assert await e.borrador() == antes


class TestAplicarLasRespuestas:
    async def test_un_si_corregido_vuelve_a_redactar_con_las_mismas_instrucciones(self):
        e = Escenario()
        await e.questions.add(SEC)
        await e.preparar(otras=[_exigencia_sec()])
        await _responder(e, "Sí")
        await e.redactar("Tono formal")
        await _responder(e, "Sí")  # se vuelve a confirmar tras redactar
        e.ai.borrador = _redaccion(offer_name=_seccion(_parrafo("Nombre nuevo")))

        borrador = await _sincronizar(e)

        assert borrador.status == "READY"
        assert borrador.content.offer_name.paragraphs[0].text == "Nombre nuevo"  # type: ignore[union-attr]
        assert e.ai.redacciones[-1]["instructions"] == "Tono formal"
        assert (await _leer(e)).changed_requirement_ids == []

    async def test_un_no_excluyente_pausa_sin_llamar_a_la_ia(self):
        e = await _redactado()
        await _responder(e, "No")

        borrador = await _sincronizar(e)

        assert borrador.status == "PAUSED"
        assert borrador.paused_requirement_id == "req-sec"
        assert len(e.ai.redacciones) == 1
        assert (await e.borrador()).status == "PAUSED"

    async def test_sin_cambios_no_hace_nada(self):
        e = await _redactado()
        antes = await e.borrador()

        borrador = await _sincronizar(e)

        assert borrador == antes
        assert len(e.ai.redacciones) == 1

    async def test_con_la_licitacion_cerrada_no_se_aplica(self):
        e = await _redactado()
        await _responder(e, "No")
        e.tenders.tenders[e.tender_id] = crear_licitacion(
            e.tender_id, status_code=TENDER_STATUSES["CLOSED"]
        )

        with pytest.raises(TenderClosedForProposal):
            await _sincronizar(e)
