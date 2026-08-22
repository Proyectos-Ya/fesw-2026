import asyncio
from datetime import datetime
from typing import Any, cast

import httpx

from app.application.services.tender_ingestion_service import ITenderIngestionService
from app.config import settings
from app.domain.models.tender_ingestion_dto import ItemLicitacionDTO, TenderIngestaDTO
from app.shared.constants import CHILE_REGIONS, UNKNOWN_REGION_ID
from app.shared.datetime_utils import CHILE_TZ


def _to_region_id(raw: object) -> int:
    """Normaliza `institucion.region` a un id de región conocido.

    Un valor ausente, no numérico o fuera del rango de las 16 regiones cae en
    `UNKNOWN_REGION_ID`: es preferible que el caso se vea a que la licitación
    quede archivada bajo una región real que no le corresponde.
    """
    try:
        region_id = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return UNKNOWN_REGION_ID
    return region_id if region_id in CHILE_REGIONS else UNKNOWN_REGION_ID


class MercadoPublicoClient(ITenderIngestionService):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api2.mercadopublico.cl/v2/compra-agil"

    async def fetch_public_tenders(self) -> list[TenderIngestaDTO]:
        headers = {"ticket": self.api_key}

        params = {
            "ttl_cambio_ms": 86400000,
            "tamano_pagina": 50 if not settings.is_dev else 10,
        }

        tenders_mapped: list[TenderIngestaDTO] = []

        async with httpx.AsyncClient() as client:
            try:
                print(
                    f"[API MP] Solicitando listado de cambios recientes a {self.base_url}..."
                )
                response = await client.get(
                    self.base_url, headers=headers, params=params, timeout=20.0
                )

                # Si nos pasamos la cuota
                if response.status_code == 429:
                    print(
                        "[API MP] Cuota diaria agotada (Error 429). Deteniendo ingesta."
                    )
                    return tenders_mapped

                response.raise_for_status()

                # Desarmamos la respuesta estructurada de ChileCompra V2
                envelope = cast(dict[str, Any], response.json())
                payload = cast(dict[str, Any], envelope.get("payload", {}))
                raw_tenders = cast(list[dict[str, Any]], payload.get("items", []))

                print(
                    f"[API MP] Se detectaron {len(raw_tenders)} procesos en la ventana. Descargando detalles relacionales..."
                )

                if settings.is_dev:
                    tenders_to_process = raw_tenders[:5]
                else:
                    tenders_to_process = raw_tenders

                # Con el modo dev = True, obtenemos solo las primeras 5 licitaciones para evitar el limite.
                for basic_tender in tenders_to_process:
                    codigo = basic_tender.get("codigo")
                    if not codigo:
                        continue

                    detail_url = f"{self.base_url}/{codigo}"
                    try:
                        detail_resp = await client.get(
                            detail_url, headers=headers, timeout=15.0
                        )
                        detail_resp.raise_for_status()

                        detail_envelope = cast(dict[str, Any], detail_resp.json())
                        tender_detail = cast(
                            dict[str, Any], detail_envelope.get("payload", {})
                        )

                        if not tender_detail:
                            continue

                        items_dto: list[ItemLicitacionDTO] = []
                        raw_products = cast(
                            list[dict[str, Any]],
                            tender_detail.get("productos_solicitados", []),
                        )

                        for prod in raw_products:
                            items_dto.append(
                                ItemLicitacionDTO(
                                    codigo_unspsc=int(prod.get("codigo_producto", 0))
                                    if prod.get("codigo_producto") is not None
                                    else None,
                                    codigo_categoria=None,
                                    categoria=None,
                                    nombre_producto=str(
                                        prod.get("nombre", "Sin nombre")
                                    ),
                                    descripcion=prod.get("descripcion"),
                                    cantidad=float(prod.get("cantidad", 1.0)),
                                    unidad_medida=str(prod.get("unidad_medida", "UN")),
                                )
                            )

                        institucion = cast(
                            dict[str, Any], tender_detail.get("institucion", {})
                        )
                        fechas = cast(dict[str, Any], tender_detail.get("fechas", {}))
                        presupuesto = cast(
                            dict[str, Any], tender_detail.get("presupuesto", {})
                        )
                        estado = cast(dict[str, Any], tender_detail.get("estado", {}))

                        tender_dto = TenderIngestaDTO(
                            CodigoExterno=str(tender_detail.get("codigo")),
                            Nombre=str(tender_detail.get("nombre")),
                            Descripcion=tender_detail.get("descripcion"),
                            CodigoEstado=int(estado.get("id_estado", 5)),
                            FechaPublicacion=fechas.get("fecha_publicacion")
                            or datetime.now(CHILE_TZ),
                            FechaCierre=fechas.get("fecha_cierre")
                            or datetime.now(CHILE_TZ),
                            RutComprador=str(institucion.get("rut", "Sin RUT")),
                            NombreOrganismo=str(
                                institucion.get("organismo_comprador", "Desconocido")
                            ),
                            UnidadCompra=str(
                                institucion.get("unidad_compra", "Sin Unidad")
                            ),
                            # La API entrega el id de región como entero. Si
                            # faltara, se usa el id de "Desconocida" en vez de
                            # atribuirle una región real a la licitación.
                            RegionId=_to_region_id(institucion.get("region")),
                            RegionUnidad=str(
                                institucion.get("nombre_region", "Sin Región")
                            ),
                            MontoEstimado=presupuesto.get("monto_disponible_clp"),
                        )
                        tender_dto.items = items_dto
                        tenders_mapped.append(tender_dto)

                        await asyncio.sleep(0.2)

                    except Exception as detail_err:
                        print(
                            f"[API MP] Saltando detalle de {codigo} por error: {detail_err}"
                        )
                        continue

                return tenders_mapped

            except httpx.HTTPStatusError as http_err:
                print(
                    f"[HTTP Error MP] Error en endpoint: {http_err.response.status_code}"
                )
                return tenders_mapped
            except Exception as e:
                print(f"[Error MP] Falla inesperada en cliente HTTP: {e}")
                return tenders_mapped
