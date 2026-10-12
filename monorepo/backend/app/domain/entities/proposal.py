"""Borrador de postulación a una Compra Ágil (HU-20).

Hay un borrador por empresa y licitación. Pasa por dos fases:

1. **Factibilidad:** se cargan las exigencias de las bases y la empresa responde
   las que el catálogo no cubre. Un "No" a una exigencia excluyente pausa el
   borrador hasta que la empresa decida continuar con advertencia o detener
   (CA7, CA8, CA9).
2. **Redacción:** con todo respondido, se genera el contenido (CA1, CA2, CA5).
   Las respuestas se pueden cambiar con el borrador listo: el texto queda como
   estaba hasta que se vuelva a redactar (plan 292, §2.7 B).

```text
FEASIBILITY ──"No" a exigencia excluyente──▶ PAUSED
PAUSED ──continuar con advertencia──▶ FEASIBILITY
PAUSED ──corregir la respuesta a "Sí"──▶ FEASIBILITY
PAUSED ──detener──▶ STOPPED ──reanudar──▶ FEASIBILITY
FEASIBILITY ──sin pendientes + generar──▶ READY ──regenerar──▶ READY
READY ──cambiar una respuesta sin bloquear la redacción──▶ READY
READY ──"No" a exigencia excluyente──▶ PAUSED
```

"Vencido" no es un estado: se calcula al leer con `Tender.esta_cerrada()`, para
que ninguna lectura tenga que escribir.
"""

import re
from dataclasses import dataclass
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
# Campo "Detalle de la cotización" del formulario de Compra Ágil: obligatorio y
# de 255 caracteres como máximo (guía del proveedor de Compra Ágil, paso 2). Es
# lo que se copia desde `offer_description` (plan 292, §2.7 A).
MAX_DETALLE_COTIZACION = 255

# Dos tipos no describen a la empresa y por eso no se preguntan:
# - `condicion`: lo que define la oferta (cantidades, duración, fechas, plazos,
#   especificaciones). Cualquier proveedor que cotiza la acepta; la redacción la
#   usa para describir la oferta.
# - `documento`: un antecedente que se adjunta (cotización, formulario,
#   declaración jurada). Es la lista de documentos necesarios del borrador (CA1).
RequirementKind = Literal[
    "certificacion", "experiencia", "disponibilidad", "condicion", "documento", "otro"
]
KINDS_SIN_PREGUNTA: frozenset[str] = frozenset({"condicion", "documento"})

# La Declaración Jurada de Habilidad se acepta en una ventana de Mercado Público
# al enviar la cotización (guía del proveedor, paso 2): no es un documento que
# se adjunte. Otras declaraciones juradas sí pueden pedirse como adjunto.
_DECLARACION_DE_HABILIDAD = re.compile(
    r"declaraci[oó]n\s+jurada\s+de\s+habilidad", re.IGNORECASE
)


def es_declaracion_de_habilidad(texto: str) -> bool:
    """¿Es la Declaración Jurada de Habilidad, que no va en los documentos?"""
    return _DECLARACION_DE_HABILIDAD.search(texto) is not None


# El perfil genérico (descripción, rubro, años) dice a qué se dedica la empresa,
# pero no prueba una experiencia ni una certificación concreta.
_PERFIL_GENERICO = ("perfil:descripcion", "perfil:sector:", "perfil:anios-experiencia")
_NO_PROBADO_POR_EL_PERFIL_GENERICO: frozenset[str] = frozenset(
    {"experiencia", "certificacion"}
)


def perfil_cubre(kind: str, item_id: str) -> bool:
    """¿Puede el elemento `item_id` del catálogo cubrir una exigencia de tipo `kind`?

    La IA a veces cita la descripción o un rubro como prueba de una experiencia
    específica. Esa cobertura no vale: se pregunta (plan 292, §2.1).

    - descripción, rubro y años: todo menos experiencia y certificación;
    - una certificación del perfil: solo una certificación;
    - una región del perfil: solo disponibilidad (cobertura geográfica);
    - respuestas (`capacidad:`) y proyectos (`evidencia:`): cualquier exigencia.
    """
    if item_id.startswith(_PERFIL_GENERICO):
        return kind not in _NO_PROBADO_POR_EL_PERFIL_GENERICO
    if item_id.startswith("perfil:certificacion:"):
        return kind == "certificacion"
    if item_id.startswith("perfil:region:"):
        return kind == "disponibilidad"
    return True


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
    # Sugerida para fortalecer la oferta: no la piden las bases, pero su respuesta
    # le da a la redacción datos de la empresa. Nunca es excluyente.
    suggested: bool = False


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


class AnalysisDocument(BaseModel):
    """Un adjunto que leyó el análisis de factibilidad.

    `corrupted`: no se pudo leer y la IA no vio su contenido.
    """

    name: str
    corrupted: bool


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


@dataclass(frozen=True)
class TechnicalSectionTemplate:
    key: str
    title: str
    # Qué poner en la sección, igual para toda licitación. La pantalla la
    # muestra bajo el título y el Word junto a los vacíos (plan 292, §2.8).
    guidance: str
    # Opcional: se incluye solo si hay contenido. Las demás siempre van, con un
    # vacío por completar si la IA no tuvo de dónde sacar el texto.
    optional: bool = False


# Plantilla fija del documento técnico, acordada con el equipo (plan 230, §2.6).
# Es lo único del borrador que se exporta a Word: nombre, descripción y
# documentos se copian desde la pestaña del borrador al formulario de la
# Compra Ágil.
TECHNICAL_SECTIONS: tuple[TechnicalSectionTemplate, ...] = (
    TechnicalSectionTemplate(
        "antecedentes",
        "Antecedentes de la empresa",
        "Quién es la empresa y su experiencia relacionada con este servicio.",
    ),
    TechnicalSectionTemplate(
        "comprension",
        "Comprensión del requerimiento",
        "Qué pide el comprador, con las cantidades, lugares y plazos de las bases.",
    ),
    TechnicalSectionTemplate(
        "metodologia",
        "Metodología",
        "Cómo ejecutarás el servicio, paso a paso.",
    ),
    TechnicalSectionTemplate(
        "plan_de_trabajo",
        "Plan de trabajo y plazos",
        "Etapas y plazos, dentro del plazo máximo de las bases.",
    ),
    TechnicalSectionTemplate(
        "equipo",
        "Equipo de trabajo",
        "Cuántas personas participan, su cargo y sus certificaciones.",
    ),
    TechnicalSectionTemplate(
        "otros",
        "Otros requisitos de las bases",
        "Otras exigencias de las bases que la oferta deba responder.",
        optional=True,
    ),
)


class TechnicalSection(BaseModel):
    key: str
    title: str
    paragraphs: list[DraftParagraph] = Field(default_factory=list)
    # `guidance` es la frase fija de la plantilla; `hint`, lo que la IA sugiere
    # agregar para esta licitación. Son `None` en los borradores redactados
    # antes de existir (viajan en el JSONB de `content`).
    guidance: str | None = None
    hint: str | None = None


class TechnicalDocument(BaseModel):
    sections: list[TechnicalSection] = Field(default_factory=list)


class DraftContent(BaseModel):
    """Plantilla fija de Compra Ágil (CA1)."""

    offer_name: DraftSection
    offer_description: DraftSection
    required_documents: DraftSection
    # Solo si las bases lo exigen; con las secciones de `TECHNICAL_SECTIONS`.
    technical_document: TechnicalDocument | None = None
    # Cuándo se redactó. Una respuesta del banco modificada después deja el texto
    # desactualizado. Es `None` en los borradores redactados antes de existir.
    generated_at: UtcDateTime | None = None

    @field_validator("generated_at")
    @classmethod
    def _redactado_en_utc_naive(cls, value: datetime | None) -> datetime | None:
        # Viaja dentro del JSONB y vuelve con zona: se normaliza como el resto.
        return aware_to_utc_naive(value)


class ProposalDraft(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    supplier_id: UUID
    tender_id: UUID
    status: ProposalStatus = "FEASIBILITY"
    requirements: list[Requirement] = Field(default_factory=list)
    # La exigencia cuyo "No" tiene el borrador en pausa.
    paused_requirement_id: str | None = None
    requires_technical_document: bool = False
    # Las bases mencionan un informe o documento técnico sin aclarar si va con
    # la oferta o se entrega al ejecutar el servicio. Nunca a la vez que
    # `requires_technical_document`. `None` en los borradores anteriores.
    technical_document_ambiguous: bool | None = None
    technical_document_reason: str | None = None
    warnings: list[ProposalWarning] = Field(default_factory=list)
    discrepancy_decisions: list[DiscrepancyDecision] = Field(default_factory=list)
    content: DraftContent | None = None
    last_instructions: str | None = None
    # Huella de lo que se usó en el análisis (adjuntos, catálogo y ficha). Al
    # volver a analizar, si no cambió, el borrador se mantiene tal cual.
    analysis_fingerprint: str | None = None
    # Los adjuntos que leyó el análisis y si la ficha menciona bases, TDR o
    # anexos. Con eso la pantalla recomienda subir las bases. Son `None` en los
    # borradores analizados antes de existir estos campos.
    analysis_documents: list[AnalysisDocument] | None = None
    mentions_attachments: bool | None = None
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

    def _estado_actual(self, polarity: Polarity | None) -> RequirementStatus:
        # Sin polaridad: la respuesta ya no está vigente y se vuelve a preguntar.
        return _ESTADO_POR_POLARIDAD[polarity] if polarity else "desconocido"

    def changed_answers(
        self, current: dict[UUID, tuple[Polarity | None, datetime | None]]
    ) -> list[str]:
        """Exigencias cuya respuesta en el banco cambió desde que se usó.

        `current` trae, por pregunta, la polaridad vigente (o `None` si ya no
        hay respuesta vigente) y cuándo se respondió. Cambió si el estado que
        daría hoy no calza con el guardado, o si se respondió después de
        redactar: el texto puede citar lo anterior. No modifica nada.

        En pausa o detenida no avisa: ahí la respuesta se corrige en el aviso
        de discrepancia o al reanudar, y `sync_answers` no aplica.
        """
        if self.status not in ("FEASIBILITY", "READY"):
            return []
        redactado = self.content.generated_at if self.content else None
        cambiadas: list[str] = []
        for requirement in self.requirements:
            question_id = requirement.capability_question_id
            if question_id is None or question_id not in current:
                continue
            polarity, answered_at = current[question_id]
            if self._estado_actual(polarity) != requirement.status or (
                redactado is not None
                and answered_at is not None
                and answered_at > redactado
            ):
                cambiadas.append(requirement.id)
        return cambiadas

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

    def _cambiar_estado(
        self, requirement: Requirement, status: RequirementStatus
    ) -> None:
        requirement.status = status
        # Una respuesta nueva reemplaza la anterior: su decisión y su
        # advertencia dejan de valer. Si vuelve a ser "No", se pregunta otra vez.
        self.discrepancy_decisions = [
            d for d in self.discrepancy_decisions if d.requirement_id != requirement.id
        ]
        self.warnings = [w for w in self.warnings if w.requirement_id != requirement.id]

    def record_answer(self, question_id: UUID, polarity: Polarity) -> None:
        """Aplica la respuesta de la empresa a las exigencias que la esperaban.

        En factibilidad se responde cualquier pregunta. En pausa, solo la de la
        exigencia pausada: así se corrige un "No" (por ejemplo uno de otra
        licitación, si la empresa ya consiguió la certificación) sin detener y
        reanudar. El resto de la cola espera a que se resuelva la discrepancia.

        Con el borrador listo también se responde. Si todavía se puede
        redactar, sigue listo y el texto no cambia: `changed_answers` avisa que
        quedó desactualizado. Un "No" excluyente pausa, como en factibilidad.
        """
        corrige_la_pausa = (
            self.status == "PAUSED" and question_id == self._pregunta_en_pausa()
        )
        if not corrige_la_pausa:
            self._exigir("FEASIBILITY", "READY", accion="responder")
        nuevo_estado = _ESTADO_POR_POLARIDAD[polarity]
        tocadas = [
            r for r in self.requirements if r.capability_question_id == question_id
        ]
        for requirement in tocadas:
            self._cambiar_estado(requirement, nuevo_estado)
        if corrige_la_pausa:
            # Se vuelve a evaluar desde cero: un "No" pausa otra vez en la misma
            # exigencia; un "Sí" puede dejar al descubierto otra sin decidir.
            self.status = "FEASIBILITY"
            self.paused_requirement_id = None
        if self.status == "READY" and not self.can_generate():
            self.status = "FEASIBILITY"
        self._pausar_si_corresponde()
        self._tocar()

    def sync_answers(self, polarities: dict[UUID, Polarity | None]) -> None:
        """Aplica las respuestas vigentes del banco a las exigencias que las usan.

        Sirve cuando la empresa corrigió una respuesta fuera de esta postulación.
        Un "No" excluyente pausa como en la factibilidad; una respuesta vencida
        vuelve a quedar pendiente. El texto redactado se conserva hasta que se
        vuelva a redactar. En pausa o detenida no se aplica: primero se resuelve
        la discrepancia.
        """
        self._exigir("FEASIBILITY", "READY", accion="actualizar las respuestas de")
        for requirement in self.requirements:
            question_id = requirement.capability_question_id
            if question_id is None or question_id not in polarities:
                continue
            nuevo = self._estado_actual(polarities[question_id])
            if nuevo != requirement.status:
                self._cambiar_estado(requirement, nuevo)
        if self.status == "READY" and (
            self.pending_requirements() or self._sin_resolver()
        ):
            self.status = "FEASIBILITY"
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

    def request_technical_document(self) -> None:
        """La empresa pide el documento técnico aunque no se detectó en las bases.

        Si las bases eran ambiguas, deja de serlo (lo decidió la empresa) y el
        motivo conserva la frase citada de las bases. Si ya se exigía, no
        cambia nada: pedirlo dos veces no debe borrar el motivo anterior.
        """
        if self.requires_technical_document:
            return
        if self.technical_document_ambiguous and self.technical_document_reason:
            motivo = f"Lo pidió la empresa. {self.technical_document_reason}"
        else:
            motivo = "Lo pidió la empresa: no se detectó que las bases lo exijan."
        self.requires_technical_document = True
        self.technical_document_ambiguous = False
        self.technical_document_reason = motivo
        self._tocar()

    def mark_ready(self, content: DraftContent, instructions: str | None) -> None:
        """Guarda el contenido redactado o regenerado (CA1, CA4)."""
        if not self.can_generate():
            raise InvalidProposalTransition(self.status, "redactar")
        self.content = content.model_copy(update={"generated_at": utc_now_naive()})
        self.last_instructions = instructions
        self.status = "READY"
        self._tocar()
