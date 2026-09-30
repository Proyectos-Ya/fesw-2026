"""Banco de preguntas de capacidades: reglas de las entidades (HU-20, B0a).

La polaridad de cada opción se exige desde ahora aunque el matching todavía no
la use (PENDIENTES 6.29): deducirla después leyendo etiquetas libres sería
frágil, y cambiar la forma del banco con respuestas ya dadas cuesta más.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.entities.capability import (
    CapabilityAnswer,
    CapabilityEvidence,
    CapabilityOption,
    CapabilityQuestion,
    evidence_for_answer,
    question_leaks_supplier_data,
)
from app.domain.entities.supplier import Supplier
from app.domain.errors.capability_errors import EvidenceNeedsAffirmativeProjectAnswer
from app.shared.datetime_utils import utc_now_naive


def _pregunta(**kwargs) -> CapabilityQuestion:
    datos = dict(
        question="¿Cuenta con inscripción vigente en el Registro de Contratistas del MOP?",
        target_field="mop_registration",
        category="construccion",
        options=[
            CapabilityOption(label="No", polarity="negativa"),
            CapabilityOption(label="Sí, en Primera Categoría", polarity="afirmativa"),
        ],
    )
    datos.update(kwargs)
    return CapabilityQuestion(**datos)


class TestCapabilityOption:
    def test_la_polaridad_es_obligatoria(self):
        with pytest.raises(ValidationError):
            CapabilityOption(label="Sí")  # type: ignore[call-arg]

    def test_rechaza_una_polaridad_fuera_del_vocabulario(self):
        with pytest.raises(ValidationError):
            CapabilityOption(label="Sí", polarity="positiva")  # type: ignore[arg-type]

    def test_rechaza_etiqueta_vacia(self):
        with pytest.raises(ValidationError):
            CapabilityOption(label="  ", polarity="neutra")


class TestCapabilityQuestion:
    def test_valores_por_defecto(self):
        pregunta = _pregunta()
        assert pregunta.kind == "capacidad"
        assert pregunta.origin == "semilla"
        assert pregunta.active is True
        assert pregunta.work_type is None

    def test_normaliza_la_categoria_a_minusculas(self):
        assert _pregunta(category="  Construccion ").category == "construccion"

    def test_rechaza_enunciado_vacio(self):
        with pytest.raises(ValidationError):
            _pregunta(question="   ")

    def test_experiencia_en_proyectos_exige_tipo_de_trabajo(self):
        with pytest.raises(ValidationError):
            _pregunta(kind="experiencia_proyecto")

    def test_experiencia_en_proyectos_con_tipo_de_trabajo(self):
        pregunta = _pregunta(
            kind="experiencia_proyecto",
            work_type="restauración de patrimonio",
        )
        assert pregunta.work_type == "restauración de patrimonio"

    def test_una_certificacion_es_un_tipo_valido(self):
        assert _pregunta(kind="certificacion").kind == "certificacion"

    def test_una_certificacion_no_lleva_tipo_de_trabajo(self):
        with pytest.raises(ValidationError):
            _pregunta(kind="certificacion", work_type="obras viales")

    def test_rechaza_un_tipo_fuera_del_vocabulario(self):
        with pytest.raises(ValidationError):
            _pregunta(kind="habilidad")

    def test_una_capacidad_no_lleva_tipo_de_trabajo(self):
        with pytest.raises(ValidationError):
            _pregunta(work_type="obras viales")

    def test_rechaza_etiquetas_de_opcion_repetidas(self):
        with pytest.raises(ValidationError):
            _pregunta(
                options=[
                    CapabilityOption(label="Sí", polarity="afirmativa"),
                    CapabilityOption(label="Sí", polarity="negativa"),
                ]
            )

    def test_acepta_solo_respuestas_que_son_una_opcion(self):
        pregunta = _pregunta()
        assert pregunta.accepts("Sí, en Primera Categoría")
        assert not pregunta.accepts("Tal vez")

    def test_sin_opciones_acepta_texto_libre_no_vacio(self):
        pregunta = _pregunta(options=[])
        assert pregunta.accepts("Tenemos laboratorio propio")
        assert not pregunta.accepts("   ")

    def test_la_polaridad_de_una_respuesta_sale_de_su_opcion(self):
        pregunta = _pregunta()
        assert pregunta.polarity_of("No") == "negativa"
        assert pregunta.polarity_of("Texto libre") is None


class TestCapabilityAnswer:
    def test_pendiente_por_defecto(self):
        respuesta = CapabilityAnswer(supplier_id=uuid4(), question_id=uuid4())
        assert respuesta.answered is False
        assert respuesta.omitted is False
        assert respuesta.answer is None
        assert respuesta.answered_at is None

    def test_respondida_exige_texto(self):
        with pytest.raises(ValidationError):
            CapabilityAnswer(
                supplier_id=uuid4(), question_id=uuid4(), answered=True, answer=" "
            )

    def test_quien_respondio_y_la_vigencia_son_opcionales(self):
        respuesta = CapabilityAnswer(supplier_id=uuid4(), question_id=uuid4())
        assert respuesta.answered_by_user_id is None
        assert respuesta.valid_until is None

    def test_no_puede_estar_respondida_y_omitida(self):
        with pytest.raises(ValidationError):
            CapabilityAnswer(
                supplier_id=uuid4(),
                question_id=uuid4(),
                answered=True,
                answer="Sí",
                omitted=True,
            )


class TestVigenciaDeLaRespuesta:
    """Una certificación vence: pasada su vigencia, la respuesta deja de valer."""

    AHORA = datetime(2026, 9, 30, 12, 0, 0)

    def _respondida(self, **kwargs) -> CapabilityAnswer:
        return CapabilityAnswer(
            supplier_id=uuid4(),
            question_id=uuid4(),
            answered=True,
            answer="Sí",
            answered_at=self.AHORA - timedelta(days=30),
            **kwargs,
        )

    def test_sin_vigencia_una_respuesta_sigue_vigente(self):
        assert self._respondida().is_current(self.AHORA)

    def test_una_vigencia_con_zona_se_guarda_en_utc_sin_zona(self):
        """Las columnas son `TIMESTAMP WITHOUT TIME ZONE`: con zona, asyncpg falla (500)."""
        santiago = timezone(timedelta(hours=-3))
        respuesta = self._respondida(
            valid_until=datetime(2027, 6, 30, 0, 0, tzinfo=santiago)
        )
        assert respuesta.valid_until == datetime(2027, 6, 30, 3, 0)
        assert respuesta.valid_until.tzinfo is None

    def test_con_vigencia_futura_sigue_vigente(self):
        respuesta = self._respondida(valid_until=self.AHORA + timedelta(days=1))
        assert respuesta.is_current(self.AHORA)

    def test_con_vigencia_vencida_deja_de_estar_vigente(self):
        respuesta = self._respondida(valid_until=self.AHORA - timedelta(seconds=1))
        assert not respuesta.is_current(self.AHORA)

    def test_una_pendiente_o_una_omitida_no_esta_vigente(self):
        pendiente = CapabilityAnswer(supplier_id=uuid4(), question_id=uuid4())
        omitida = CapabilityAnswer(
            supplier_id=uuid4(), question_id=uuid4(), omitted=True
        )
        assert not pendiente.is_current(self.AHORA)
        assert not omitida.is_current(self.AHORA)


def _evidencia(**kwargs) -> CapabilityEvidence:
    datos = dict(
        supplier_id=uuid4(),
        work_type="obras viales",
        title="Pavimentación calle Los Aromos",
        buyer="Municipalidad de Quilpué",
        year=2024,
        amount_clp=45_000_000,
    )
    datos.update(kwargs)
    return CapabilityEvidence(**datos)


class TestCapabilityEvidence:
    def test_valores_por_defecto(self):
        evidencia = _evidencia()
        assert evidencia.origin == "manual"
        assert evidencia.answer_id is None
        assert evidencia.created_by_user_id is None

    def test_acepta_el_origen_mercado_publico(self):
        assert _evidencia(origin="mercado_publico").origin == "mercado_publico"

    def test_rechaza_un_origen_fuera_del_vocabulario(self):
        with pytest.raises(ValidationError):
            _evidencia(origin="linkedin")

    def test_exige_titulo(self):
        with pytest.raises(ValidationError):
            _evidencia(title="  ")

    def test_exige_tipo_de_trabajo(self):
        """Sin respuesta de la que heredarlo, el tipo de trabajo es lo que la clasifica."""
        with pytest.raises(ValidationError):
            _evidencia(work_type=None)

    def test_rechaza_un_anio_futuro(self):
        with pytest.raises(ValidationError):
            _evidencia(year=utc_now_naive().year + 1)

    def test_rechaza_un_anio_implausible(self):
        with pytest.raises(ValidationError):
            _evidencia(year=1899)

    def test_rechaza_un_monto_negativo(self):
        with pytest.raises(ValidationError):
            _evidencia(amount_clp=-1)

    def test_mandante_monto_y_descripcion_son_opcionales(self):
        evidencia = _evidencia(buyer=None, amount_clp=None, description=None)
        assert evidencia.buyer is None
        assert evidencia.amount_clp is None


class TestEvidenciaDeUnaRespuesta:
    """Una evidencia colgada de una respuesta respalda un "Sí" de experiencia."""

    def _proyecto(self) -> CapabilityQuestion:
        return _pregunta(
            kind="experiencia_proyecto",
            work_type="obras viales",
            target_field="experiencia:obras-viales",
        )

    def _respuesta(self, pregunta: CapabilityQuestion, answer: str) -> CapabilityAnswer:
        return CapabilityAnswer(
            supplier_id=uuid4(),
            question_id=pregunta.id,
            answered=True,
            answer=answer,
        )

    def test_hereda_empresa_y_tipo_de_trabajo_de_la_respuesta(self):
        pregunta = self._proyecto()
        respuesta = self._respuesta(pregunta, "Sí, en Primera Categoría")
        autor = uuid4()

        evidencia = evidence_for_answer(
            pregunta,
            respuesta,
            title="Pavimentación calle Los Aromos",
            year=2024,
            created_by_user_id=autor,
        )

        assert evidencia.answer_id == respuesta.id
        assert evidencia.supplier_id == respuesta.supplier_id
        assert evidencia.work_type == "obras viales"
        assert evidencia.origin == "manual"
        assert evidencia.created_by_user_id == autor

    def test_rechaza_una_respuesta_negativa(self):
        pregunta = self._proyecto()
        with pytest.raises(EvidenceNeedsAffirmativeProjectAnswer):
            evidence_for_answer(
                pregunta, self._respuesta(pregunta, "No"), title="X", year=2024
            )

    def test_rechaza_una_pregunta_que_no_es_de_experiencia_en_proyectos(self):
        pregunta = _pregunta()
        with pytest.raises(EvidenceNeedsAffirmativeProjectAnswer):
            evidence_for_answer(
                pregunta,
                self._respuesta(pregunta, "Sí, en Primera Categoría"),
                title="X",
                year=2024,
            )

    def test_rechaza_una_respuesta_pendiente(self):
        pregunta = self._proyecto()
        pendiente = CapabilityAnswer(supplier_id=uuid4(), question_id=pregunta.id)
        with pytest.raises(EvidenceNeedsAffirmativeProjectAnswer):
            evidence_for_answer(pregunta, pendiente, title="X", year=2024)

    def test_rechaza_una_respuesta_de_otra_pregunta(self):
        pregunta = self._proyecto()
        ajena = self._respuesta(self._proyecto(), "Sí, en Primera Categoría")
        with pytest.raises(EvidenceNeedsAffirmativeProjectAnswer):
            evidence_for_answer(pregunta, ajena, title="X", year=2024)


class TestFugaDeDatosDeLaEmpresa:
    """Una pregunta del banco la ven todas las empresas: no puede nombrar a una."""

    @pytest.fixture
    def empresa(self) -> Supplier:
        return Supplier(
            rut="76086428-5",
            legal_name="Constructora Andes SpA",
            trade_name="Andes Obras",
        )

    def test_una_pregunta_generica_no_filtra(self, empresa):
        assert not question_leaks_supplier_data(
            "¿Cuenta con laboratorio de ensayos de hormigón acreditado?", empresa
        )

    def test_detecta_la_razon_social_sin_importar_tildes_ni_mayusculas(self, empresa):
        assert question_leaks_supplier_data(
            "¿CONSTRUCTORA ÁNDES SPA tiene laboratorio propio?", empresa
        )

    def test_detecta_el_nombre_de_fantasia(self, empresa):
        assert question_leaks_supplier_data("¿Andes Obras opera en regiones?", empresa)

    def test_detecta_el_rut_en_cualquier_formato(self, empresa):
        assert question_leaks_supplier_data(
            "¿La empresa 76086428-5 está al día?", empresa
        )
        assert question_leaks_supplier_data(
            "¿La empresa 76.086.428-5 está al día?", empresa
        )
