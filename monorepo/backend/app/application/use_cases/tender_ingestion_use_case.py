import uuid
from typing import Any

from app.application.repositories.tender_repository import ITenderRepository
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.tender_ingestion_service import ITenderIngestionService
from app.application.services.text_builder import TextBuilder
from app.domain.entities.tender import utc_now_naive
from app.infrastructure.repositories.tender_model import TenderItemModel, TenderModel
from app.shared.constants import TENDER_STATUS_CODE_BY_ID


class TenderIngestionUseCase:
    # Mapeo de CodigoEstado (int) al código de string usado en Qdrant y constantes.
    # Definido en shared/constants para mantener una sola fuente de verdad con
    # el seeder y el repositorio SQL.
    _STATUS_CODE_MAP: dict[int, str] = TENDER_STATUS_CODE_BY_ID

    def __init__(
        self,
        ingestion_service: ITenderIngestionService,
        repository: ITenderRepository,
        embedding_service: IEmbeddingService,
        tender_vector_repo: ITenderVectorRepository,
    ):
        self.service = ingestion_service
        self.repo = repository
        self.embedding_service = embedding_service
        self.tender_vector_repo = tender_vector_repo
        self.text_builder = TextBuilder()

    async def execute(self, limit: int | None = None) -> dict[str, Any]:
        dtos = await self.service.fetch_public_tenders()

        if limit:
            dtos = dtos[:limit]
            print(
                f"[Ingesta] Modo desarrollo activo. Procesando solo {limit} registros."
            )

        stats: dict[str, Any] = {
            "fetched": len(dtos),
            "saved": 0,
            "skipped": 0,
            "failed": 0,
            "failed_codes": [],
        }

        for dto in dtos:
            try:
                if await self.repo.get_by_code(dto.code):
                    stats["skipped"] += 1
                    continue

                if (
                    not dto.buyer_rut
                    or dto.buyer_rut.strip() == ""
                    or dto.buyer_rut == "Sin RUT"
                ):
                    safe_buyer_rut = f"GENERIC-{dto.code}"
                else:
                    safe_buyer_rut = dto.buyer_rut

                # El id llega como dato desde la API; ya no se deduce del nombre.
                region_id = dto.region_id

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
                    available_amount_clp=dto.available_amount_clp,
                    created_at=now,
                    updated_at=now,
                )

                tender_items = [
                    TenderItemModel(
                        id=uuid.uuid4(),
                        tender_id=tender_id,
                        product_code=str(item.codigo_unspsc)
                        if item.codigo_unspsc
                        else "0",
                        name=item.nombre_producto,
                        description=item.descripcion,
                        quantity=item.cantidad,
                        unit_of_measure=item.unidad_medida,
                    )
                    for item in dto.items
                ]

                text = self.text_builder.build_from_tender(new_tender, tender_items)
                vectors = await self.embedding_service.embed([text])
                status_code = self._STATUS_CODE_MAP.get(dto.status_code, "desconocido")

                # Qdrant antes que SQL, deliberadamente. Las dos escrituras no
                # comparten transacción, así que una puede fallar tras la otra;
                # lo que sí se elige es hacia qué lado queda el desbalance:
                #
                #   fila en SQL sin punto   → invisible para el matching de forma
                #                             permanente (Qdrant es el único punto
                #                             de entrada y get_by_code impide el
                #                             reintento).
                #   punto sin fila en SQL   → rank_tenders (3.3.1) lo elimina en
                #                             cuanto aparece en una búsqueda.
                #
                # Escribiendo primero el vector, el único desbalance posible es
                # el que el sistema ya reconcilia solo.
                await self.tender_vector_repo.upsert(
                    tender_id=tender_id,
                    embedding=vectors[0],
                    payload={
                        "status_code": status_code,
                        "region_id": region_id,
                        "available_amount_clp": dto.available_amount_clp,
                    },
                )

                # Recién acá se abre la transacción SQL. Ambos get_or_create
                # hacen flush, así que dejarlos antes del embedding mantendría
                # los locks tomados durante toda la inferencia del modelo.
                # Son las claves foráneas de new_tender: deben existir al commit.
                await self.repo.get_or_create_buyer(
                    rut=safe_buyer_rut, name=dto.buyer_name, region_id=region_id
                )
                await self.repo.get_or_create_status(status_id=dto.status_code)
                await self.repo.save_complex_tender(new_tender, tender_items)
                stats["saved"] += 1

            except Exception as e:
                # get_or_create_buyer/status hacen flush dentro de la misma
                # transacción: sin rollback quedarían pendientes en la sesión.
                print(
                    f"[Error Ingesta] Falló procesamiento de licitación {dto.code}: {e}"
                )
                await self.repo.rollback()
                stats["failed"] += 1
                stats["failed_codes"].append(dto.code)
                continue

        # Un fallo sistémico (Qdrant caído, cuota agotada) debe distinguirse de
        # una corrida limpia sin licitaciones nuevas: ambas dejaban saved=0.
        status = "partial" if stats["failed"] else "success"
        return {"status": status, "summary": stats}
