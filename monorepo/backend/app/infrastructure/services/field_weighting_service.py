import re
from uuid import UUID

from app.application.services.weighting_service import IWeightingService
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.shared.regions import are_regions_matching


class FieldWeightingService(IWeightingService):
    """
    Implementación del servicio de ponderación híbrida por componentes y campos.
    Combina la afinidad semántica profunda del Reranker (calibrado con Platt Scaling)
    con la presencia y densidad de requerimientos, sectores y palabras clave en el título,
    descripción y partidas de la licitación.
    """

    def __init__(
        self,
        reranker_weight: float = 0.50,
        sector_weight: float = 0.25,
        keyword_weight: float = 0.25,
        region_weight: float = 0.0,
    ) -> None:
        self.reranker_weight = reranker_weight
        self.sector_weight = sector_weight
        self.keyword_weight = keyword_weight
        self.region_weight = region_weight

    def calculate_scores(
        self,
        candidates: list[tuple[Tender, float]],
        supplier: Supplier,
    ) -> list[tuple[UUID, float]]:
        """
        Calcula el score final ponderando el Re-ranking semántico con las coincidencias de campos.
        """
        scored_candidates = []

        for tender, reranker_score in candidates:
            # 1. Puntuación base del Reranker calibrado (50%)
            score = reranker_score * self.reranker_weight

            # 2. Coincidencia de región (si tiene peso asignado).
            # Se exige `supplier.regions` no vacío: `are_regions_matching`
            # devuelve True cuando no hay restricción, y sin esta guarda un
            # proveedor sin regiones configuradas se llevaría el bono siempre.
            if self.region_weight > 0 and supplier.regions:
                if are_regions_matching(tender.region, supplier.regions):
                    score += self.region_weight

            # Texto global de la licitación (título + descripción)
            tender_overview = f"{tender.name} {tender.description or ''}"
            
            # Texto de los ítems/partidas
            items_texts = []
            if tender.items:
                for item in tender.items:
                    items_texts.append(f"{item.name} {item.description or ''}")
            all_tender_text = f"{tender_overview} {' '.join(items_texts)}"

            # 3. Coincidencia de sector / rubro principal (25%)
            sector_matches = 0
            if supplier.sectors:
                for sector in supplier.sectors:
                    sec_clean = sector.strip()
                    if not sec_clean:
                        continue
                    
                    # Intentar coincidencia de frase completa
                    pattern_full = rf"\b{re.escape(sec_clean)}\b"
                    if re.search(pattern_full, all_tender_text, re.IGNORECASE):
                        sector_matches += 1
                        continue
                    
                    # Si no coincide la frase completa, evaluar tokens significativos (len >= 4)
                    tokens = [t for t in re.split(r"\s+", sec_clean) if len(t) >= 4 and t.lower() not in ("para", "sobre", "entre", "desde", "hasta")]
                    for tok in tokens:
                        pattern_tok = rf"\b{re.escape(tok)}\b"
                        if re.search(pattern_tok, tender_overview, re.IGNORECASE):
                            sector_matches += 0.75
                            break

            if sector_matches > 0:
                sector_ratio = min(1.0, sector_matches)
                score += self.sector_weight * sector_ratio

            # 4. Coincidencia de palabras clave / especialidad con bono por densidad (25%)
            matched_keywords = 0
            if supplier.keywords:
                for keyword in supplier.keywords:
                    kw_clean = keyword.strip()
                    if not kw_clean:
                        continue
                    kw_pattern = rf"\b{re.escape(kw_clean)}\b"
                    if re.search(kw_pattern, all_tender_text, re.IGNORECASE):
                        matched_keywords += 1

            if matched_keywords > 0:
                # 1 coincidencia -> 75% del bono; 2 o más coincidencias -> 100% del bono
                keyword_ratio = min(1.0, 0.75 + 0.25 * (matched_keywords - 1))
                score += self.keyword_weight * keyword_ratio

            # Acotar a máximo 1.0 (100%)
            score = min(score, 1.0)
            scored_candidates.append((tender.id, score))

        # Ordenar de mayor a menor puntuación final
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return scored_candidates
