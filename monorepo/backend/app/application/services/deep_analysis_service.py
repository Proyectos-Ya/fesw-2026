from abc import ABC, abstractmethod
from typing import Optional
from app.domain.entities.tender import Tender
from app.domain.entities.supplier import Supplier
from app.domain.entities.deep_analysis import DeepAnalysis


class IDeepAnalysisService(ABC):

    @abstractmethod
    async def analyze_compatibility(
        self,
        tender: Tender,
        supplier: Supplier,
        matching_score: float,
        prompt_instruction: Optional[str] = None
    ) -> DeepAnalysis:
        """Genera el análisis profundo de compatibilidad entre un proveedor y una licitación."""
        ...
