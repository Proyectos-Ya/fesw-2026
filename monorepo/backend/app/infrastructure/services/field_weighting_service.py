from uuid import UUID

from app.application.services.weighting_service import IWeightingService
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender


class FieldWeightingService(IWeightingService):
    """
    Implementación del servicio de ponderación manual de campos.
    """

    def __init__(
        self,
        reranker_weight: float = 0.5,
        region_weight: float = 0.2,
        sector_weight: float = 0.2,
        keyword_weight: float = 0.1,
    ) -> None:
        self.reranker_weight = reranker_weight
        self.region_weight = region_weight
        self.sector_weight = sector_weight
        self.keyword_weight = keyword_weight

    def calculate_scores(
        self,
        candidates: list[tuple[Tender, float]],
        supplier: Supplier,
    ) -> list[tuple[UUID, float]]:
        """
        Pondera la puntuación del reranker con coincidencias precisas de metadatos.
        """
        scored_candidates = []

        for tender, reranker_score in candidates:
            # 1. Puntuación base del Reranker
            score = reranker_score * self.reranker_weight

            # 2. Coincidencia de región (province de la licitación con regions del proveedor)
            region_matched = False
            if supplier.regions and tender.province:
                prov_lower = tender.province.strip().lower()
                for region in supplier.regions:
                    if region.strip().lower() in prov_lower or prov_lower in region.strip().lower():
                        region_matched = True
                        break

            if region_matched:
                score += self.region_weight

            # 3. Coincidencia de sector (sectors del proveedor con nombre/descripción de la licitación)
            sector_matched = False
            tender_text = (tender.name + " " + (tender.description or "")).lower()
            if supplier.sectors:
                for sector in supplier.sectors:
                    if sector.strip().lower() in tender_text:
                        sector_matched = True
                        break

            if sector_matched:
                score += self.sector_weight

            # 4. Coincidencia de palabras clave (keywords del proveedor con items de la licitación)
            keyword_matched = False
            if supplier.keywords and tender.items:
                # Comparamos cada palabra clave contra cada item
                for keyword in supplier.keywords:
                    kw_lower = keyword.strip().lower()
                    for item in tender.items:
                        item_text = (item.name + " " + (item.description or "")).lower()
                        if kw_lower in item_text:
                            keyword_matched = True
                            break
                    if keyword_matched:
                        break

            if keyword_matched:
                score += self.keyword_weight

            scored_candidates.append((tender.id, score))

        # Ordenamos de mayor a menor puntuación final
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return scored_candidates
