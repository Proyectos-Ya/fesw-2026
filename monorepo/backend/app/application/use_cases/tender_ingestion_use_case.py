import uuid
from typing import Dict, Any, Optional

# Interfaces de la capa de aplicación
from app.application.services.tender_ingestion_service import ITenderIngestionService
from app.application.repositories.tender_repository import ITenderRepository
from app.infrastructure.repositories.tender_model import TenderModel, TenderItemModel
from app.domain.entities.tender import utc_now_naive

class TenderIngestionUseCase:
    REGION_MAP = {
        "Región de Tarapacá": 1, "Tarapacá": 1,
        "Región de Antofagasta": 2, "Antofagasta": 2,
        "Región de Atacama": 3, "Atacama": 3,
        "Región de Coquimbo": 4, "Coquimbo": 4,
        "Región de Valparaíso": 5, "Valparaíso": 5, "Valparaiso": 5,
        "Región del Libertador Gral. Bernardo O’Higgins": 6, "Región del Libertador General Bernardo O'Higgins": 6, "O'Higgins": 6, "O’Higgins": 6,
        "Región del Maule": 7, "Maule": 7,
        "Región del Biobío": 8, "Región del Bio bío": 8, "Biobío": 8, "Bio-Bio": 8,
        "Región de la Araucanía": 9, "Región de La Araucanía": 9, "Araucanía": 9, "Araucania": 9,
        "Región de Los Lagos": 10, "Los Lagos": 10,
        "Región de Aysén del Gral. Carlos Ibáñez del Campo": 11, "Región de Aysén del General Carlos Ibáñez del Campo": 11, "Aysén": 11, "Aysen": 11,
        "Región de Magallanes y de la Antártica Chilena": 12, "Magallanes y Antártica": 12, "Magallanes": 12,
        "Región Metropolitana de Santiago": 13, "Metropolitana": 13, "Región Metropolitana": 13,
        "Región de Los Ríos": 14, "Región de Los Rios": 14, "Los Ríos": 14, "Los Rios": 14,
        "Región de Arica y Parinacota": 15, "Arica y Parinacota": 15,
        "Región de Ñuble": 16, "Ñuble": 16, "Nuble": 16
    }
    def __init__(
        self, 
        ingestion_service: ITenderIngestionService, 
        repository: ITenderRepository
    ):
        self.service = ingestion_service
        self.repo = repository

    async def execute(self, limit: Optional[int] = None) -> Dict[str, Any]:
        dtos = await self.service.fetch_public_tenders()
        
        if limit:
            dtos = dtos[:limit]
            print(f"[Ingesta] Modo desarrollo activo. Procesando solo {limit} registros.")

        stats = {"fetched": len(dtos), "saved": 0, "skipped": 0}

        for dto in dtos:
            try:
                if await self.repo.get_by_code(dto.code):
                    stats["skipped"] += 1
                    continue

                if not dto.buyer_rut or dto.buyer_rut.strip() == "" or dto.buyer_rut == "Sin RUT":
                    safe_buyer_rut = f"GENERIC-{dto.code}"
                else:
                    safe_buyer_rut = dto.buyer_rut

                region_id = self.REGION_MAP.get(dto.region_name, 7)
                await self.repo.get_or_create_buyer(
                    rut=safe_buyer_rut,
                    name=dto.buyer_name,
                    region_id=region_id
                )

                await self.repo.get_or_create_status(status_id=dto.status_code)

                tender_id = uuid.uuid4()
                now = utc_now_naive()

                new_tender = TenderModel(
                    id=tender_id,
                    code=dto.code,
                    name=dto.name,
                    description=dto.description,
                    status_id=dto.status_code,
                    published_at=dto.published_at,
                    closing_at=dto.closing_at,
                    last_change_at=now,
                    buyer_rut=safe_buyer_rut,
                    buyer_unit=dto.buyer_unit,
                    province=None, 
                    available_amount_clp=dto.available_amount_clp,
                    created_at=now,
                    updated_at=now
                )

                tender_items = [
                    TenderItemModel(
                        id=uuid.uuid4(),
                        tender_id=tender_id,
                        product_code=str(item.codigo_unspsc) if item.codigo_unspsc else "0",
                        name=item.nombre_producto,
                        description=item.descripcion,
                        quantity=item.cantidad,
                        unit_of_measure=item.unidad_medida
                    ) for item in dto.items
                ]

                await self.repo.save_complex_tender(new_tender, tender_items)
                stats["saved"] += 1

            except Exception as e:
                print(f"[Error Ingesta] Falló procesamiento de licitación {dto.code}: {e}")
                await self.repo.rollback()
                continue

        return {
            "status": "success",
            "summary": stats
        }