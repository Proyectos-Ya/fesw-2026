"""Redacción del borrador de postulación (HU-20, B4) con una IA falsa.

La IA redacta; el caso de uso aplica los guardrails: solo fuentes que existan
en el catálogo, un vacío donde se afirma algo de la empresa sin respaldo, la
lista de documentos detectados en la factibilidad y el documento técnico solo
si las bases lo exigen.
"""

from uuid import uuid4

import pytest

from app.application.services.proposal_ai_service import (
    DraftContentDTO,
    DraftParagraphDTO,
    DraftSectionDTO,
    FeasibilityResultDTO,
    ProposalAIServiceError,
    TechnicalDocumentDTO,
)
from app.application.use_cases.capabilities.answer_capability_question import (
    AnswerCapabilityQuestionUseCase,
)
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.application.use_cases.proposals.generate_proposal import (
    GenerateProposalUseCase,
)
from app.domain.entities.capability import CapabilityOption, CapabilityQuestion
from app.domain.entities.proposal import ProposalDraft, Requirement
from app.domain.entities.supplier import Supplier
from app.domain.errors.proposal_errors import (
    InvalidProposalTransition,
    ProposalDraftNotFound,
)
from app.domain.errors.tender_errors import TenderClosedForProposal
from app.shared.constants import TENDER_STATUSES
from tests.unit.application.fakes import (
    InMemoryCapabilityAnswerRepository,
    InMemoryCapabilityEvidenceRepository,
    InMemoryCapabilityQuestionRepository,
    InMemoryProposalDraftRepository,
    InMemorySupplierRepository,
    InMemoryTenderChatRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.test_score_tender_on_demand import crear_licitacion
from tests.unit.application.test_start_feasibility import FakeProposalAI

SEC_Q = uuid4()


def _parrafo(text: str, *sources: str, afirma: bool = False) -> DraftParagraphDTO:
    return DraftParagraphDTO(
        text=text, source_ids=list(sources), asserts_company_fact=afirma
    )


def _seccion(*parrafos: DraftParagraphDTO) -> DraftSectionDTO:
    return DraftSectionDTO(paragraphs=list(parrafos))


def _redaccion(**kwargs) -> DraftContentDTO:
    datos = dict(
        offer_name=_seccion(_parrafo("Capacitación PAC en Coyhaique")),
        offer_description=_seccion(
            _parrafo(
                "Operamos en la Región de Aysén.", "perfil:region:aysen", afirma=True
            )
        ),
    )
    datos.update(kwargs)
    return DraftContentDTO(**datos)


class Escenario:
    def __init__(self, redaccion: DraftContentDTO | None = None) -> None:
        self.suppliers = InMemorySupplierRepository()
        self.tenders = InMemoryTenderRepository()
        self.drafts = InMemoryProposalDraftRepository()
        self.questions = InMemoryCapabilityQuestionRepository()
        self.answers = InMemoryCapabilityAnswerRepository()
        self.evidences = InMemoryCapabilityEvidenceRepository()
        self.ai = FakeProposalAI(FeasibilityResultDTO(), redaccion or _redaccion())
        self.user_id = uuid4()
        self.tender_id = uuid4()
        self.tenders.tenders[self.tender_id] = crear_licitacion(self.tender_id)

    async def preparar(self, requiere_tecnico: bool = False, **extra) -> "Escenario":
        self.empresa = await self.suppliers.save(
            Supplier(
                user_id=self.user_id,
                rut="76086428-5",
                legal_name="Andes SpA",
                regions=["Aysén"],
            )
        )
        borrador = ProposalDraft(
            supplier_id=self.empresa.id,
            tender_id=self.tender_id,
            requires_technical_document=requiere_tecnico,
        )
        borrador.load_requirements(
            [
                Requirement(
                    id="req-1",
                    text="Ejecución presencial en Coyhaique",
                    kind="disponibilidad",
                    mandatory=True,
                    origin="Descripción",
                    status="cumple",
                    catalog_item_id="perfil:region:aysen",
                ),
                Requirement(
                    id="req-2",
                    text="Duración de 40 horas cronológicas",
                    kind="condicion",
                    mandatory=True,
                    origin="Descripción",
                    status="cumple",
                ),
                Requirement(
                    id="req-3",
                    text="Adjuntar cotización",
                    kind="documento",
                    mandatory=True,
                    origin="Descripción",
                    status="cumple",
                ),
                Requirement(
                    id="req-4",
                    text="Adjuntar formulario de solicitud de transferencias",
                    kind="documento",
                    mandatory=True,
                    origin="Descripción",
                    status="cumple",
                ),
                *extra.get("otras", []),
            ]
        )
        await self.drafts.save(borrador)
        return self

    async def borrador(self) -> ProposalDraft:
        leido = await self.drafts.get(self.empresa.id, self.tender_id)
        assert leido is not None
        return leido

    def caso(self) -> GenerateProposalUseCase:
        return GenerateProposalUseCase(
            supplier_repo=self.suppliers,
            tender_repo=self.tenders,
            draft_repo=self.drafts,
            catalog_use_case=BuildExperienceCatalogUseCase(
                self.suppliers, self.questions, self.answers, self.evidences
            ),
            chat_repo=InMemoryTenderChatRepository(),
            ai_service=self.ai,
        )

    async def redactar(self, instrucciones: str | None = None):
        return await self.caso().execute(
            user_id=self.user_id,
            supplier_id=self.empresa.id,
            tender_id=self.tender_id,
            instructions=instrucciones,
        )


def _textos(seccion) -> list[str]:
    return [p.text for p in seccion.paragraphs]


class TestRedactar:
    async def test_deja_el_borrador_listo_con_la_plantilla_de_compra_agil(self):
        e = await Escenario().preparar()

        borrador = await e.redactar()

        assert borrador.status == "READY"
        assert borrador.content is not None
        assert _textos(borrador.content.offer_name) == ["Capacitación PAC en Coyhaique"]
        assert borrador.content.technical_document is None
        assert (await e.borrador()).status == "READY"

    async def test_convierte_los_vacios_en_texto_visible(self):
        e = await Escenario(
            _redaccion(
                offer_description=_seccion(
                    _parrafo("Relator con [[INSERTAR: años de experiencia]] años.")
                )
            )
        ).preparar()

        borrador = await e.redactar()

        [parrafo] = borrador.content.offer_description.paragraphs  # type: ignore[union-attr]
        assert "(Por favor, inserte aquí el valor años de experiencia)" in parrafo.text
        assert parrafo.placeholders == ["años de experiencia"]

    async def test_la_ia_recibe_exigencias_advertencias_y_catalogo(self):
        e = await Escenario().preparar()

        await e.redactar(instrucciones="Más formal")

        [llamada] = e.ai.redacciones
        assert [r.id for r in llamada["requirements"]] == [
            "req-1",
            "req-2",
            "req-3",
            "req-4",
        ]
        assert "perfil:region:aysen" in {i.id for i in llamada["catalog"].items}
        assert llamada["include_technical_document"] is False
        assert llamada["instructions"] == "Más formal"


class TestFuentes:
    async def test_conserva_las_fuentes_del_catalogo_con_su_etiqueta(self):
        e = await Escenario().preparar()

        borrador = await e.redactar()

        [parrafo] = borrador.content.offer_description.paragraphs  # type: ignore[union-attr]
        [fuente] = parrafo.sources
        assert fuente.id == "perfil:region:aysen"
        assert "Aysén" in fuente.label
        assert parrafo.placeholders == []

    async def test_descarta_las_fuentes_inventadas(self):
        e = await Escenario(
            _redaccion(
                offer_description=_seccion(
                    _parrafo(
                        "Operamos en Aysén.",
                        "perfil:region:aysen",
                        "evidencia:inventada",
                        afirma=True,
                    )
                )
            )
        ).preparar()

        borrador = await e.redactar()

        [parrafo] = borrador.content.offer_description.paragraphs  # type: ignore[union-attr]
        assert [f.id for f in parrafo.sources] == ["perfil:region:aysen"]

    async def test_una_afirmacion_sin_fuente_valida_recibe_un_vacio(self):
        """Guardrail: nada de "10 años de experiencia en PAC" sin respaldo."""
        e = await Escenario(
            _redaccion(
                offer_description=_seccion(
                    _parrafo(
                        "Contamos con amplia experiencia en capacitaciones PAC.",
                        "capacidad:inventada",
                        afirma=True,
                    )
                )
            )
        ).preparar()

        borrador = await e.redactar()

        [parrafo] = borrador.content.offer_description.paragraphs  # type: ignore[union-attr]
        assert parrafo.sources == []
        assert parrafo.placeholders == ["respaldo de esta afirmación"]
        assert (
            "(Por favor, inserte aquí el valor respaldo de esta afirmación)"
            in parrafo.text
        )

    async def test_un_parrafo_que_no_afirma_nada_de_la_empresa_no_necesita_fuente(self):
        e = await Escenario(
            _redaccion(
                offer_description=_seccion(
                    _parrafo("La capacitación dura 40 horas cronológicas.")
                )
            )
        ).preparar()

        borrador = await e.redactar()

        [parrafo] = borrador.content.offer_description.paragraphs  # type: ignore[union-attr]
        assert parrafo.placeholders == []


class TestDetalleDeLaCotizacion:
    """Plan 292, §2.7 A: el formulario tiene un solo campo de 255 caracteres."""

    async def test_un_solo_parrafo_queda_igual(self):
        e = await Escenario().preparar()

        borrador = await e.redactar()

        assert _textos(borrador.content.offer_description) == [  # type: ignore[union-attr]
            "Operamos en la Región de Aysén."
        ]

    async def test_junta_varios_parrafos_en_uno_con_sus_fuentes_y_vacios(self):
        pregunta = CapabilityQuestion(
            question="¿Tiene experiencia en capacitaciones PAC?",
            target_field="experiencia:pac",
            category="general",
            kind="capacidad",
            options=[
                CapabilityOption(label="Sí", polarity="afirmativa"),
                CapabilityOption(label="No", polarity="negativa"),
            ],
        )
        capacidad = f"capacidad:{pregunta.id}"
        e = Escenario(
            _redaccion(
                offer_description=_seccion(
                    _parrafo(
                        "Capacitación PAC para [[INSERTAR: número de funcionarios]] "
                        "funcionarios.\n",
                        "perfil:region:aysen",
                    ),
                    _parrafo(
                        "Operamos en Aysén y dictamos cursos PAC.",
                        "perfil:region:aysen",
                        capacidad,
                        afirma=True,
                    ),
                    _parrafo("Plazo: [[INSERTAR: fecha de inicio]]."),
                )
            )
        )
        await e.questions.add(pregunta)
        await e.preparar()
        await AnswerCapabilityQuestionUseCase(
            e.suppliers, e.questions, e.answers
        ).execute(
            user_id=e.user_id,
            supplier_id=e.empresa.id,
            question_id=pregunta.id,
            answer="Sí",
        )

        borrador = await e.redactar()

        [parrafo] = borrador.content.offer_description.paragraphs  # type: ignore[union-attr]
        assert parrafo.text == (
            "Capacitación PAC para (Por favor, inserte aquí el valor número de "
            "funcionarios) funcionarios. Operamos en Aysén y dictamos cursos PAC. "
            "Plazo: (Por favor, inserte aquí el valor fecha de inicio)."
        )
        assert [f.id for f in parrafo.sources] == ["perfil:region:aysen", capacidad]
        assert parrafo.placeholders == ["número de funcionarios", "fecha de inicio"]

    async def test_no_trunca_un_texto_largo(self):
        largo = "Servicio de capacitación presencial. " * 10
        e = await Escenario(
            _redaccion(offer_description=_seccion(_parrafo(largo)))
        ).preparar()

        borrador = await e.redactar()

        [parrafo] = borrador.content.offer_description.paragraphs  # type: ignore[union-attr]
        assert parrafo.text == largo


class TestDocumentos:
    async def test_lista_los_documentos_de_la_factibilidad_y_suma_los_nuevos(self):
        e = await Escenario(
            _redaccion(
                required_documents=_seccion(
                    _parrafo("Adjuntar cotización"),
                    _parrafo("Declaración jurada simple"),
                )
            )
        ).preparar()

        borrador = await e.redactar()

        assert _textos(borrador.content.required_documents) == [  # type: ignore[union-attr]
            "Adjuntar cotización",
            "Adjuntar formulario de solicitud de transferencias",
            "Declaración jurada simple",
        ]

    async def test_no_lista_la_declaracion_jurada_de_habilidad(self):
        """Se acepta en una ventana de Mercado Público al enviar: no se adjunta."""
        e = await Escenario(
            _redaccion(
                required_documents=_seccion(
                    _parrafo("Declaración Jurada de Habilidad firmada"),
                    _parrafo("Declaración jurada simple"),
                )
            )
        ).preparar()

        borrador = await e.redactar()

        assert "Declaración Jurada de Habilidad firmada" not in _textos(
            borrador.content.required_documents  # type: ignore[union-attr]
        )
        assert "Declaración jurada simple" in _textos(
            borrador.content.required_documents  # type: ignore[union-attr]
        )


def _tecnico(**secciones: DraftSectionDTO) -> TechnicalDocumentDTO:
    return TechnicalDocumentDTO(**secciones)


def _secciones(borrador) -> dict:
    tecnico = borrador.content.technical_document
    assert tecnico is not None
    return {s.key: s for s in tecnico.sections}


class TestDocumentoTecnico:
    """Plantilla fija: cinco secciones siempre y "Otros requisitos" si hay algo."""

    async def test_se_arma_con_la_plantilla_si_las_bases_lo_exigen(self):
        e = await Escenario(
            _redaccion(
                technical_document=_tecnico(
                    metodologia=_seccion(
                        _parrafo("Clases presenciales con casos prácticos.")
                    )
                )
            )
        ).preparar(requiere_tecnico=True)

        borrador = await e.redactar()

        tecnico = borrador.content.technical_document  # type: ignore[union-attr]
        assert tecnico is not None
        assert [s.key for s in tecnico.sections] == [
            "antecedentes",
            "comprension",
            "metodologia",
            "plan_de_trabajo",
            "equipo",
        ]
        assert _secciones(borrador)["metodologia"].paragraphs[0].text == (
            "Clases presenciales con casos prácticos."
        )
        assert e.ai.redacciones[0]["include_technical_document"] is True

    async def test_una_seccion_sin_contenido_queda_como_vacio(self):
        e = await Escenario().preparar(requiere_tecnico=True)

        borrador = await e.redactar()

        equipo = _secciones(borrador)["equipo"]
        assert equipo.title == "Equipo de trabajo"
        assert equipo.paragraphs[0].placeholders == ["nombre y experiencia del equipo"]
        assert _secciones(borrador)["metodologia"].paragraphs[0].placeholders == [
            "metodología"
        ]

    async def test_otros_requisitos_solo_si_hay_contenido(self):
        sin = await Escenario().preparar(requiere_tecnico=True)
        con = await Escenario(
            _redaccion(
                technical_document=_tecnico(
                    otros=_seccion(_parrafo("Plan de mitigación de riesgos: ..."))
                )
            )
        ).preparar(requiere_tecnico=True)

        assert "otros" not in _secciones(await sin.redactar())
        otros = _secciones(await con.redactar())["otros"]
        assert otros.title == "Otros requisitos de las bases"

    async def test_las_fuentes_del_tecnico_tambien_se_validan(self):
        e = await Escenario(
            _redaccion(
                technical_document=_tecnico(
                    antecedentes=_seccion(
                        _parrafo(
                            "Operamos en Aysén y tenemos 20 años de experiencia.",
                            "perfil:region:aysen",
                            "capacidad:inventada",
                            afirma=True,
                        )
                    )
                )
            )
        ).preparar(requiere_tecnico=True)

        borrador = await e.redactar()

        [parrafo] = _secciones(borrador)["antecedentes"].paragraphs
        assert [f.id for f in parrafo.sources] == ["perfil:region:aysen"]

    async def test_no_se_incluye_si_no_lo_exigen_aunque_la_ia_lo_escriba(self):
        e = await Escenario(
            _redaccion(
                technical_document=_tecnico(metodologia=_seccion(_parrafo("...")))
            )
        ).preparar(requiere_tecnico=False)

        borrador = await e.redactar()

        assert borrador.content.technical_document is None  # type: ignore[union-attr]


class TestPausaDeLaRedaccion:
    """CA7: no se redacta con preguntas pendientes, en pausa ni detenido."""

    async def test_con_preguntas_pendientes_no_se_redacta(self):
        pendiente = Requirement(
            id="req-5",
            text="Deberá contar con SEC.",
            kind="certificacion",
            mandatory=True,
            origin="Descripción",
            capability_question_id=SEC_Q,
        )
        e = await Escenario().preparar(otras=[pendiente])

        with pytest.raises(InvalidProposalTransition):
            await e.redactar()
        assert e.ai.redacciones == []
        assert (await e.borrador()).status == "FEASIBILITY"

    async def test_en_pausa_no_se_redacta(self):
        e = await Escenario().preparar(
            otras=[
                Requirement(
                    id="req-5",
                    text="Deberá contar con SEC.",
                    kind="certificacion",
                    mandatory=True,
                    origin="Descripción",
                    status="no_cumple",
                    capability_question_id=SEC_Q,
                )
            ]
        )
        assert (await e.borrador()).status == "PAUSED"

        with pytest.raises(InvalidProposalTransition):
            await e.redactar()

    async def test_con_la_licitacion_cerrada_no_se_redacta(self):
        e = await Escenario().preparar()
        e.tenders.tenders[e.tender_id] = crear_licitacion(
            e.tender_id, status_code=TENDER_STATUSES["CLOSED"]
        )

        with pytest.raises(TenderClosedForProposal):
            await e.redactar()

    async def test_sin_borrador(self):
        e = await Escenario().preparar()
        e.drafts.filas.clear()

        with pytest.raises(ProposalDraftNotFound):
            await e.redactar()

    async def test_si_la_ia_falla_el_borrador_no_cambia(self):
        e = await Escenario().preparar()

        async def fallar(**_):
            raise ProposalAIServiceError("Gemini no responde")

        e.ai.generate_draft = fallar  # type: ignore[method-assign]

        with pytest.raises(ProposalAIServiceError):
            await e.redactar()
        assert (await e.borrador()).status == "FEASIBILITY"


class TestDocumentoTecnicoAPedido:
    """La empresa lo pide aunque no se detectó en las bases: se redacta con la plantilla."""

    async def test_redacta_incluyendo_el_documento_tecnico(self):
        e = await Escenario().preparar(requiere_tecnico=False)
        await e.redactar()

        borrador = await e.caso().execute(
            user_id=e.user_id,
            supplier_id=e.empresa.id,
            tender_id=e.tender_id,
            request_technical_document=True,
        )

        assert borrador.requires_technical_document is True
        assert borrador.content.technical_document is not None  # type: ignore[union-attr]
        assert e.ai.redacciones[-1]["include_technical_document"] is True
        assert "no se detectó" in (borrador.technical_document_reason or "")

    async def test_sin_poder_redactar_no_se_pide(self):
        pendiente = Requirement(
            id="req-5",
            text="Deberá contar con SEC.",
            kind="certificacion",
            mandatory=True,
            origin="Descripción",
            capability_question_id=SEC_Q,
        )
        e = await Escenario().preparar(otras=[pendiente])

        with pytest.raises(InvalidProposalTransition):
            await e.caso().execute(
                user_id=e.user_id,
                supplier_id=e.empresa.id,
                tender_id=e.tender_id,
                request_technical_document=True,
            )
        assert (await e.borrador()).requires_technical_document is False
