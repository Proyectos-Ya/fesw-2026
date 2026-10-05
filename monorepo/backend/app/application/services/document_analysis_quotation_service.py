from abc import ABC, abstractmethod
from dataclasses import dataclass

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
        document_bytes: bytes,
        file_name: str,
        file_type: str,
        tender: Tender,
        supplier: Supplier,
        matching_score: float | None = None,
    ) -> DocumentAnalysisAndQuotationResult:
        """Genera conjuntamente análisis profundo y cotización estimada a partir de un documento y contexto."""
        ...
