from abc import ABC, abstractmethod

from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender


class IDeepAnalysisService(ABC):
    @abstractmethod
    async def analyze_compatibility(
        self,
        tender: Tender,
        supplier: Supplier,
        matching_score: float,
        prompt_instruction: str | None = None,
    ) -> DeepAnalysis:
        """Genera el análisis profundo de compatibilidad entre un proveedor y una licitación."""
        ...
