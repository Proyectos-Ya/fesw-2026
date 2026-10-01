"""Borrador de postulación: máquina de estados y marcado de vacíos (HU-20, B1).

```text
FEASIBILITY ──"No" a exigencia excluyente──▶ PAUSED
PAUSED ──continuar con advertencia──▶ FEASIBILITY
PAUSED ──corregir la respuesta a "Sí"──▶ FEASIBILITY
PAUSED ──detener──▶ STOPPED ──reanudar──▶ FEASIBILITY
FEASIBILITY ──sin pendientes + generar──▶ READY
```
"""

from uuid import uuid4

import pytest

from app.domain.entities.proposal import (
    TECHNICAL_SECTIONS,
    DraftContent,
    DraftParagraph,
    DraftSection,
    ProposalDraft,
    Requirement,
    TechnicalDocument,
    TechnicalSection,
    render_placeholders,
)
from app.domain.errors.proposal_errors import InvalidProposalTransition

SEC_Q = uuid4()
VIALES_Q = uuid4()
PLAZO_Q = uuid4()


def _exigencias() -> list[Requirement]:
    return [
        Requirement(
            id="req-sec",
            text="El proveedor deberá contar con certificación SEC.",
            kind="certificacion",
            mandatory=True,
            origin="Descripción",
            capability_question_id=SEC_Q,
        ),
        Requirement(
            id="req-viales",
            text="Se valorará experiencia en obras viales.",
            kind="experiencia",
            mandatory=False,
            origin="Bases técnicas.pdf",
            capability_question_id=VIALES_Q,
        ),
        Requirement(
            id="req-region",
            text="Entrega en la Región de Valparaíso.",
            kind="disponibilidad",
            mandatory=True,
            origin="Ítem 1",
            status="cumple",
            catalog_item_id="perfil:region:valparaiso",
        ),
    ]


def _borrador(**kwargs) -> ProposalDraft:
    datos = dict(supplier_id=uuid4(), tender_id=uuid4())
    datos.update(kwargs)
    borrador = ProposalDraft(**datos)
    borrador.load_requirements(_exigencias())
    return borrador


def _contenido() -> DraftContent:
    parrafo = DraftParagraph(text="Oferta de instalación eléctrica.")
    return DraftContent(
        offer_name=DraftSection(paragraphs=[parrafo]),
        offer_description=DraftSection(paragraphs=[parrafo]),
        required_documents=DraftSection(paragraphs=[parrafo]),
    )


def _requisito(borrador: ProposalDraft, req_id: str) -> Requirement:
    return next(r for r in borrador.requirements if r.id == req_id)


class TestCargarExigencias:
    def test_arranca_en_factibilidad_con_preguntas_pendientes(self):
        borrador = _borrador()

        assert borrador.status == "FEASIBILITY"
        assert {r.id for r in borrador.pending_requirements()} == {
            "req-sec",
            "req-viales",
        }
        assert not borrador.can_generate()

    def test_una_negativa_ya_conocida_a_una_excluyente_pausa_de_entrada(self):
        """La empresa ya había dicho "No" en otra licitación: se pausa al cargar."""
        exigencias = _exigencias()
        exigencias[0] = exigencias[0].model_copy(update={"status": "no_cumple"})
        borrador = ProposalDraft(supplier_id=uuid4(), tender_id=uuid4())

        borrador.load_requirements(exigencias)

        assert borrador.status == "PAUSED"
        assert borrador.paused_requirement_id == "req-sec"


class TestResponder:
    def test_un_si_cumple_la_exigencia(self):
        borrador = _borrador()

        borrador.record_answer(SEC_Q, "afirmativa")

        assert _requisito(borrador, "req-sec").status == "cumple"
        assert borrador.status == "FEASIBILITY"

    def test_un_no_a_una_excluyente_pausa(self):
        borrador = _borrador()

        borrador.record_answer(SEC_Q, "negativa")

        assert _requisito(borrador, "req-sec").status == "no_cumple"
        assert borrador.status == "PAUSED"
        assert borrador.paused_requirement_id == "req-sec"

    def test_un_no_a_una_deseable_no_pausa(self):
        borrador = _borrador()

        borrador.record_answer(VIALES_Q, "negativa")

        assert _requisito(borrador, "req-viales").status == "no_cumple"
        assert borrador.status == "FEASIBILITY"

    def test_una_respuesta_neutra_queda_parcial_y_no_pausa(self):
        borrador = _borrador()

        borrador.record_answer(SEC_Q, "neutra")

        assert _requisito(borrador, "req-sec").status == "parcial"
        assert borrador.status == "FEASIBILITY"

    def test_una_pregunta_ajena_al_borrador_no_cambia_nada(self):
        borrador = _borrador()

        borrador.record_answer(uuid4(), "negativa")

        assert borrador.status == "FEASIBILITY"
        assert len(borrador.pending_requirements()) == 2

    @pytest.mark.parametrize("estado", ["STOPPED", "READY"])
    def test_detenido_o_listo_no_se_responde(self, estado):
        borrador = _borrador()
        borrador.status = estado

        with pytest.raises(InvalidProposalTransition):
            borrador.record_answer(SEC_Q, "afirmativa")


class TestActualizarRespuestaEnPausa:
    """En pausa se puede corregir la respuesta de la exigencia pausada.

    Sin esto, cambiar un "No" viejo (la empresa ya consiguió la certificación)
    obligaba a detener, reanudar y responder de nuevo.
    """

    def _pausado(self) -> ProposalDraft:
        borrador = _borrador()
        borrador.record_answer(SEC_Q, "negativa")
        assert borrador.status == "PAUSED"
        return borrador

    def test_un_si_resuelve_la_pausa(self):
        borrador = self._pausado()

        borrador.record_answer(SEC_Q, "afirmativa")

        assert borrador.status == "FEASIBILITY"
        assert borrador.paused_requirement_id is None
        assert _requisito(borrador, "req-sec").status == "cumple"
        assert borrador.discrepancy_decisions == []

    def test_una_neutra_tambien_resuelve_la_pausa(self):
        borrador = self._pausado()

        borrador.record_answer(SEC_Q, "neutra")

        assert borrador.status == "FEASIBILITY"
        assert _requisito(borrador, "req-sec").status == "parcial"

    def test_un_no_mantiene_la_pausa_en_la_misma_exigencia(self):
        borrador = self._pausado()

        borrador.record_answer(SEC_Q, "negativa")

        assert borrador.status == "PAUSED"
        assert borrador.paused_requirement_id == "req-sec"

    def test_no_se_puede_responder_otra_pregunta_en_pausa(self):
        """Primero se resuelve la discrepancia; el resto de la cola espera."""
        borrador = self._pausado()

        with pytest.raises(InvalidProposalTransition):
            borrador.record_answer(VIALES_Q, "afirmativa")

    def test_un_si_pausa_en_la_siguiente_excluyente_sin_decidir(self):
        exigencias = _exigencias()
        otra_q = uuid4()
        exigencias[0] = exigencias[0].model_copy(update={"status": "no_cumple"})
        exigencias.append(
            Requirement(
                id="req-mop",
                text="Deberá estar inscrito en el registro MOP.",
                kind="certificacion",
                mandatory=True,
                origin="Descripción",
                status="no_cumple",
                capability_question_id=otra_q,
            )
        )
        borrador = ProposalDraft(supplier_id=uuid4(), tender_id=uuid4())
        borrador.load_requirements(exigencias)

        borrador.record_answer(SEC_Q, "afirmativa")

        assert borrador.status == "PAUSED"
        assert borrador.paused_requirement_id == "req-mop"


class TestDecidir:
    def _pausado(self) -> ProposalDraft:
        borrador = _borrador()
        borrador.record_answer(SEC_Q, "negativa")
        return borrador

    def test_continuar_guarda_la_decision_y_la_advertencia(self):
        borrador = self._pausado()
        user_id = uuid4()

        borrador.decide("continue", user_id)

        assert borrador.status == "FEASIBILITY"
        assert borrador.paused_requirement_id is None
        [decision] = borrador.discrepancy_decisions
        assert decision.requirement_id == "req-sec"
        assert decision.capability_question_id == SEC_Q
        assert decision.action == "continue"
        assert decision.user_id == user_id
        [advertencia] = borrador.warnings
        assert advertencia.requirement_id == "req-sec"
        assert "certificación SEC" in advertencia.text

    def test_detener_guarda_la_decision_y_para(self):
        borrador = self._pausado()

        borrador.decide("stop", uuid4())

        assert borrador.status == "STOPPED"
        assert borrador.discrepancy_decisions[-1].action == "stop"
        assert borrador.warnings == []
        assert not borrador.can_generate()

    def test_solo_se_decide_en_pausa(self):
        with pytest.raises(InvalidProposalTransition):
            _borrador().decide("continue", uuid4())

    def test_continuar_pausa_de_nuevo_si_queda_otra_excluyente_sin_decidir(self):
        exigencias = _exigencias()
        otra_q = uuid4()
        exigencias.append(
            Requirement(
                id="req-mop",
                text="Deberá estar inscrito en el registro MOP.",
                kind="certificacion",
                mandatory=True,
                origin="Descripción",
                status="no_cumple",
                capability_question_id=otra_q,
            )
        )
        exigencias[0] = exigencias[0].model_copy(update={"status": "no_cumple"})
        borrador = ProposalDraft(supplier_id=uuid4(), tender_id=uuid4())
        borrador.load_requirements(exigencias)
        assert borrador.paused_requirement_id == "req-sec"

        borrador.decide("continue", uuid4())

        assert borrador.status == "PAUSED"
        assert borrador.paused_requirement_id == "req-mop"


class TestReanudar:
    def _detenido(self) -> ProposalDraft:
        borrador = _borrador()
        borrador.record_answer(SEC_Q, "negativa")
        borrador.decide("stop", uuid4())
        return borrador

    def test_vuelve_a_factibilidad_sin_pausar_de_nuevo(self):
        """Reanudar es para poder cambiar la respuesta, no para ver el modal otra vez."""
        borrador = self._detenido()

        borrador.resume()

        assert borrador.status == "FEASIBILITY"
        assert borrador.paused_requirement_id is None

    def test_tras_reanudar_se_puede_cambiar_la_respuesta(self):
        borrador = self._detenido()
        borrador.resume()

        borrador.record_answer(SEC_Q, "afirmativa")

        assert _requisito(borrador, "req-sec").status == "cumple"
        assert borrador.status == "FEASIBILITY"

    def test_sin_cambiar_la_respuesta_no_se_puede_redactar(self):
        borrador = self._detenido()
        borrador.resume()
        borrador.record_answer(VIALES_Q, "afirmativa")

        assert not borrador.can_generate()

    def test_un_nuevo_no_vuelve_a_pausar(self):
        borrador = self._detenido()
        borrador.resume()

        borrador.record_answer(SEC_Q, "negativa")

        assert borrador.status == "PAUSED"

    def test_solo_se_reanuda_lo_detenido(self):
        with pytest.raises(InvalidProposalTransition):
            _borrador().resume()


class TestAdvertenciasAlCorregir:
    def test_un_si_tras_continuar_quita_la_advertencia(self):
        borrador = _borrador()
        borrador.record_answer(SEC_Q, "negativa")
        borrador.decide("continue", uuid4())
        assert borrador.warnings

        borrador.record_answer(SEC_Q, "afirmativa")

        assert borrador.warnings == []


class TestPuedeRedactar:
    def test_con_todo_respondido_si(self):
        borrador = _borrador()
        borrador.record_answer(SEC_Q, "afirmativa")
        borrador.record_answer(VIALES_Q, "negativa")

        assert borrador.can_generate()

    def test_con_una_excluyente_en_no_y_continuar_si(self):
        borrador = _borrador()
        borrador.record_answer(SEC_Q, "negativa")
        borrador.decide("continue", uuid4())
        borrador.record_answer(VIALES_Q, "afirmativa")

        assert borrador.can_generate()

    def test_con_preguntas_pendientes_no(self):
        borrador = _borrador()
        borrador.record_answer(SEC_Q, "afirmativa")

        assert not borrador.can_generate()

    def test_marcar_listo_guarda_el_contenido(self):
        borrador = _borrador()
        borrador.record_answer(SEC_Q, "afirmativa")
        borrador.record_answer(VIALES_Q, "afirmativa")

        borrador.mark_ready(_contenido(), instructions=None)

        assert borrador.status == "READY"
        assert borrador.content == _contenido()

    def test_marcar_listo_sin_poder_redactar_falla(self):
        with pytest.raises(InvalidProposalTransition):
            _borrador().mark_ready(_contenido(), instructions=None)

    def test_regenerar_desde_listo_guarda_las_instrucciones(self):
        borrador = _borrador()
        borrador.record_answer(SEC_Q, "afirmativa")
        borrador.record_answer(VIALES_Q, "afirmativa")
        borrador.mark_ready(_contenido(), instructions=None)

        borrador.mark_ready(_contenido(), instructions="Más formal")

        assert borrador.status == "READY"
        assert borrador.last_instructions == "Más formal"


class TestVacios:
    def test_convierte_la_marca_en_texto_visible_y_la_registra(self):
        texto, vacios = render_placeholders(
            "Contamos con [[INSERTAR: número de trabajadores]] trabajadores."
        )

        assert texto == (
            "Contamos con (Por favor, inserte aquí el valor número de trabajadores) "
            "trabajadores."
        )
        assert vacios == ["número de trabajadores"]

    def test_varias_marcas_en_orden_y_sin_mayusculas_estrictas(self):
        texto, vacios = render_placeholders(
            "Plazo: [[insertar:plazo de entrega]]. Monto: [[ INSERTAR : monto ]]."
        )

        assert vacios == ["plazo de entrega", "monto"]
        assert "(Por favor, inserte aquí el valor plazo de entrega)" in texto
        assert "(Por favor, inserte aquí el valor monto)" in texto
        assert "[[" not in texto

    def test_sin_marcas_no_cambia_el_texto(self):
        assert render_placeholders("Texto completo.") == ("Texto completo.", [])

    def test_una_marca_vacia_pide_el_dato_sin_nombre(self):
        texto, vacios = render_placeholders("Dato: [[INSERTAR:]].")

        assert texto == "Dato: (Por favor, inserte aquí el valor faltante)."
        assert vacios == ["valor faltante"]

    def test_el_parrafo_aplica_el_marcado_al_construirse(self):
        parrafo = DraftParagraph.from_ai_text(
            "Experiencia de [[INSERTAR: años]] años.", sources=[]
        )

        assert (
            parrafo.text
            == "Experiencia de (Por favor, inserte aquí el valor años) años."
        )
        assert parrafo.placeholders == ["años"]


class TestPlantillaDelDocumentoTecnico:
    """Plantilla fija acordada con el equipo (plan 230, §2.6)."""

    def test_las_secciones_en_orden(self):
        assert [(s.key, s.title) for s in TECHNICAL_SECTIONS] == [
            ("antecedentes", "Antecedentes de la empresa"),
            ("comprension", "Comprensión del requerimiento"),
            ("metodologia", "Metodología"),
            ("plan_de_trabajo", "Plan de trabajo y plazos"),
            ("equipo", "Equipo de trabajo"),
            ("otros", "Otros requisitos de las bases"),
        ]

    def test_solo_otros_requisitos_es_opcional(self):
        opcionales = [s.key for s in TECHNICAL_SECTIONS if s.optional]
        assert opcionales == ["otros"]

    def test_el_documento_tecnico_es_una_lista_de_subsecciones(self):
        documento = TechnicalDocument(
            sections=[
                TechnicalSection(
                    key="metodologia",
                    title="Metodología",
                    paragraphs=[DraftParagraph(text="Clases presenciales.")],
                )
            ]
        )
        assert documento.sections[0].title == "Metodología"
