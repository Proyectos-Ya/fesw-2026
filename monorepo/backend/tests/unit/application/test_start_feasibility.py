"""Factibilidad de una postulación (HU-20, B2) con una IA falsa.

La IA decide qué cubre cada exigencia; el caso de uso lo aterriza: valida los ids
del catálogo, reutiliza o registra preguntas del banco, crea las respuestas
pendientes de la empresa y deja el borrador listo (o pausado).
"""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.application.services.proposal_ai_service import (
    DraftContentDTO,
    DraftSectionDTO,
    FeasibilityRequirementDTO,
    FeasibilityResultDTO,
    IProposalAIService,
    NewQuestionDTO,
)
from app.application.services.tender_assistant_ai_service import DocumentContextDTO
from app.application.use_cases.capabilities.answer_capability_question import (
    AnswerCapabilityQuestionUseCase,
)
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.application.use_cases.proposals.start_feasibility import (
    StartFeasibilityUseCase,
)
from app.domain.entities.capability import (
    CapabilityOption,
    CapabilityQuestion,
    ExperienceCatalog,
)
from app.domain.entities.proposal import DraftContent, DraftSection
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.entities.tender_chat import TenderChatDocument
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_errors import TenderClosedForProposal, TenderNotFound
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

CATEGORIA = "obras-de-construccion-e-infraestructura"
SI_NO = [
    CapabilityOption(label="No", polarity="negativa"),
    CapabilityOption(label="Sí", polarity="afirmativa"),
]


def _pregunta(target_field: str, **kwargs) -> CapabilityQuestion:
    datos = dict(
        question=f"¿Pregunta sobre {target_field}?",
        target_field=target_field,
        category=CATEGORIA,
        options=SI_NO,
    )
    datos.update(kwargs)
    return CapabilityQuestion(**datos)


SEC = _pregunta("sec_clase_a", kind="certificacion")
MOP = _pregunta("registro_mop", kind="certificacion")
BIM = _pregunta("bim")
OTRO_RUBRO = _pregunta("iso_27001", category="tecnologia")


class FakeProposalAI(IProposalAIService):
    def __init__(
        self,
        resultado: FeasibilityResultDTO,
        borrador: DraftContentDTO | None = None,
    ) -> None:
        self.resultado = resultado
        self.borrador = borrador or DraftContentDTO(
            offer_name=DraftSectionDTO(), offer_description=DraftSectionDTO()
        )
        self.llamadas: list[dict] = []
        self.redacciones: list[dict] = []

    async def generate_draft(self, **kwargs) -> DraftContentDTO:
        self.redacciones.append(kwargs)
        return self.borrador

    async def analyze_feasibility(
        self,
        tender: Tender,
        catalog: ExperienceCatalog,
        bank_questions: list[CapabilityQuestion],
        documents: list[DocumentContextDTO],
    ) -> FeasibilityResultDTO:
        self.llamadas.append(
            dict(
                tender=tender,
                catalog=catalog,
                bank_questions=bank_questions,
                documents=documents,
            )
        )
        return self.resultado


def _exigencia(**kwargs) -> FeasibilityRequirementDTO:
    datos = dict(
        text="Exigencia", kind="certificacion", mandatory=True, origin="Descripción"
    )
    datos.update(kwargs)
    return FeasibilityRequirementDTO(**datos)


class Escenario:
    def __init__(self, *exigencias: FeasibilityRequirementDTO, **resultado) -> None:
        self.suppliers = InMemorySupplierRepository()
        self.questions = InMemoryCapabilityQuestionRepository(
            [SEC, MOP, BIM, OTRO_RUBRO]
        )
        self.answers = InMemoryCapabilityAnswerRepository()
        self.evidences = InMemoryCapabilityEvidenceRepository()
        self.tenders = InMemoryTenderRepository()
        self.drafts = InMemoryProposalDraftRepository()
        self.chat = InMemoryTenderChatRepository()
        self.ai = FakeProposalAI(
            FeasibilityResultDTO(requirements=list(exigencias), **resultado)
        )
        self.user_id = uuid4()
        self.tender_id = uuid4()
        self.tenders.tenders[self.tender_id] = crear_licitacion(self.tender_id)

    async def preparar(self) -> "Escenario":
        self.empresa = await self.suppliers.save(
            Supplier(
                user_id=self.user_id,
                rut="76086428-5",
                legal_name="Constructora Andes SpA",
                trade_name="Andes Obras",
                sectors=["Obras de Construcción e Infraestructura"],
                regions=["Valparaíso"],
            )
        )
        return self

    async def responde(self, pregunta: CapabilityQuestion, answer: str) -> None:
        await AnswerCapabilityQuestionUseCase(
            self.suppliers, self.questions, self.answers
        ).execute(
            user_id=self.user_id,
            supplier_id=self.empresa.id,
            question_id=pregunta.id,
            answer=answer,
        )

    def caso(self) -> StartFeasibilityUseCase:
        return StartFeasibilityUseCase(
            supplier_repo=self.suppliers,
            tender_repo=self.tenders,
            draft_repo=self.drafts,
            question_repo=self.questions,
            answer_repo=self.answers,
            catalog_use_case=BuildExperienceCatalogUseCase(
                self.suppliers, self.questions, self.answers, self.evidences
            ),
            chat_repo=self.chat,
            ai_service=self.ai,
        )

    async def ejecutar(self):
        return await self.caso().execute(
            user_id=self.user_id, supplier_id=self.empresa.id, tender_id=self.tender_id
        )


def _req(borrador, indice: int):
    return borrador.requirements[indice]


class TestCubiertasPorElCatalogo:
    async def test_una_cubierta_por_el_perfil_cumple(self):
        e = await Escenario(
            _exigencia(
                kind="disponibilidad",
                text="Entrega en Valparaíso",
                catalog_item_id="perfil:region:valparaiso",
            )
        ).preparar()

        borrador = await e.ejecutar()

        req = _req(borrador, 0)
        assert req.status == "cumple"
        assert req.catalog_item_id == "perfil:region:valparaiso"
        assert req.capability_question_id is None

    async def test_una_cubierta_por_un_si_previo_cumple_y_guarda_la_pregunta(self):
        e = await Escenario(
            _exigencia(catalog_item_id=f"capacidad:{SEC.id}")
        ).preparar()
        await e.responde(SEC, "Sí")

        borrador = await e.ejecutar()

        req = _req(borrador, 0)
        assert req.status == "cumple"
        assert req.capability_question_id == SEC.id

    async def test_un_no_previo_a_una_excluyente_pausa_y_se_puede_corregir(self):
        """El catalog_item_id explica el origen; la pregunta permite actualizarla."""
        e = await Escenario(
            _exigencia(catalog_item_id=f"capacidad:{SEC.id}")
        ).preparar()
        await e.responde(SEC, "No")

        borrador = await e.ejecutar()

        req = _req(borrador, 0)
        assert req.status == "no_cumple"
        assert req.catalog_item_id == f"capacidad:{SEC.id}"
        assert req.capability_question_id == SEC.id
        assert borrador.status == "PAUSED"
        assert borrador.paused_requirement_id == req.id

    async def test_un_id_de_catalogo_inventado_no_se_acepta(self):
        """Guardrail: la IA solo puede citar lo que existe."""
        e = await Escenario(
            _exigencia(catalog_item_id="perfil:certificacion:inventada")
        ).preparar()

        borrador = await e.ejecutar()

        req = _req(borrador, 0)
        assert req.catalog_item_id is None
        assert req.status == "parcial"


class TestPreguntasDelBanco:
    async def test_reutiliza_una_pregunta_del_banco_y_crea_la_respuesta_pendiente(self):
        e = await Escenario(_exigencia(question_key="registro_mop")).preparar()

        borrador = await e.ejecutar()

        req = _req(borrador, 0)
        assert req.status == "desconocido"
        assert req.capability_question_id == MOP.id
        pendiente = await e.answers.get(e.empresa.id, MOP.id)
        assert pendiente is not None
        assert pendiente.answered is False
        assert pendiente.tender_id == e.tender_id

    async def test_si_la_empresa_ya_la_respondio_usa_esa_respuesta(self):
        """La IA no la vio en el catálogo, pero la respuesta existe: no se pregunta de nuevo."""
        e = await Escenario(_exigencia(question_key="registro_mop")).preparar()
        await e.responde(MOP, "Sí")

        borrador = await e.ejecutar()

        assert _req(borrador, 0).status == "cumple"
        respuesta = await e.answers.get(e.empresa.id, MOP.id)
        assert respuesta is not None and respuesta.answered is True

    async def test_registra_una_pregunta_nueva_en_el_rubro_de_la_empresa(self):
        e = await Escenario(
            _exigencia(
                kind="experiencia",
                mandatory=False,
                new_question=NewQuestionDTO(
                    question="¿Tiene experiencia en obras viales?",
                    target_field="experiencia:obras-viales",
                    kind="experiencia_proyecto",
                    work_type="obras viales",
                ),
            )
        ).preparar()

        borrador = await e.ejecutar()

        nueva = await e.questions.get_by_key(CATEGORIA, "experiencia:obras-viales")
        assert nueva is not None
        assert nueva.origin == "ia"
        assert [o.label for o in nueva.options] == ["Sí", "No"]
        req = _req(borrador, 0)
        assert req.capability_question_id == nueva.id
        assert req.status == "desconocido"
        pendiente = await e.answers.get(e.empresa.id, nueva.id)
        assert pendiente is not None and pendiente.tender_id == e.tender_id

    async def test_una_pregunta_nueva_con_clave_existente_reutiliza_la_del_banco(self):
        e = await Escenario(
            _exigencia(
                new_question=NewQuestionDTO(
                    question="¿Tiene SEC clase A vigente?",
                    target_field="sec_clase_a",
                    kind="certificacion",
                )
            )
        ).preparar()

        borrador = await e.ejecutar()

        assert _req(borrador, 0).capability_question_id == SEC.id

    async def test_una_pregunta_que_nombra_a_la_empresa_no_entra_al_banco(self):
        e = await Escenario(
            _exigencia(
                new_question=NewQuestionDTO(
                    question="¿Andes Obras tiene laboratorio propio?",
                    target_field="laboratorio_propio",
                    kind="capacidad",
                )
            )
        ).preparar()

        borrador = await e.ejecutar()

        assert await e.questions.get_by_key(CATEGORIA, "laboratorio_propio") is None
        req = _req(borrador, 0)
        assert req.capability_question_id is None
        assert req.status == "parcial"

    async def test_la_ia_recibe_solo_las_preguntas_del_rubro_de_la_empresa(self):
        e = await Escenario().preparar()

        await e.ejecutar()

        recibidas = {q.id for q in e.ai.llamadas[0]["bank_questions"]}
        assert recibidas == {SEC.id, MOP.id, BIM.id}


class TestBorrador:
    async def test_guarda_el_borrador_de_la_empresa_con_su_autor(self):
        e = await Escenario(
            _exigencia(question_key="registro_mop"),
            requires_technical_document=True,
            technical_document_reason="Las bases piden una memoria técnica.",
        ).preparar()

        borrador = await e.ejecutar()

        guardado = await e.drafts.get(e.empresa.id, e.tender_id)
        assert guardado == borrador
        assert borrador.created_by_user_id == e.user_id
        assert borrador.requires_technical_document is True
        assert (
            borrador.technical_document_reason == "Las bases piden una memoria técnica."
        )
        assert [r.id for r in borrador.requirements] == ["req-1"]

    async def test_si_ya_hay_borrador_lo_devuelve_sin_llamar_a_la_ia(self):
        e = await Escenario(_exigencia(question_key="registro_mop")).preparar()
        primero = await e.ejecutar()

        segundo = await e.ejecutar()

        assert segundo == primero
        assert len(e.ai.llamadas) == 1

    async def test_manda_a_la_ia_los_adjuntos_del_usuario(self):
        e = await Escenario().preparar()
        documento = TenderChatDocument(
            tender_id=e.tender_id,
            user_id=e.user_id,
            file_name="bases.pdf",
            file_type="pdf",
            file_size_bytes=4,
            storage_path="x/bases.pdf",
        )
        await e.chat.save_document(documento, b"%PDF")

        await e.ejecutar()

        [doc] = e.ai.llamadas[0]["documents"]
        assert doc.document_name == "bases.pdf"
        assert doc.file_bytes == b"%PDF"


class TestErrores:
    async def test_una_licitacion_cerrada_sin_borrador_es_409(self):
        e = await Escenario().preparar()
        e.tenders.tenders[e.tender_id] = crear_licitacion(
            e.tender_id, status_code=TENDER_STATUSES["CLOSED"]
        )

        with pytest.raises(TenderClosedForProposal):
            await e.ejecutar()
        assert e.ai.llamadas == []

    async def test_una_licitacion_cerrada_con_borrador_lo_sigue_mostrando(self):
        e = await Escenario().preparar()
        borrador = await e.ejecutar()
        e.tenders.tenders[e.tender_id] = crear_licitacion(
            e.tender_id, status_code=TENDER_STATUSES["CLOSED"]
        )

        assert await e.ejecutar() == borrador

    async def test_licitacion_inexistente(self):
        e = await Escenario().preparar()
        e.tender_id = uuid4()

        with pytest.raises(TenderNotFound):
            await e.ejecutar()

    async def test_sin_empresa(self):
        e = await Escenario().preparar()

        with pytest.raises(SupplierNotFoundForUser):
            await e.caso().execute(
                user_id=uuid4(), supplier_id=None, tender_id=e.tender_id
            )


def test_ids_de_las_preguntas_de_prueba_son_distintos():
    assert len({SEC.id, MOP.id, BIM.id, OTRO_RUBRO.id}) == 4
    assert isinstance(SEC.id, UUID)


class TestCondicionesDelServicio:
    """Cantidades, duración, fechas o especificaciones: definen la oferta, no a la empresa.

    Cualquier proveedor que cotiza las acepta. Preguntarlas cansa y llena el
    banco de preguntas que no sirven en otra licitación: quedan cumplidas y la
    redacción las usa para describir la oferta.
    """

    async def test_una_condicion_queda_cumplida_sin_pregunta(self):
        e = await Escenario(
            _exigencia(kind="condicion", text="Duración total de 40 horas cronológicas")
        ).preparar()

        borrador = await e.ejecutar()

        req = _req(borrador, 0)
        assert req.kind == "condicion"
        assert req.status == "cumple"
        assert req.capability_question_id is None
        assert borrador.can_generate()

    async def test_una_condicion_no_crea_preguntas_aunque_la_ia_proponga_una(self):
        e = await Escenario(
            _exigencia(
                kind="condicion",
                text="Ejecución durante septiembre de 2026",
                new_question=NewQuestionDTO(
                    question="¿Tiene disponibilidad en septiembre de 2026?",
                    target_field="disponibilidad_septiembre",
                    kind="capacidad",
                ),
            )
        ).preparar()

        borrador = await e.ejecutar()

        assert (
            await e.questions.get_by_key(CATEGORIA, "disponibilidad_septiembre") is None
        )
        assert _req(borrador, 0).capability_question_id is None
        assert e.answers._filas == {}


class TestDocumentosNecesarios:
    """Adjuntar una cotización o un formulario no es una capacidad de la empresa.

    Son los documentos necesarios de la oferta (CA1): no se preguntan, quedan
    cumplidos y la redacción los lista.
    """

    async def test_un_documento_queda_cumplido_sin_pregunta(self):
        e = await Escenario(
            _exigencia(
                kind="documento",
                text="Adjuntar cotización y formulario de transferencias",
                new_question=NewQuestionDTO(
                    question="¿Cuenta con la cotización y el formulario?",
                    target_field="cotizacion_formulario",
                    kind="capacidad",
                ),
            )
        ).preparar()

        borrador = await e.ejecutar()

        req = _req(borrador, 0)
        assert req.kind == "documento"
        assert req.status == "cumple"
        assert req.capability_question_id is None
        assert await e.questions.get_by_key(CATEGORIA, "cotizacion_formulario") is None


async def _subir_bases(e: "Escenario", nombre: str = "bases.pdf") -> None:
    await e.chat.save_document(
        TenderChatDocument(
            tender_id=e.tender_id,
            user_id=e.user_id,
            file_name=nombre,
            file_type="pdf",
            file_size_bytes=4,
            storage_path=f"x/{nombre}",
        ),
        b"%PDF",
    )


class TestVolverAAnalizar:
    """Rehacer la factibilidad, por ejemplo tras subir las bases que faltaban.

    Solo si algo cambió desde el análisis anterior (adjuntos, catálogo de la
    empresa o la ficha). Si nada cambió, el borrador se mantiene tal cual.
    """

    async def _rehacer(self, e: "Escenario"):
        return await e.caso().execute(
            user_id=e.user_id,
            supplier_id=e.empresa.id,
            tender_id=e.tender_id,
            force=True,
        )

    async def test_sin_cambios_mantiene_el_borrador_redactado_sin_llamar_a_la_ia(self):
        e = await Escenario(_exigencia(question_key="registro_mop")).preparar()
        borrador = await e.ejecutar()
        # Redactado sin tocar el banco: el catálogo de la empresa no cambia.
        borrador.record_answer(MOP.id, "afirmativa")
        borrador.mark_ready(
            DraftContent(
                offer_name=DraftSection(),
                offer_description=DraftSection(),
                required_documents=DraftSection(),
            ),
            instructions=None,
        )
        await e.drafts.save(borrador)

        mismo = await self._rehacer(e)

        assert mismo.status == "READY"
        assert mismo.content is not None
        assert len(e.ai.llamadas) == 1

    async def test_subir_bases_nuevas_cuenta_como_cambio(self):
        e = await Escenario(_exigencia(question_key="registro_mop")).preparar()
        await e.ejecutar()
        await _subir_bases(e)

        await self._rehacer(e)

        assert len(e.ai.llamadas) == 2
        assert [d.document_name for d in e.ai.llamadas[1]["documents"]] == ["bases.pdf"]

    async def test_vuelve_a_llamar_a_la_ia_y_reemplaza_las_exigencias(self):
        e = await Escenario(_exigencia(question_key="registro_mop")).preparar()
        primero = await e.ejecutar()
        await _subir_bases(e)
        e.ai.resultado = FeasibilityResultDTO(
            requirements=[
                _exigencia(question_key="registro_mop"),
                _exigencia(kind="documento", text="Adjuntar cotización"),
            ],
            requires_technical_document=True,
        )

        segundo = await e.caso().execute(
            user_id=e.user_id,
            supplier_id=e.empresa.id,
            tender_id=e.tender_id,
            force=True,
        )

        assert len(e.ai.llamadas) == 2
        assert segundo.id == primero.id
        assert [r.kind for r in segundo.requirements] == ["certificacion", "documento"]
        assert segundo.requires_technical_document is True
        assert await e.drafts.get(e.empresa.id, e.tender_id) == segundo

    async def test_descarta_el_borrador_redactado_y_las_decisiones(self):
        e = await Escenario(_exigencia(question_key="registro_mop")).preparar()
        borrador = await e.ejecutar()
        await e.responde(MOP, "Sí")
        await _subir_bases(e)
        borrador.record_answer(MOP.id, "afirmativa")
        borrador.mark_ready(
            DraftContent(
                offer_name=DraftSection(),
                offer_description=DraftSection(),
                required_documents=DraftSection(),
            ),
            instructions="Más formal",
        )
        await e.drafts.save(borrador)

        nuevo = await e.caso().execute(
            user_id=e.user_id,
            supplier_id=e.empresa.id,
            tender_id=e.tender_id,
            force=True,
        )

        assert nuevo.status == "FEASIBILITY"
        assert nuevo.content is None
        assert nuevo.last_instructions is None
        assert nuevo.discrepancy_decisions == []

    async def test_reutiliza_las_respuestas_que_la_empresa_ya_dio(self):
        e = await Escenario(_exigencia(question_key="registro_mop")).preparar()
        await e.ejecutar()
        await e.responde(MOP, "Sí")
        await _subir_bases(e)

        nuevo = await e.caso().execute(
            user_id=e.user_id,
            supplier_id=e.empresa.id,
            tender_id=e.tender_id,
            force=True,
        )

        assert nuevo.requirements[0].status == "cumple"

    async def test_responder_las_preguntas_no_cuenta_como_cambio(self):
        """Si contara, responder la postulación ya bastaría para descartarla."""
        e = await Escenario(_exigencia(question_key="registro_mop")).preparar()
        await e.ejecutar()
        await e.responde(MOP, "Sí")

        await self._rehacer(e)

        assert len(e.ai.llamadas) == 1

    async def test_cambiar_el_perfil_cuenta_como_cambio(self):
        e = await Escenario(_exigencia(question_key="registro_mop")).preparar()
        await e.ejecutar()
        empresa = await e.suppliers.get_by_id(e.empresa.id)
        assert empresa is not None
        empresa.regions = [*(empresa.regions or []), "Aysén"]
        empresa.updated_at = empresa.updated_at + timedelta(minutes=1)
        await e.suppliers.save(empresa)

        await self._rehacer(e)

        assert len(e.ai.llamadas) == 2

    async def test_tocar_la_empresa_sin_cambiar_lo_que_se_analiza_no_cuenta(self):
        """El banner del home escribe `keywords` y mueve `updated_at`, pero la
        factibilidad no usa las keywords: no hay nada nuevo que analizar."""
        e = await Escenario(_exigencia(question_key="registro_mop")).preparar()
        await e.ejecutar()
        empresa = await e.suppliers.get_by_id(e.empresa.id)
        assert empresa is not None
        empresa.keywords = [*(empresa.keywords or []), "mop_registration:Sí"]
        empresa.updated_at = empresa.updated_at + timedelta(minutes=1)
        await e.suppliers.save(empresa)

        await self._rehacer(e)

        assert len(e.ai.llamadas) == 1

    async def test_con_la_licitacion_cerrada_no_se_vuelve_a_analizar(self):
        e = await Escenario().preparar()
        await e.ejecutar()
        e.tenders.tenders[e.tender_id] = crear_licitacion(
            e.tender_id, status_code=TENDER_STATUSES["CLOSED"]
        )

        with pytest.raises(TenderClosedForProposal):
            await e.caso().execute(
                user_id=e.user_id,
                supplier_id=e.empresa.id,
                tender_id=e.tender_id,
                force=True,
            )
        assert len(e.ai.llamadas) == 1


class TestPreguntasSugeridasEnLaFactibilidad:
    """Hasta 3 preguntas para fortalecer la oferta, solo de lo que no se sabe."""

    def _sugerida(self, **kwargs) -> FeasibilityRequirementDTO:
        datos = dict(
            text="Experiencia en suministros a municipios",
            kind="experiencia",
            mandatory=True,  # la IA podría marcarla; una sugerida nunca es excluyente
            origin="IA",
            new_question=NewQuestionDTO(
                question="¿Tiene experiencia suministrando materiales a municipios?",
                target_field="experiencia:suministro-municipios",
                kind="experiencia_proyecto",
                work_type="suministro a municipios",
            ),
        )
        datos.update(kwargs)
        return FeasibilityRequirementDTO(**datos)

    async def test_se_agregan_como_preguntas_no_excluyentes(self):
        e = Escenario()
        e.ai.resultado = FeasibilityResultDTO(offer_questions=[self._sugerida()])
        await e.preparar()

        borrador = await e.ejecutar()

        [sug] = borrador.requirements
        assert sug.suggested is True
        assert sug.mandatory is False
        assert sug.id == "sug-1"
        assert sug.status == "desconocido"
        assert not borrador.can_generate()

    async def test_maximo_tres(self):
        e = Escenario()
        e.ai.resultado = FeasibilityResultDTO(
            offer_questions=[
                self._sugerida(
                    new_question=NewQuestionDTO(
                        question=f"¿Pregunta {i}?",
                        target_field=f"sug_{i}",
                        kind="capacidad",
                    )
                )
                for i in range(5)
            ]
        )
        await e.preparar()

        borrador = await e.ejecutar()

        assert len([r for r in borrador.requirements if r.suggested]) == 3

    async def test_lo_que_la_empresa_ya_respondio_no_se_sugiere(self):
        e = Escenario()
        e.ai.resultado = FeasibilityResultDTO(
            offer_questions=[
                self._sugerida(new_question=None, question_key="registro_mop")
            ]
        )
        await e.preparar()
        await e.responde(MOP, "Sí")

        borrador = await e.ejecutar()

        assert borrador.requirements == []

    async def test_una_condicion_o_un_documento_no_se_sugiere(self):
        e = Escenario()
        e.ai.resultado = FeasibilityResultDTO(
            offer_questions=[self._sugerida(kind="condicion", new_question=None)]
        )
        await e.preparar()

        borrador = await e.ejecutar()

        assert borrador.requirements == []
