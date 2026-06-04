import httpx
from typing import List, Dict, Any, cast
from datetime import datetime, timedelta
from monorepo.backend.app.application.repositories.tenders.tender_ingestion_service import TenderIngestionService
from monorepo.backend.app.domain.models.tender_ingestion_dto import TenderIngestaDTO, ItemLicitacionDTO

class MercadoPublicoClient(TenderIngestionService):
    # Cliente para interactuar con la API de mercado publico
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"

    async def fetch_public_tenders(self) -> List[TenderIngestaDTO]:
        ayer = datetime.now() - timedelta(days=1)
        fecha_consulta = ayer.strftime("%d%m%Y")
        
        params = {
            "fecha": fecha_consulta,
            "ticket": self.api_key
        }

        tenders_mapped: List[TenderIngestaDTO] = []

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self.base_url, params=params, timeout=20.0)
                response.raise_for_status()
                
                raw_data = cast(Dict[str, Any], response.json())
                raw_tenders = cast(List[Dict[str, Any]], raw_data.get("Listado", []))

                for tender_item in raw_tenders:

                    items_dto: List[ItemLicitacionDTO] = []
                    raw_items = tender_item.get("Items")

                    if isinstance(raw_items, dict) and "Listado" in raw_items:
                        # SOLUCIÓN LINEA 46/48: Casteamos la lista interna de items
                        raw_items_list = cast(List[Dict[str, Any]], raw_items["Listado"])
                        
                        for safe_item in raw_items_list:
                            items_dto.append(
                                ItemLicitacionDTO(
                                    codigo_unspsc=int(safe_item.get("CodigoProducto", 0)) if safe_item.get("CodigoProducto") is not None else None,
                                    codigo_categoria=str(safe_item.get("CodigoCategoria", "")),
                                    categoria=str(safe_item.get("Categoria", "")),
                                    nombre_producto=str(safe_item.get("Producto", "Sin nombre")),
                                    descripcion=str(safe_item.get("Especificacion")) if safe_item.get("Especificacion") is not None else None,
                                    cantidad=float(safe_item.get("Cantidad", 1.0)),
                                    unidad_medida=str(safe_item.get("UnidadMedida", "UN"))
                                )
                            )

                    tender_dto = TenderIngestaDTO(**tender_item)
                    tender_dto.items = items_dto
                    
                    tenders_mapped.append(tender_dto)

                return tenders_mapped
            
            except httpx.HTTPStatusError as http_err:
                print(f"[HTTP Error] Error en Mercado Público API: {http_err.response.status_code}")
                return tenders_mapped
            except Exception as e:
                print(f"[Error] Error inesperado en el mapeo de la ingesta: {e}")
                return tenders_mapped