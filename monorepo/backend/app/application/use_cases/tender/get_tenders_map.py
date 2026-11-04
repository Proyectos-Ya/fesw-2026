"""Licitaciones abiertas con dirección de entrega ubicada, por región (HU-22, #314)."""

from app.application.repositories.tender_map_repository import ITenderMapRepository
from app.application.schemas.tender_map_schema import TenderMapResponse
from app.domain.errors.tender_errors import InvalidSearchCriteria
from app.shared.regions import CHILE_REGIONS, normalize_region_name

# Cubre la región más cargada del país con holgura, en vez de acotar el payload:
# el criterio 1 pide un marcador por licitación, y un tope que se alcanza esconde
# la mayoría justo donde más licitaciones hay.
#
# El corpus vigente completo es de ~9.000 licitaciones en todo Chile y no crece,
# porque lo que entra iguala a lo que cierra (spike 2.1, medido el 2026-09-10).
# Ni siquiera la Metropolitana se acerca a este tope. Son ~340 bytes por
# marcador: 3.000 son ~0,9 MB de JSON, unos 130 KB ya comprimidos.
#
# El tope se mantiene igual porque la consulta no pagina: sin él, un corpus que
# creciera de forma inesperada se traería entero en una sola respuesta. Cuando
# recorta, `is_truncated` deja que la UI lo diga en vez de mentir con el total.
MAP_RESULT_LIMIT = 3000


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
