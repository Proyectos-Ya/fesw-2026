"""Casos de uso del banco de capacidades y del catálogo de experiencia (HU-20, B0b).

Todo se resuelve contra la **empresa activa**: las respuestas y los proyectos son
de la empresa, no de quien los cargó, así que cualquier miembro ve lo que
respondió otro y ninguna otra empresa lo ve.
"""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.application.use_cases.capabilities.add_capability_evidence import (
    AddCapabilityEvidenceUseCase,
)
from app.application.use_cases.capabilities.answer_capability_question import (
    AnswerCapabilityQuestionUseCase,
)
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.application.use_cases.capabilities.list_pending_questions import (
    ListPendingCapabilityQuestionsUseCase,
)
from app.application.use_cases.capabilities.register_capability_question import (
    RegisterCapabilityQuestionUseCase,
)
from app.domain.entities.capability import (
    CapabilityAnswer,
    CapabilityEvidence,
    CapabilityOption,
    CapabilityQuestion,
)
from app.domain.entities.supplier import Supplier
from app.domain.errors.capability_errors import (
    CapabilityQuestionNotFound,
    DuplicateCapabilityQuestion,
    EvidenceNeedsAffirmativeProjectAnswer,
    InvalidCapabilityAnswer,
    QuestionLeaksSupplierData,
)
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.shared.datetime_utils import utc_now_naive
from tests.unit.application.fakes import (
    InMemoryCapabilityAnswerRepository,
    InMemoryCapabilityEvidenceRepository,
    InMemoryCapabilityQuestionRepository,
    InMemorySupplierRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.test_score_tender_on_demand import crear_licitacion


def _pregunta(target_field: str = "sec_clase_a", **kwargs) -> CapabilityQuestion:
    datos = dict(
        question=f"¿Pregunta sobre {target_field}?",
        target_field=target_field,
        category="construccion",
        options=[
            CapabilityOption(label="No", polarity="negativa"),
            CapabilityOption(label="Sí", polarity="afirmativa"),
        ],
    )
    datos.update(kwargs)
    return CapabilityQuestion(**datos)


def _proyecto() -> CapabilityQuestion:
    return _pregunta(
        "experiencia:obras-viales",
        kind="experiencia_proyecto",
        work_type="obras viales",
    )


class Escenario:
    """Una empresa con dos miembros (dueña y otra persona) y una empresa ajena."""

    def __init__(self, preguntas: list[CapabilityQuestion] | None = None) -> None:
        self.suppliers = InMemorySupplierRepository()
        self.questions = InMemoryCapabilityQuestionRepository(preguntas)
        self.answers = InMemoryCapabilityAnswerRepository()
        self.evidences = InMemoryCapabilityEvidenceRepository()
        self.duena = uuid4()
        self.miembro = uuid4()
        self.ajeno = uuid4()

    async def preparar(self) -> "Escenario":
        self.empresa = await self.suppliers.save(
            Supplier(
                user_id=self.duena,
                rut="76086428-5",
                legal_name="Constructora Andes SpA",
                trade_name="Andes Obras",
                sectors=["Obras de Construcción e Infraestructura"],
                regions=["Valparaíso", "Metropolitana"],
                certifications=["ISO 9001:2015"],
                years_experience=12,
                description="Obras viales y pavimentación.",
            )
        )
        self.otra = await self.suppliers.save(
            Supplier(user_id=self.ajeno, rut="77654321-7", legal_name="Otra Ltda")
        )
        return self

    def responder(self) -> AnswerCapabilityQuestionUseCase:
        return AnswerCapabilityQuestionUseCase(
            self.suppliers, self.questions, self.answers
        )

    def evidencia(self) -> AddCapabilityEvidenceUseCase:
        return AddCapabilityEvidenceUseCase(
            self.suppliers, self.questions, self.answers, self.evidences
        )

    def catalogo(self) -> BuildExperienceCatalogUseCase:
        return BuildExperienceCatalogUseCase(
            self.suppliers, self.questions, self.answers, self.evidences
        )

    async def responde(
        self, user_id: UUID, pregunta: CapabilityQuestion, answer: str = "Sí", **kw
    ):
        return await self.responder().execute(
            user_id=user_id,
            supplier_id=self.empresa.id,
            question_id=pregunta.id,
            answer=answer,
            **kw,
        )


class TestResponder:
    async def test_guarda_la_respuesta_de_la_empresa_activa_y_quien_respondio(self):
        sec = _pregunta()
        e = await Escenario([sec]).preparar()

        respuesta = await e.responde(e.miembro, sec)

        assert respuesta.supplier_id == e.empresa.id
        assert respuesta.answered is True
        assert respuesta.answer == "Sí"
        assert respuesta.answered_by_user_id == e.miembro
        assert respuesta.answered_at is not None
        assert await e.answers.get(e.empresa.id, sec.id) == respuesta

    async def test_sin_empresa_activa_usa_la_propia(self):
        sec = _pregunta()
        e = await Escenario([sec]).preparar()

        respuesta = await e.responder().execute(
            user_id=e.duena, supplier_id=None, question_id=sec.id, answer="Sí"
        )

        assert respuesta.supplier_id == e.empresa.id

    async def test_sin_empresa_falla(self):
        sec = _pregunta()
        e = await Escenario([sec]).preparar()

        with pytest.raises(SupplierNotFoundForUser):
            await e.responder().execute(
                user_id=uuid4(), supplier_id=None, question_id=sec.id, answer="Sí"
            )

    async def test_no_escribe_en_keywords_ni_certificaciones(self):
        sec = _pregunta(kind="certificacion")
        e = await Escenario([sec]).preparar()

        await e.responde(e.duena, sec)

        empresa = await e.suppliers.get_by_id(e.empresa.id)
        assert empresa is not None
        assert empresa.keywords is None
        assert empresa.certifications == ["ISO 9001:2015"]

    async def test_guarda_la_vigencia_y_la_licitacion_de_origen(self):
        sec = _pregunta(kind="certificacion")
        e = await Escenario([sec]).preparar()
        vence = utc_now_naive() + timedelta(days=90)
        tender_id = uuid4()

        respuesta = await e.responde(
            e.duena, sec, valid_until=vence, tender_id=tender_id
        )

        assert respuesta.valid_until == vence
        assert respuesta.tender_id == tender_id

    async def test_corregir_conserva_la_licitacion_de_origen(self):
        sec = _pregunta()
        e = await Escenario([sec]).preparar()
        tender_id = uuid4()
        await e.responde(e.duena, sec, answer="No", tender_id=tender_id)

        corregida = await e.responde(e.miembro, sec, answer="Sí")

        assert corregida.answer == "Sí"
        assert corregida.answered_by_user_id == e.miembro
        assert corregida.tender_id == tender_id

    async def test_rechaza_una_respuesta_que_no_es_opcion(self):
        sec = _pregunta()
        e = await Escenario([sec]).preparar()

        with pytest.raises(InvalidCapabilityAnswer):
            await e.responde(e.duena, sec, answer="Tal vez")

    async def test_rechaza_una_pregunta_inexistente(self):
        e = await Escenario().preparar()

        with pytest.raises(CapabilityQuestionNotFound):
            await e.responde(e.duena, _pregunta())


class TestAgregarEvidencia:
    async def test_cuelga_el_proyecto_del_si_de_la_empresa(self):
        proyecto = _proyecto()
        e = await Escenario([proyecto]).preparar()
        respuesta = await e.responde(e.duena, proyecto)

        evidencia = await e.evidencia().execute(
            user_id=e.miembro,
            supplier_id=e.empresa.id,
            question_id=proyecto.id,
            title="Pavimentación calle Los Aromos",
            year=2024,
            buyer="Municipalidad de Quilpué",
            amount_clp=45_000_000,
        )

        assert evidencia.answer_id == respuesta.id
        assert evidencia.supplier_id == e.empresa.id
        assert evidencia.work_type == "obras viales"
        assert evidencia.created_by_user_id == e.miembro
        assert e.evidences.filas == [evidencia]

    async def test_sin_respuesta_de_la_empresa_no_se_puede(self):
        proyecto = _proyecto()
        e = await Escenario([proyecto]).preparar()

        with pytest.raises(EvidenceNeedsAffirmativeProjectAnswer):
            await e.evidencia().execute(
                user_id=e.duena,
                supplier_id=e.empresa.id,
                question_id=proyecto.id,
                title="X",
                year=2024,
            )

    async def test_no_respalda_un_no(self):
        proyecto = _proyecto()
        e = await Escenario([proyecto]).preparar()
        await e.responde(e.duena, proyecto, answer="No")

        with pytest.raises(EvidenceNeedsAffirmativeProjectAnswer):
            await e.evidencia().execute(
                user_id=e.duena,
                supplier_id=e.empresa.id,
                question_id=proyecto.id,
                title="X",
                year=2024,
            )

    async def test_no_usa_la_respuesta_de_otra_empresa(self):
        proyecto = _proyecto()
        e = await Escenario([proyecto]).preparar()
        await e.responde(e.duena, proyecto)

        with pytest.raises(EvidenceNeedsAffirmativeProjectAnswer):
            await e.evidencia().execute(
                user_id=e.ajeno,
                supplier_id=e.otra.id,
                question_id=proyecto.id,
                title="X",
                year=2024,
            )


class TestRegistrarPregunta:
    async def test_agrega_una_pregunta_generica_al_banco(self):
        e = await Escenario().preparar()
        nueva = _pregunta("laboratorio_hormigon", origin="ia")

        guardada = await RegisterCapabilityQuestionUseCase(e.questions).execute(
            nueva, origin_supplier=e.empresa
        )

        assert await e.questions.get(guardada.id) == nueva

    async def test_rechaza_una_pregunta_que_nombra_a_la_empresa(self):
        e = await Escenario().preparar()
        filtrada = _pregunta(question="¿Andes Obras tiene laboratorio propio?")

        with pytest.raises(QuestionLeaksSupplierData):
            await RegisterCapabilityQuestionUseCase(e.questions).execute(
                filtrada, origin_supplier=e.empresa
            )
        assert await e.questions.get(filtrada.id) is None

    async def test_un_duplicado_trae_la_existente(self):
        existente = _pregunta()
        e = await Escenario([existente]).preparar()

        with pytest.raises(DuplicateCapabilityQuestion) as error:
            await RegisterCapabilityQuestionUseCase(e.questions).execute(
                _pregunta(question="Otra redacción"), origin_supplier=e.empresa
            )

        assert error.value.existing == existente


class TestCatalogo:
    async def _catalogo(self, e: Escenario, user_id: UUID, supplier_id: UUID):
        return await e.catalogo().execute(user_id=user_id, supplier_id=supplier_id)

    async def test_incluye_el_perfil_con_ids_estables(self):
        e = await Escenario().preparar()

        catalogo = await self._catalogo(e, e.duena, e.empresa.id)

        ids = {item.id for item in catalogo.items}
        assert {
            "perfil:anios-experiencia",
            "perfil:descripcion",
            "perfil:certificacion:iso-9001-2015",
            "perfil:sector:obras-de-construccion-e-infraestructura",
            "perfil:region:valparaiso",
            "perfil:region:metropolitana",
        } <= ids
        assert all(item.origin == "perfil" for item in catalogo.items)

    async def test_incluye_respuestas_afirmativas_y_negativas_con_su_polaridad(self):
        sec, bim = _pregunta("sec_clase_a"), _pregunta("bim")
        e = await Escenario([sec, bim]).preparar()
        await e.responde(e.duena, sec, answer="Sí")
        await e.responde(e.duena, bim, answer="No")

        catalogo = await self._catalogo(e, e.duena, e.empresa.id)

        por_id = {item.id: item for item in catalogo.items}
        assert por_id[f"capacidad:{sec.id}"].polarity == "afirmativa"
        assert por_id[f"capacidad:{bim.id}"].polarity == "negativa"
        assert por_id[f"capacidad:{sec.id}"].title == sec.question
        assert por_id[f"capacidad:{sec.id}"].answered_by_user_id == e.duena
        # Para explicar de dónde viene una pausa: "respondiste 'No' el 12-oct".
        assert por_id[f"capacidad:{bim.id}"].answered_at is not None

    async def test_un_miembro_ve_lo_que_respondio_otro_de_la_misma_empresa(self):
        sec = _pregunta()
        e = await Escenario([sec]).preparar()
        await e.responde(e.miembro, sec)

        catalogo = await self._catalogo(e, e.duena, e.empresa.id)

        assert f"capacidad:{sec.id}" in {item.id for item in catalogo.items}

    async def test_otra_empresa_no_ve_las_respuestas(self):
        sec = _pregunta()
        e = await Escenario([sec]).preparar()
        await e.responde(e.duena, sec)

        catalogo = await self._catalogo(e, e.ajeno, e.otra.id)

        assert all(item.origin == "perfil" for item in catalogo.items)

    async def test_excluye_respuestas_vencidas(self):
        sec = _pregunta(kind="certificacion")
        e = await Escenario([sec]).preparar()
        await e.responde(
            e.duena, sec, valid_until=utc_now_naive() - timedelta(minutes=1)
        )

        catalogo = await self._catalogo(e, e.duena, e.empresa.id)

        assert f"capacidad:{sec.id}" not in {item.id for item in catalogo.items}

    async def test_incluye_los_proyectos_manuales(self):
        proyecto = _proyecto()
        e = await Escenario([proyecto]).preparar()
        await e.responde(e.duena, proyecto)
        evidencia = await e.evidencia().execute(
            user_id=e.duena,
            supplier_id=e.empresa.id,
            question_id=proyecto.id,
            title="Pavimentación calle Los Aromos",
            year=2024,
            buyer="Municipalidad de Quilpué",
            amount_clp=45_000_000,
        )

        catalogo = await self._catalogo(e, e.duena, e.empresa.id)

        item = next(i for i in catalogo.items if i.id == f"evidencia:{evidencia.id}")
        assert item.origin == "evidencia"
        assert item.kind == "experiencia_proyecto"
        assert item.title == "Pavimentación calle Los Aromos"
        assert "Municipalidad de Quilpué" in item.detail
        assert "2024" in item.detail
        assert "45.000.000" in item.detail

    async def test_excluye_los_proyectos_importados_sin_confirmar(self):
        """Hasta que exista la confirmación (spike de Mercado Público), no se citan."""
        e = await Escenario().preparar()
        importada = await e.evidences.add(
            CapabilityEvidence(
                supplier_id=e.empresa.id,
                work_type="obras viales",
                origin="mercado_publico",
                title="OC 1234-56-SE24",
                year=2024,
            )
        )

        catalogo = await self._catalogo(e, e.duena, e.empresa.id)

        assert f"evidencia:{importada.id}" not in {item.id for item in catalogo.items}

    async def test_last_changed_at_es_el_ultimo_cambio(self):
        sec = _pregunta()
        e = await Escenario([sec]).preparar()
        respuesta = await e.responde(e.duena, sec)

        catalogo = await self._catalogo(e, e.duena, e.empresa.id)

        assert catalogo.last_changed_at == max(
            e.empresa.updated_at, respuesta.answered_at
        )

    async def test_sin_empresa_falla(self):
        e = await Escenario().preparar()

        with pytest.raises(SupplierNotFoundForUser):
            await e.catalogo().execute(user_id=uuid4(), supplier_id=None)


class TestPendientes:
    """Preguntas que la empresa tiene por responder, con la licitación que las originó."""

    async def _escenario(self, *preguntas):
        e = await Escenario(list(preguntas)).preparar()
        tenders = InMemoryTenderRepository()
        tender_id = uuid4()
        tenders.tenders[tender_id] = crear_licitacion(tender_id)
        caso = ListPendingCapabilityQuestionsUseCase(
            e.suppliers, e.questions, e.answers, tenders
        )
        return e, caso, tender_id

    async def _pendiente(self, e: Escenario, pregunta, tender_id=None):
        await e.answers.save(
            CapabilityAnswer(
                supplier_id=e.empresa.id, question_id=pregunta.id, tender_id=tender_id
            )
        )

    async def test_lista_las_pendientes_con_su_licitacion(self):
        sec = _pregunta()
        e, caso, tender_id = await self._escenario(sec)
        await self._pendiente(e, sec, tender_id)

        [pendiente] = await caso.execute(user_id=e.duena, supplier_id=e.empresa.id)

        assert pendiente.question == sec
        assert pendiente.tender_id == tender_id
        assert pendiente.tender_code == f"COT-{tender_id}"

    async def test_no_lista_las_respondidas_ni_las_omitidas(self):
        sec, bim, mop = _pregunta("sec"), _pregunta("bim"), _pregunta("mop")
        e, caso, _ = await self._escenario(sec, bim, mop)
        await self._pendiente(e, sec)
        await e.responde(e.duena, bim)
        await e.answers.save(
            CapabilityAnswer(supplier_id=e.empresa.id, question_id=mop.id, omitted=True)
        )

        pendientes = await caso.execute(user_id=e.duena, supplier_id=e.empresa.id)

        assert [p.question.id for p in pendientes] == [sec.id]

    async def test_una_respuesta_vencida_vuelve_a_quedar_pendiente(self):
        sec = _pregunta(kind="certificacion")
        e, caso, _ = await self._escenario(sec)
        await e.responde(
            e.duena, sec, valid_until=utc_now_naive() - timedelta(minutes=1)
        )

        [pendiente] = await caso.execute(user_id=e.duena, supplier_id=e.empresa.id)

        assert pendiente.question.id == sec.id
        assert pendiente.tender_id is None

    async def test_otra_empresa_no_ve_las_pendientes(self):
        sec = _pregunta()
        e, caso, _ = await self._escenario(sec)
        await self._pendiente(e, sec)

        assert await caso.execute(user_id=e.ajeno, supplier_id=e.otra.id) == []
