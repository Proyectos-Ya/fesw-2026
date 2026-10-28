"""Licitaciones abiertas con dirección de entrega ubicada, por región (HU-22, #314)."""

from app.application.repositories.tender_map_repository import ITenderMapRepository
from app.application.schemas.tender_map_schema import TenderMapResponse
from app.domain.errors.tender_errors import InvalidSearchCriteria
from app.shared.regions import CHILE_REGIONS, normalize_region_name

# El mismo tope absoluto que la búsqueda: más marcadores en una región ya no se
# leen ni agrupados, y el payload por marcador es chico (~250 bytes).
MAP_RESULT_LIMIT = 500


class GetTendersMapUseCase:
    def __init__(self, repo: ITenderMapRepository) -> None:
        self.repo = repo

    async def execute(self, region: str) -> TenderMapResponse:
        """`region` vale con el nombre canónico o con el del wizard ("Metropolitana").

        El perfil de empresa guarda los nombres del wizard y el buscador usa los
        canónicos; el mapa recibe cualquiera de los dos.
        """
        region_id = normalize_region_name(region)
        if region_id is None:
            raise InvalidSearchCriteria(f"Región desconocida: {region!r}.")

        puntos, total = await self.repo.list_open_with_location(
            region_id=region_id, limit=MAP_RESULT_LIMIT
        )
        return TenderMapResponse(
            region=CHILE_REGIONS[region_id],
            items=puntos,
            total=total,
            is_truncated=total > len(puntos),
        )
