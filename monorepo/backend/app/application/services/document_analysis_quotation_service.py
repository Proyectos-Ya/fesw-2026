from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.application.services.tender_assistant_ai_service import DocumentContextDTO
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.quotation import QuotationInput
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender


@dataclass
class DocumentAnalysisAndQuotationResult:
    analysis: DeepAnalysis
    quotation: QuotationInput


class IDocumentAnalysisAndQuotationService(ABC):
    @abstractmethod
    async def analyze_and_quote(
        self,
        documents: list[DocumentContextDTO],
        tender: Tender,
        supplier: Supplier,
        matching_score: float | None = None,
    ) -> DocumentAnalysisAndQuotationResult:
        """Genera en una sola llamada el análisis profundo y la cotización estimada.

        `documents` son los anexos de la licitación (plan 233). Los tipos que el
        servicio no sabe mandar se omiten.
        """
        ...
