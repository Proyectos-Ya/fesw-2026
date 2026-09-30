from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    # Solo para el tipo: la entidad importa este módulo para lanzar sus errores.
    from app.domain.entities.capability import CapabilityQuestion


class CapabilityQuestionNotFound(Exception):
    def __init__(self, question_id: UUID):
        super().__init__(f"No existe la pregunta {question_id} en el banco.")
        self.question_id = question_id


class InvalidCapabilityAnswer(Exception):
    """La respuesta no es una de las opciones de la pregunta."""

    def __init__(self, question_id: UUID, answer: str):
        super().__init__(
            "La respuesta no corresponde a ninguna de las opciones de la pregunta."
        )
        self.question_id = question_id
        self.answer = answer


class DuplicateCapabilityQuestion(Exception):
    """Ya hay una pregunta para esa categoría y campo. Trae la existente para reusarla."""

    def __init__(self, existing: "CapabilityQuestion"):
        super().__init__(
            f"Ya existe una pregunta para {existing.category}/{existing.target_field}."
        )
        self.existing = existing


class QuestionLeaksSupplierData(Exception):
    """El enunciado nombra a una empresa y el banco lo verían todas las demás."""

    def __init__(self) -> None:
        super().__init__(
            "La pregunta menciona datos de una empresa concreta y no puede compartirse."
        )


class EvidenceNeedsAffirmativeProjectAnswer(Exception):
    """Un proyecto solo respalda un "Sí" a una pregunta de experiencia en proyectos."""

    def __init__(self, answer_id: UUID):
        super().__init__(
            "Solo se puede agregar un proyecto a una respuesta afirmativa de "
            "experiencia en proyectos."
        )
        self.answer_id = answer_id
