from datetime import UTC, datetime

import httpx

from app.application.services.mercado_publico_service import IMercadoPublicoService
from app.domain.entities.tender import Tender as Licitacion, TenderItem as ItemLicitacion

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
        from uuid import uuid4
        comprador = item.get("Comprador") or {}
        items_raw = (item.get("Items") or {}).get("Listado") or []
        tender_id = uuid4()
        now = datetime.now(UTC).replace(tzinfo=None)
        return Licitacion(
            id=tender_id,
            code=item["CodigoExterno"],
            name=item["Nombre"],
            description=item.get("Descripcion"),
            status_id=1,
            published_at=now,
            closing_at=MercadoPublicoClient._parse_fecha(item["FechaCierre"]).replace(tzinfo=None),
            last_change_at=now,
            buyer_rut=comprador.get("RutUnidad") or "12.345.678-9",
            buyer_unit=comprador.get("NombreOrganismo") or "",
            items=[
                ItemLicitacion(
                    id=uuid4(),
                    tender_id=tender_id,
                    product_code=str(i.get("CodigoProducto") or ""),
                    name=i["NombreProducto"],
                    description=i.get("Descripcion"),
                    quantity=float(i.get("Cantidad") or 1.0),
                    unit_of_measure=str(i.get("UnidadMedida") or "UN"),
                )
                for i in items_raw
            ],
        )

    @staticmethod
    def _parse_fecha(fecha_str: str) -> datetime:
        return datetime.strptime(fecha_str, _DATE_FORMAT).replace(tzinfo=UTC)
