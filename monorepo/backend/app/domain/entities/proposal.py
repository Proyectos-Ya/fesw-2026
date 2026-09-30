"""Borrador de postulación a una Compra Ágil (HU-20).

Hay un borrador por empresa y licitación. Pasa por dos fases:

1. **Factibilidad:** se cargan las exigencias de las bases y la empresa responde
   las que el catálogo no cubre. Un "No" a una exigencia excluyente pausa el
   borrador hasta que la empresa decida continuar con advertencia o detener
   (CA7, CA8, CA9).
2. **Redacción:** con todo respondido, se genera el contenido (CA1, CA2, CA5).

```text
FEASIBILITY ──"No" a exigencia excluyente──▶ PAUSED
PAUSED ──continuar con advertencia──▶ FEASIBILITY
PAUSED ──corregir la respuesta a "Sí"──▶ FEASIBILITY
PAUSED ──detener──▶ STOPPED ──reanudar──▶ FEASIBILITY
FEASIBILITY ──sin pendientes + generar──▶ READY ──regenerar──▶ READY
```

"Vencido" no es un estado: se calcula al leer con `Tender.esta_cerrada()`, para
que ninguna lectura tenga que escribir.
"""

import re
from datetime import datetime
from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from app.domain.entities.capability import Polarity
from app.domain.errors.proposal_errors import InvalidProposalTransition
from app.shared.datetime_utils import (
    UtcDateTime,
    aware_to_utc_naive,
    utc_now_naive,
)

ProposalStatus = Literal["FEASIBILITY", "PAUSED", "STOPPED", "READY"]
RequirementKind = Literal["certificacion", "experiencia", "disponibilidad", "otro"]
# `parcial` sale de una respuesta neutra ("En proceso de inscripción"): no es un
# "No", así que no pausa, pero tampoco es un "Sí" que el borrador pueda afirmar.
RequirementStatus = Literal["cumple", "no_cumple", "parcial", "desconocido"]
DecisionAction = Literal["continue", "stop"]

_ESTADO_POR_POLARIDAD: dict[Polarity, RequirementStatus] = {
    "afirmativa": "cumple",
    "negativa": "no_cumple",
    "neutra": "parcial",
}


class Requirement(BaseModel):
    """Una exigencia de las bases de la licitación."""

    # Estable dentro del borrador: la decisión y la advertencia apuntan a él.
    id: str
    text: str
    kind: RequirementKind
    # Excluyente: si no se cumple, la oferta queda fuera. Es de la licitación, no
    # de la capacidad: la misma certificación puede ser excluyente acá y deseable
    # en otra Compra Ágil.
    mandatory: bool
    # Dónde está en las bases: "Descripción", "Ítem 2", el nombre de un adjunto.
    origin: str
    status: RequirementStatus = "desconocido"
    # El elemento del `ExperienceCatalog` que la cubre, si la cubre.
    catalog_item_id: str | None = None
    # La pregunta del banco que la empresa tiene que responder, si hace falta una.
    capability_question_id: UUID | None = None


class DiscrepancyDecision(BaseModel):
    """Lo que la empresa decidió ante un "No" a una exigencia excluyente."""

    requirement_id: str
    capability_question_id: UUID | None = None
    action: DecisionAction
    user_id: UUID
    decided_at: UtcDateTime = Field(default_factory=utc_now_naive)

    @field_validator("decided_at")
    @classmethod
    def _en_utc_naive(cls, value: datetime) -> datetime:
        # Vuelve del JSONB con sufijo "Z"; lo persistido es UTC sin zona.
        return aware_to_utc_naive(value) or value


class ProposalWarning(BaseModel):
    """Advertencia que el borrador incluye por haber continuado (CA8)."""

    requirement_id: str
    text: str


_MARCA_VACIO = re.compile(r"\[\[\s*insertar\s*:\s*(.*?)\s*\]\]", re.IGNORECASE)
_VACIO_SIN_NOMBRE = "valor faltante"


def render_placeholders(text: str) -> tuple[str, list[str]]:
    """Convierte las marcas `[[INSERTAR: X]]` de la IA en texto visible (CA2).

    Devuelve el texto con cada marca reemplazada por "(Por favor, inserte aquí el
    valor X)" y la lista de los X, en orden. Es determinístico: la IA solo marca
    dónde falta un dato; cómo se le muestra al usuario lo decide el dominio.
    """
    vacios: list[str] = []

    def _reemplazar(coincidencia: re.Match[str]) -> str:
        nombre = coincidencia.group(1).strip()
        if not nombre:
            vacios.append(_VACIO_SIN_NOMBRE)
            return "(Por favor, inserte aquí el valor faltante)"
        vacios.append(nombre)
        return f"(Por favor, inserte aquí el valor {nombre})"

    return _MARCA_VACIO.sub(_reemplazar, text), vacios


class DraftSource(BaseModel):
    """Fuente citada por un párrafo: un elemento del `ExperienceCatalog` (CA5)."""

    id: str
    label: str


class DraftParagraph(BaseModel):
    text: str
    sources: list[DraftSource] = Field(default_factory=list)
    placeholders: list[str] = Field(default_factory=list)

    @classmethod
    def from_ai_text(cls, text: str, sources: list[DraftSource]) -> Self:
        visible, vacios = render_placeholders(text)
        return cls(text=visible, sources=sources, placeholders=vacios)


class DraftSection(BaseModel):
    paragraphs: list[DraftParagraph] = Field(default_factory=list)


class DraftContent(BaseModel):
    """Plantilla fija de Compra Ágil (CA1)."""

    offer_name: DraftSection
    offer_description: DraftSection
    required_documents: DraftSection
    # Solo si las bases lo exigen.
    technical_document: DraftSection | None = None


class ProposalDraft(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    supplier_id: UUID
    tender_id: UUID
    status: ProposalStatus = "FEASIBILITY"
    requirements: list[Requirement] = Field(default_factory=list)
    # La exigencia cuyo "No" tiene el borrador en pausa.
    paused_requirement_id: str | None = None
    requires_technical_document: bool = False
    technical_document_reason: str | None = None
    warnings: list[ProposalWarning] = Field(default_factory=list)
    discrepancy_decisions: list[DiscrepancyDecision] = Field(default_factory=list)
    content: DraftContent | None = None
    last_instructions: str | None = None
    created_by_user_id: UUID | None = None
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)

    # --- consultas -----------------------------------------------------------

    def pending_requirements(self) -> list[Requirement]:
        return [r for r in self.requirements if r.status == "desconocido"]

    def _ultima_decision(self, requirement_id: str) -> DiscrepancyDecision | None:
        return next(
            (
                d
                for d in reversed(self.discrepancy_decisions)
                if d.requirement_id == requirement_id
            ),
            None,
        )

    def _sin_resolver(self) -> list[Requirement]:
        """Excluyentes en "No" que la empresa no decidió pasar por alto."""
        return [
            r
            for r in self.requirements
            if r.mandatory
            and r.status == "no_cumple"
            and (
                (decision := self._ultima_decision(r.id)) is None
                or decision.action != "continue"
            )
        ]

    def can_generate(self) -> bool:
        """¿Se puede redactar? La "pausa" de la generación del CA7."""
        return (
            self.status in ("FEASIBILITY", "READY")
            and not self.pending_requirements()
            and not self._sin_resolver()
        )

    # --- transiciones --------------------------------------------------------

    def _exigir(self, *estados: ProposalStatus, accion: str) -> None:
        if self.status not in estados:
            raise InvalidProposalTransition(self.status, accion)

    def _tocar(self) -> None:
        self.updated_at = utc_now_naive()

    def _pausar_si_corresponde(self) -> None:
        """Pausa en la primera excluyente en "No" que aún no tiene decisión.

        Una que se decidió detener no vuelve a pausar: tras reanudar, la empresa
        corrige la respuesta o la vuelve a responder "No", y eso sí pausa.
        """
        for requirement in self.requirements:
            if (
                requirement.mandatory
                and requirement.status == "no_cumple"
                and self._ultima_decision(requirement.id) is None
            ):
                self.status = "PAUSED"
                self.paused_requirement_id = requirement.id
                return

    def load_requirements(self, requirements: list[Requirement]) -> None:
        """Carga las exigencias que dejó el análisis de factibilidad."""
        self._exigir("FEASIBILITY", accion="cargar exigencias en")
        self.requirements = requirements
        self._pausar_si_corresponde()
        self._tocar()

    def _pregunta_en_pausa(self) -> UUID | None:
        pausada = next(
            (r for r in self.requirements if r.id == self.paused_requirement_id),
            None,
        )
        return pausada.capability_question_id if pausada else None

    def record_answer(self, question_id: UUID, polarity: Polarity) -> None:
        """Aplica la respuesta de la empresa a las exigencias que la esperaban.

        En factibilidad se responde cualquier pregunta. En pausa, solo la de la
        exigencia pausada: así se corrige un "No" (por ejemplo uno de otra
        licitación, si la empresa ya consiguió la certificación) sin detener y
        reanudar. El resto de la cola espera a que se resuelva la discrepancia.
        """
        corrige_la_pausa = (
            self.status == "PAUSED" and question_id == self._pregunta_en_pausa()
        )
        if not corrige_la_pausa:
            self._exigir("FEASIBILITY", accion="responder")
        nuevo_estado = _ESTADO_POR_POLARIDAD[polarity]
        tocadas = [
            r for r in self.requirements if r.capability_question_id == question_id
        ]
        for requirement in tocadas:
            requirement.status = nuevo_estado
            # Una respuesta nueva reemplaza la anterior: su decisión y su
            # advertencia dejan de valer. Si vuelve a ser "No", se pregunta otra vez.
            self.discrepancy_decisions = [
                d
                for d in self.discrepancy_decisions
                if d.requirement_id != requirement.id
            ]
            self.warnings = [
                w for w in self.warnings if w.requirement_id != requirement.id
            ]
        if corrige_la_pausa:
            # Se vuelve a evaluar desde cero: un "No" pausa otra vez en la misma
            # exigencia; un "Sí" puede dejar al descubierto otra sin decidir.
            self.status = "FEASIBILITY"
            self.paused_requirement_id = None
        self._pausar_si_corresponde()
        self._tocar()

    def decide(self, action: DecisionAction, user_id: UUID) -> None:
        """Continuar con advertencia (CA8) o detener (CA9) ante la discrepancia."""
        self._exigir("PAUSED", accion="decidir sobre")
        requirement = next(
            r for r in self.requirements if r.id == self.paused_requirement_id
        )
        self.discrepancy_decisions.append(
            DiscrepancyDecision(
                requirement_id=requirement.id,
                capability_question_id=requirement.capability_question_id,
                action=action,
                user_id=user_id,
            )
        )
        self.paused_requirement_id = None
        if action == "stop":
            self.status = "STOPPED"
        else:
            self.warnings.append(
                ProposalWarning(
                    requirement_id=requirement.id,
                    text=(
                        f"Las bases exigen: {requirement.text} "
                        "La empresa declaró no cumplirlo."
                    ),
                )
            )
            self.status = "FEASIBILITY"
            self._pausar_si_corresponde()
        self._tocar()

    def resume(self) -> None:
        """Vuelve a factibilidad para poder cambiar la respuesta (CA9)."""
        self._exigir("STOPPED", accion="reanudar")
        self.status = "FEASIBILITY"
        self._tocar()

    def mark_ready(self, content: DraftContent, instructions: str | None) -> None:
        """Guarda el contenido redactado o regenerado (CA1, CA4)."""
        if not self.can_generate():
            raise InvalidProposalTransition(self.status, "redactar")
        self.content = content
        self.last_instructions = instructions
        self.status = "READY"
        self._tocar()
