from datetime import UTC, datetime

import httpx

from app.application.services.mercado_publico_service import IMercadoPublicoService
from app.domain.entities.licitacion import ItemLicitacion, Licitacion

_DATE_FORMAT = "%d-%m-%Y %H:%M:%S"
_BASE_URL = (
    "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
)


class MercadoPublicoClient(IMercadoPublicoService):

    def __init__(self, api_key: str, http_client: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self._http_client = http_client

    async def fetch_licitaciones(
        self,
        estado: str,
        limit: int,
        offset: int,
    ) -> list[Licitacion]:
        page = (offset // limit) + 1 if limit > 0 else 1
        response = await self._http_client.get(
            _BASE_URL,
            params={
                "ticket": self._api_key,
                "estado": estado,
                "cantidad": limit,
                "pagina": page,
            },
        )
        response.raise_for_status()
        data = response.json()
        return [
            self._map_to_entity(item)
            for item in (data.get("Listado") or [])
        ]

    @staticmethod
    def _map_to_entity(item: dict) -> Licitacion:
        comprador = item.get("Comprador") or {}
        items_raw = (item.get("Items") or {}).get("Listado") or []
        return Licitacion(
            codigo_externo=item["CodigoExterno"],
            nombre=item["Nombre"],
            descripcion=item.get("Descripcion"),
            organismo_nombre=comprador.get("NombreOrganismo") or "",
            monto_estimado=item.get("MontoEstimado"),
            fecha_cierre=MercadoPublicoClient._parse_fecha(item["FechaCierre"]),
            region=comprador.get("RegionUnidad") or "",
            estado=item.get("EstadoCodigo") or "",
            items=[
                ItemLicitacion(
                    nombre=i["NombreProducto"],
                    descripcion=i.get("Descripcion"),
                )
                for i in items_raw
            ],
        )

    @staticmethod
    def _parse_fecha(fecha_str: str) -> datetime:
        return datetime.strptime(fecha_str, _DATE_FORMAT).replace(tzinfo=UTC)
