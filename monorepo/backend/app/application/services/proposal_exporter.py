from abc import ABC, abstractmethod

from app.domain.entities.proposal import ProposalDraft
from app.domain.entities.tender import Tender


class IProposalExporter(ABC):
    """Convierte un borrador redactado en un archivo descargable (CA3)."""

    @abstractmethod
    def to_docx(self, draft: ProposalDraft, tender: Tender) -> bytes:
        """Word con la estructura del borrador y los puntos a revisar destacados."""
