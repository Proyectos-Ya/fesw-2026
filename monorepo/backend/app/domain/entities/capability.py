"""Banco de preguntas de capacidades y evidencias de experiencia (HU-20).

Las preguntas **capturan** un dato; lo que se guarda es una capacidad de la
empresa. Tres piezas con dueños distintos:

* `CapabilityQuestion` es del **banco**, compartido entre empresas. Por eso nunca
  puede nombrar a una empresa concreta (`question_leaks_supplier_data`): la
  pregunta se deriva de lo que exige una licitación, no de los datos de quien
  la responde.
* `CapabilityAnswer` es de **una** empresa y apunta a una pregunta del banco.
* `CapabilityEvidence` es un proyecto de **una** empresa que respalda su
  experiencia: es lo que el borrador de postulación cita como "el proyecto".
"""

import re
import unicodedata
from datetime import datetime
from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.entities.supplier import Supplier
from app.domain.errors.capability_errors import EvidenceNeedsAffirmativeProjectAnswer
from app.shared.datetime_utils import (
    UtcDateTime,
    aware_to_utc_naive,
    utc_now_naive,
)

# Se exige desde ya aunque el matching todavía no la use (PENDIENTES 6.29).
Polarity = Literal["afirmativa", "negativa", "neutra"]
CapabilityKind = Literal["capacidad", "certificacion", "experiencia_proyecto"]
QuestionOrigin = Literal["semilla", "ia"]
# `mercado_publico` queda reservado para importar órdenes de compra adjudicadas
# (plan 230, §5 punto 10). Se admite desde ya para no migrar la columna después.
EvidenceOrigin = Literal["manual", "mercado_publico"]
ExperienceOrigin = Literal["perfil", "capacidad", "evidencia"]

# Antes de esto no hay compras públicas registradas que valga la pena citar; el
# límite solo ataja errores de tipeo como "224" o "20024".
_PRIMER_ANIO_PLAUSIBLE = 1900


def _no_vacio(value: str) -> str:
    if not value or not value.strip():
        raise ValueError("El campo no puede estar vacío.")
    return value.strip()


class CapabilityOption(BaseModel):
    label: str
    polarity: Polarity

    @field_validator("label")
    @classmethod
    def _label_no_vacio(cls, value: str) -> str:
        return _no_vacio(value)


class CapabilityQuestion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    question: str
    target_field: str
    category: str
    kind: CapabilityKind = "capacidad"
    work_type: str | None = None
    options: list[CapabilityOption] = Field(default_factory=list)
    origin: QuestionOrigin = "semilla"
    active: bool = True
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)

    @field_validator("question", "target_field")
    @classmethod
    def _textos_no_vacios(cls, value: str) -> str:
        return _no_vacio(value)

    @field_validator("category")
    @classmethod
    def _categoria_normalizada(cls, value: str) -> str:
        return _no_vacio(value).lower()

    @model_validator(mode="after")
    def _coherencia(self) -> Self:
        if self.kind == "experiencia_proyecto":
            if not self.work_type or not self.work_type.strip():
                raise ValueError(
                    "Una pregunta de experiencia en proyectos debe indicar el tipo de trabajo."
                )
            self.work_type = self.work_type.strip()
        elif self.work_type is not None:
            raise ValueError(
                "Solo las preguntas de experiencia en proyectos llevan tipo de trabajo."
            )

        etiquetas = [option.label for option in self.options]
        if len(etiquetas) != len(set(etiquetas)):
            raise ValueError("Las opciones de una pregunta no pueden repetirse.")
        return self

    def option_for(self, answer: str) -> CapabilityOption | None:
        return next((o for o in self.options if o.label == answer), None)

    def accepts(self, answer: str) -> bool:
        """Con opciones, solo una de ellas; sin opciones, cualquier texto no vacío."""
        if self.options:
            return self.option_for(answer) is not None
        return bool(answer and answer.strip())

    def polarity_of(self, answer: str) -> Polarity | None:
        option = self.option_for(answer)
        return option.polarity if option else None


class CapabilityAnswer(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    supplier_id: UUID
    question_id: UUID
    answer: str | None = None
    answered: bool = False
    omitted: bool = False
    # Licitación cuya exigencia motivó la pregunta, cuando la hay.
    tender_id: UUID | None = None
    # El miembro que respondió: la respuesta es de la empresa, no de quien la dio,
    # pero el panel de fuentes del borrador muestra quién la dio.
    answered_by_user_id: UUID | None = None
    # Vigencia de lo respondido, por ejemplo una certificación que vence.
    valid_until: UtcDateTime | None = None
    generated_at: UtcDateTime = Field(default_factory=utc_now_naive)
    answered_at: UtcDateTime | None = None

    @field_validator("valid_until")
    @classmethod
    def _vigencia_en_utc_naive(cls, value: datetime | None) -> datetime | None:
        """Las fechas se guardan en UTC sin zona (`datetime_utils`).

        Una fecha con zona se convierte desde su offset; una sin zona se asume ya
        en UTC, que es el invariante de lo persistido. La ambigüedad de una fecha
        sin zona que venga del cliente la resuelve la API rechazándola.
        """
        return aware_to_utc_naive(value)

    @model_validator(mode="after")
    def _estado_coherente(self) -> Self:
        if self.answered and self.omitted:
            raise ValueError(
                "Una pregunta no puede estar respondida y omitida a la vez."
            )
        if self.answered:
            if self.answer is None or not self.answer.strip():
                raise ValueError("Una pregunta respondida necesita una respuesta.")
            self.answer = self.answer.strip()
        return self

    def is_current(self, now: datetime | None = None) -> bool:
        """¿Cuenta como dato de la empresa? Respondida y sin vigencia vencida."""
        if not self.answered:
            return False
        if self.valid_until is None:
            return True
        return self.valid_until > (now or utc_now_naive())


class CapabilityEvidence(BaseModel):
    """Un proyecto que respalda la experiencia de una empresa.

    Puede colgar de una respuesta ("Sí, tengo experiencia en obras viales" → este
    proyecto) o existir sola, como una orden de compra importada que no responde
    ninguna pregunta. En los dos casos `work_type` la clasifica: cuando cuelga de
    una respuesta se copia de la pregunta (`evidence_for_answer`), así que la
    evidencia no pierde su clase si la respuesta se borra.
    """

    id: UUID = Field(default_factory=uuid4)
    supplier_id: UUID
    answer_id: UUID | None = None
    work_type: str
    origin: EvidenceOrigin = "manual"
    title: str
    buyer: str | None = None
    year: int
    amount_clp: int | None = Field(default=None, ge=0)
    description: str | None = None
    # Nulo cuando la evidencia viene de una importación y no de una persona.
    created_by_user_id: UUID | None = None
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)

    @field_validator("title", "work_type")
    @classmethod
    def _textos_no_vacios(cls, value: str) -> str:
        return _no_vacio(value)

    @field_validator("year")
    @classmethod
    def _anio_plausible(cls, value: int) -> int:
        if not _PRIMER_ANIO_PLAUSIBLE <= value <= utc_now_naive().year:
            raise ValueError("El año del proyecto no es válido.")
        return value


def evidence_for_answer(
    question: CapabilityQuestion,
    answer: CapabilityAnswer,
    *,
    title: str,
    year: int,
    buyer: str | None = None,
    amount_clp: int | None = None,
    description: str | None = None,
    created_by_user_id: UUID | None = None,
) -> CapabilityEvidence:
    """Evidencia manual que respalda un "Sí" a una pregunta de experiencia en proyectos.

    Un proyecto no respalda un "No" ni una certificación, y la respuesta tiene
    que ser de esta pregunta: de lo contrario el borrador citaría un proyecto
    como prueba de algo que no prueba.
    """
    if (
        question.kind != "experiencia_proyecto"
        or answer.question_id != question.id
        or not answer.answered
        or answer.answer is None
        or question.polarity_of(answer.answer) != "afirmativa"
    ):
        raise EvidenceNeedsAffirmativeProjectAnswer(answer.id)

    # `experiencia_proyecto` garantiza `work_type` (validador de la pregunta).
    assert question.work_type is not None
    return CapabilityEvidence(
        supplier_id=answer.supplier_id,
        answer_id=answer.id,
        work_type=question.work_type,
        title=title,
        year=year,
        buyer=buyer,
        amount_clp=amount_clp,
        description=description,
        created_by_user_id=created_by_user_id,
    )


class ExperienceItem(BaseModel):
    """Un elemento del catálogo de experiencia de una empresa.

    `id` es estable y se compone del origen y una clave: `perfil:certificacion:
    iso-9001`, `capacidad:<id de la pregunta>` o `evidencia:<id>`. Es lo que el
    borrador de postulación guarda para citar la fuente de un párrafo (CA5).
    """

    id: str
    origin: ExperienceOrigin
    kind: str
    title: str
    detail: str
    polarity: Polarity | None = None
    # Solo en las respuestas: quién respondió y qué licitación motivó la pregunta.
    answered_by_user_id: UUID | None = None
    tender_id: UUID | None = None


class ExperienceCatalog(BaseModel):
    """Lo que el sistema sabe que la empresa puede acreditar.

    No se guarda: se compone al leer, juntando el perfil, las respuestas vigentes
    y los proyectos. Copiarlo obligaría a mantenerlo sincronizado.
    """

    items: list[ExperienceItem] = Field(default_factory=list)
    # El último cambio de cualquiera de sus fuentes. Sirve para avisar que un
    # borrador escrito antes quedó desactualizado.
    last_changed_at: UtcDateTime | None = None


def _plegar(text: str) -> str:
    """Minúsculas, sin tildes y con espacios colapsados, para comparar nombres."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", sin_tildes).strip().casefold()


def _solo_rut(text: str) -> str:
    return re.sub(r"[^0-9kK]", "", text).upper()


def question_leaks_supplier_data(question: str, supplier: Supplier) -> bool:
    """¿El enunciado nombra a la empresa? Una pregunta así no puede ir al banco.

    Compara razón social y nombre de fantasía sin tildes ni mayúsculas, y el RUT
    en cualquier formato (con o sin puntos y guion).
    """
    plegada = _plegar(question)
    for nombre in (supplier.legal_name, supplier.trade_name):
        if nombre and _plegar(nombre) and _plegar(nombre) in plegada:
            return True

    rut = _solo_rut(supplier.rut)
    candidatos = re.findall(r"\d[\d.]*-?[\dkK]", question)
    return any(_solo_rut(candidato) == rut for candidato in candidatos)
