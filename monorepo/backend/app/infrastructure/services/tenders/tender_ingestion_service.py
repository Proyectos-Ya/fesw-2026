import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.tender_ingestion_service import ITenderIngestionService
from app.application.use_cases.tender_ingestion_use_case import TenderIngestionUseCase
from app.config import settings
from app.domain.models.tender_ingestion_dto import ItemLicitacionDTO, TenderIngestaDTO
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.repositories.tender_model import TenderMetadataModel
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)
from app.shared.regions import to_region_id


# Implementación del servicio de ingesta de licitaciones
class TenderIngestionService(ITenderIngestionService):
    def __init__(
        self,
        engine: AsyncEngine,
        client: MercadoPublicoClient,
        embedding_service: IEmbeddingService,
        qdrant_client: AsyncQdrantClient | None = None,
        tender_vector_repo: ITenderVectorRepository | None = None,
    ):
        self.engine = engine
        self.client = client
        self.embedding_service = embedding_service
        self.qdrant_client = qdrant_client
        self._tender_vector_repo = tender_vector_repo

    # Obtiene listado de cambios recientes y guarda códigos en tender_metadata si no existen
    async def fetch_tenders_metadata(self) -> None:
        async with AsyncSession(self.engine) as session:
            to_date = datetime.now(UTC)
            from_date = to_date - timedelta(days=1)
            limit = settings.mercadopublico_fetching_limit

            print(
                f"[IngestionService] Consultando licitaciones recientes (límite: {limit})..."
            )
            try:
                items = await self.client.get_tenders(from_date, to_date, limit)
                new_count = 0
                for item in items:
                    code = item.get("codigo")
                    if not code:
                        continue

                    # 1. Filtrar solo licitaciones abiertas / publicadas
                    estado = item.get("estado", {}) or {}
                    id_estado = estado.get("id_estado")
                    codigo_estado = str(estado.get("codigo", "")).lower()
                    glosa_estado = str(estado.get("glosa", "")).lower()
                    ACTIVE_STATUS_IDS = {1, 2, 5, 6}
                    is_active_status = (
                        (id_estado in ACTIVE_STATUS_IDS)
                        or ("publicada" in codigo_estado)
                        or ("publicada" in glosa_estado)
                    )
                    if not is_active_status:
                        continue

                    # 2. Filtrar licitaciones cuya fecha de cierre ya venció
                    fechas = item.get("fechas", {}) or {}
                    fecha_cierre_str = fechas.get("fecha_cierre")
                    if fecha_cierre_str:
                        try:
                            fc_clean = fecha_cierre_str.replace("Z", "+00:00")
                            if " " in fc_clean and "T" not in fc_clean:
                                closing_dt = datetime.strptime(
                                    fc_clean, "%Y-%m-%d %H:%M"
                                )
                            else:
                                closing_dt = datetime.fromisoformat(fc_clean).replace(
                                    tzinfo=None
                                )

                            now_naive = datetime.now(UTC).replace(tzinfo=None)
                            if closing_dt <= now_naive:
                                continue
                        except Exception:
                            pass

                    # 3. Filtrar por región en el listado si TARGET_REGION está configurado
                    if settings.target_region:
                        institucion = item.get("institucion", {}) or {}
                        nombre_region = str(institucion.get("nombre_region", ""))
                        if nombre_region:
                            target_reg = settings.target_region.strip().lower()
                            item_reg = nombre_region.strip().lower()
                            if (
                                target_reg not in item_reg
                                and item_reg not in target_reg
                            ):
                                continue

                    # Comprobar si ya existe en metadata para no duplicar
                    stmt = select(TenderMetadataModel).where(
                        TenderMetadataModel.code == code
                    )
                    existing = (await session.exec(stmt)).first()
                    if not existing:
                        metadata = TenderMetadataModel(
                            id=uuid.uuid4(),
                            code=code,
                            is_processed=False,
                            created_at=datetime.now(UTC).replace(tzinfo=None),
                            updated_at=datetime.now(UTC).replace(tzinfo=None),
                        )
                        session.add(metadata)
                        new_count += 1

                await session.commit()
                print(f"[IngestionService] Metadata sincronizada. Nuevas: {new_count}.")
            except Exception as e:
                print(f"[IngestionService] Error al sincronizar metadatos: {e}")
                await session.rollback()

    # Procesa todas las licitaciones marcadas como is_processed=False
    async def process_unprocessed_tenders(self) -> None:
        async with AsyncSession(self.engine) as session:
            # `is_(False)` y no `not ...`: la comparación tiene que generar
            # SQL, no evaluarse en Python. La sugerencia de ruff (E712) rompe
            # la query en silencio.
            stmt = select(TenderMetadataModel).where(
                col(TenderMetadataModel.is_processed).is_(False)
            )
            unprocessed_list = (await session.exec(stmt)).all()

            if not unprocessed_list:
                return

            print(
                f"[IngestionService] Encontradas {len(unprocessed_list)} licitaciones sin procesar."
            )

            repo = TenderRepository(session)
            if self._tender_vector_repo:
                tender_vector_repo = self._tender_vector_repo
            else:
                tender_vector_repo = QdrantTenderRepository(
                    client=self.qdrant_client,  # type: ignore
                    vector_size=settings.embedding_vector_size,
                )
            use_case = TenderIngestionUseCase(
                repository=repo,
                embedding_service=self.embedding_service,
                tender_vector_repo=tender_vector_repo,
            )

            # Extraemos los datos necesarios antes de iterar para evitar expiración por commits intermedios
            unprocessed_tenders = [(m.id, m.code) for m in unprocessed_list]

            for metadata_id, code in unprocessed_tenders:
                try:
                    print(f"[IngestionService] Ingestando detalles para {code}...")

                    # Descargar JSON crudo desde el cliente de Mercado Público
                    detail_payload = await self.client.get_tender_detail(code)
                    if not detail_payload:
                        print(
                            f"[IngestionService] Detalle de {code} vacío o inválido. Marcando como procesado."
                        )
                        metadata_item = await session.get(
                            TenderMetadataModel, metadata_id
                        )
                        if metadata_item:
                            metadata_item.is_processed = True
                            metadata_item.updated_at = datetime.now(UTC).replace(
                                tzinfo=None
                            )
                            session.add(metadata_item)
                        await session.commit()
                        continue

                    # Convertir a DTO e ingestar en SQL y Vector DB
                    dto = self._parse_to_dto(detail_payload)

                    if settings.target_region:
                        target_reg = settings.target_region.strip().lower()
                        dto_reg = dto.region_name.strip().lower()
                        if target_reg not in dto_reg and dto_reg not in target_reg:
                            metadata_item = await session.get(
                                TenderMetadataModel, metadata_id
                            )
                            if metadata_item:
                                metadata_item.is_processed = True
                                metadata_item.updated_at = datetime.now(UTC).replace(
                                    tzinfo=None
                                )
                                session.add(metadata_item)
                            await session.commit()
                            print(
                                f"[IngestionService] Omitiendo {code}: región '{dto.region_name}' no coincide con TARGET_REGION '{settings.target_region}'."
                            )
                            continue

                    await use_case.execute(dto)

                    # Actualizar metadata a procesado recuperándola de la sesión
                    metadata_item = await session.get(TenderMetadataModel, metadata_id)
                    if metadata_item:
                        metadata_item.is_processed = True
                        metadata_item.updated_at = datetime.now(UTC).replace(
                            tzinfo=None
                        )
                        session.add(metadata_item)

                    await session.commit()
                    print(f"[IngestionService] Licitación {code} procesada con éxito.")

                    # Espaciar llamadas a la API
                    await asyncio.sleep(settings.mercadopublico_detail_delay)

                except asyncio.CancelledError:
                    await session.rollback()
                    raise
                except Exception as e:
                    print(
                        f"[IngestionService] Error al procesar licitación {code}: {e}. Marcando como procesado para continuar."
                    )
                    await session.rollback()
                    try:
                        metadata_item = await session.get(
                            TenderMetadataModel, metadata_id
                        )
                        if metadata_item:
                            metadata_item.is_processed = True
                            metadata_item.updated_at = datetime.now(UTC).replace(
                                tzinfo=None
                            )
                            session.add(metadata_item)
                            await session.commit()
                    except Exception:
                        pass

    # Mapea diccionario a DTO de dominio
    def _parse_to_dto(self, detail: dict) -> TenderIngestaDTO:
        items_dto = []
        raw_products = detail.get("productos_solicitados", []) or []
        for prod in raw_products:
            items_dto.append(
                ItemLicitacionDTO(
                    codigo_unspsc=int(prod.get("codigo_producto", 0))
                    if prod.get("codigo_producto") is not None
                    else None,
                    codigo_categoria=None,
                    categoria=None,
                    nombre_producto=str(prod.get("nombre", "Sin nombre")),
                    descripcion=prod.get("descripcion"),
                    cantidad=float(prod.get("cantidad", 1.0)),
                    unidad_medida=str(prod.get("unidad_medida", "UN")),
                )
            )

        institucion = detail.get("institucion", {}) or {}
        fechas = detail.get("fechas", {}) or {}
        presupuesto = detail.get("presupuesto", {}) or {}
        estado = detail.get("estado", {}) or {}

        def parse_date(date_str) -> datetime:
            if not date_str:
                return datetime.utcnow()
            try:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(
                    tzinfo=None
                )
            except Exception:
                return datetime.utcnow()

        return TenderIngestaDTO(
            CodigoExterno=str(detail.get("codigo")),
            Nombre=str(detail.get("nombre")),
            Descripcion=detail.get("descripcion"),
            CodigoEstado=int(estado.get("id_estado", 5)),
            FechaPublicacion=parse_date(fechas.get("fecha_publicacion")),
            FechaCierre=parse_date(fechas.get("fecha_cierre")),
            RutComprador=str(institucion.get("rut", "Sin RUT")),
            NombreOrganismo=str(institucion.get("organismo_comprador", "Desconocido")),
            UnidadCompra=str(institucion.get("unidad_compra", "Sin Unidad")),
            # La API entrega el id de región como entero. Si faltara, se usa el
            # id de "Desconocida" en vez de atribuirle una región real.
            RegionId=to_region_id(institucion.get("region")),
            RegionUnidad=str(institucion.get("nombre_region", "Sin Región")),
            MontoEstimado=presupuesto.get("monto_disponible_clp"),
            # Las partidas se armaban arriba y no se asignaban, así que toda
            # licitación ingestada entraba sin ítems. No fallaba nada: el campo
            # tiene [] por defecto. El costo era invisible y grande — TextBuilder
            # arma el texto del embedding con nombre + descripción + partidas, y
            # son las partidas las que dicen qué se está pidiendo de verdad.
            items=items_dto,
        )
