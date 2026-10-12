from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.capability import (
    CapabilityAnswer,
    CapabilityEvidence,
    CapabilityQuestion,
)


class ICapabilityQuestionRepository(ABC):
    """Banco de preguntas compartido entre empresas."""

    @abstractmethod
    async def get(self, question_id: UUID) -> CapabilityQuestion | None: ...

    @abstractmethod
    async def get_by_key(
        self, category: str, target_field: str
    ) -> CapabilityQuestion | None: ...

    @abstractmethod
    async def list_active(self, categories: set[str]) -> list[CapabilityQuestion]:
        """Preguntas activas de esas categorías, en orden estable."""

    @abstractmethod
    async def list_by_ids(self, question_ids: list[UUID]) -> list[CapabilityQuestion]:
        """Incluye las inactivas: una respuesta vieja sigue siendo experiencia."""

    @abstractmethod
    async def add(self, question: CapabilityQuestion) -> CapabilityQuestion:
        """Persiste y confirma. Un duplicado de categoría y campo lanza
        `DuplicateCapabilityQuestion` con la pregunta existente."""


class ICapabilityAnswerRepository(ABC):
    """Respuestas de una empresa, a lo sumo una por pregunta."""

    @abstractmethod
    async def get(
        self, supplier_id: UUID, question_id: UUID
    ) -> CapabilityAnswer | None: ...

    @abstractmethod
    async def list_by_supplier(self, supplier_id: UUID) -> list[CapabilityAnswer]: ...

    @abstractmethod
    async def save(self, answer: CapabilityAnswer) -> CapabilityAnswer:
        """Crea o reemplaza la fila de esa empresa y pregunta, y confirma."""


class ICapabilityEvidenceRepository(ABC):
    """Proyectos que respaldan la experiencia de una empresa."""

    @abstractmethod
    async def add(self, evidence: CapabilityEvidence) -> CapabilityEvidence:
        """Persiste y confirma."""

    @abstractmethod
    async def list_by_supplier(self, supplier_id: UUID) -> list[CapabilityEvidence]:
        """Todas las evidencias de la empresa, de cualquier origen, en orden estable."""
