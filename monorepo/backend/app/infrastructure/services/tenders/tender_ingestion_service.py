import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from qdrant_client import AsyncQdrantClient
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
    CuotaAgotadaError,
    ErrorTransitorioMercadoPublico,
    MercadoPublicoClient,
)
from app.shared.constants import ACTIVE_TENDER_STATUSES
from app.shared.datetime_utils import to_utc_naive, utc_now_naive
from app.shared.regions import to_region_id

# Implementación del servicio de ingesta de licitaciones
# Filas por sentencia al insertar metadata. Postgres topa en 65.535 parámetros
# por sentencia y cada fila lleva 5 columnas, así que el techo real ronda las
# 13.000. Mil deja margen de sobra y mantiene las transacciones cortas.
LOTE_METADATA = 1000

# Licitaciones por lote de procesamiento. El SELECT antes no tenía LIMIT y la
# sesión seguía abierta mientras se procesaba la cola entera: con 5.000
# pendientes son horas con una conexión del pooler de Supabase ocupada. Con un
# lote acotado, cada pasada dura minutos y el llamador decide si sigue.
LOTE_PROCESAMIENTO = 200

# Intentos antes de dar una licitación por perdida. Descartarla al primer error
# —lo que se hacía antes— la perdía para siempre, porque el listado deduplica
# por código y no la vuelve a ofrecer. No rendirse nunca tampoco sirve: una
# licitación que la API devuelve rota bloquearía la cola.
MAX_INTENTOS_INGESTA = 3


@dataclass
class ResultadoProceso:
    """Qué pasó en una pasada, para que el llamador decida si sigue.

    `cuota_agotada` es la que importa: sin ella, el bucle de rondas de la carga
    inicial volvía a intentar y gastaba los cuatro reintentos del cliente contra
    una cuota que ya no existe.
    """

    procesadas: int = 0
    fallidas: int = 0
    cuota_agotada: bool = False


def _lotes(elementos: list, tamano: int):
    """Trocea una lista en sublistas de a lo más `tamano`."""
    for inicio in range(0, len(elementos), tamano):
        yield elementos[inicio : inicio + tamano]


def _cierre_ya_vencio(fecha_cierre: str | None, ahora_utc_naive: datetime) -> bool:
    """Si el plazo de cotización ya pasó. Ante la duda, False: se conserva.

    La conversión de zona la hace `to_utc_naive` y no un `replace(tzinfo=None)`:
    `replace` **descarta** el offset en vez de convertir, así que un cierre con
    `-04:00` —la hora de Chile— se comparaba contra UTC con cuatro horas de
    error, y descartaba licitaciones que seguían abiertas. Con sufijo `Z` el
    error no se notaba, porque ahí la hora de pared ya es UTC.

    Descartar una licitación viva es peor que ingerir una ya cerrada: lo segundo
    lo corrige el barrido de vencidas, lo primero no lo nota nadie.
    """
    if not fecha_cierre:
        return False

    texto = fecha_cierre.replace("Z", "+00:00")
    try:
        if " " in texto and "T" not in texto:
            # Formato sin zona que la API no documenta, pero que se vio en la
            # práctica. `to_utc_naive` lo interpreta en hora de Chile.
            parseada = datetime.strptime(texto, "%Y-%m-%d %H:%M")
        else:
            parseada = datetime.fromisoformat(texto)
    except (ValueError, TypeError):
        return False

    cierre = to_utc_naive(parseada)
    return cierre is not None and cierre <= ahora_utc_naive


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
    async def fetch_tenders_metadata(
        self,
        *,
        dias: int | None = None,
        por_publicacion: bool = False,
        estado: str | None = None,
        limite: int | None = None,
    ) -> int:
        async with AsyncSession(self.engine) as session:
            to_date = datetime.now(UTC)
            from_date = to_date - timedelta(days=dias or 1)
            limit = limite or settings.mercadopublico_fetching_limit

            print(
                f"[IngestionService] Consultando licitaciones recientes (límite: {limit})..."
            )
            try:
                items = await self.client.get_tenders(
                    from_date,
                    to_date,
                    limit,
                    por_publicacion=por_publicacion,
                    estado=estado,
                )
                codigos_candidatos: list[str] = []
                for item in items:
                    code = item.get("codigo")
                    if not code:
                        continue

                    # 1. Filtrar solo licitaciones abiertas / publicadas.
                    # Por `estado.codigo`, que es el enum documentado de la API,
                    # y no por `id_estado`, cuya numeración la guía no publica.
                    # `estado_item` y no `estado`: ese nombre es el parámetro
                    # de la función —el filtro que se le manda a la API— y
                    # reasignarlo acá lo convertía en un dict a mitad de camino.
                    # Hoy no rompe nada porque `get_tenders` ya se llamó, pero
                    # cualquier uso posterior del filtro fallaría.
                    estado_item = item.get("estado", {}) or {}
                    codigo_estado = (
                        str(estado_item.get("codigo") or "").strip().lower()
                    )
                    if codigo_estado not in ACTIVE_TENDER_STATUSES:
                        continue

                    # 2. Filtrar licitaciones cuya fecha de cierre ya venció
                    fechas = item.get("fechas", {}) or {}
                    if _cierre_ya_vencio(fechas.get("fecha_cierre"), utc_now_naive()):
                        continue

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

                    codigos_candidatos.append(code)

                new_count = await self._insertar_metadata(session, codigos_candidatos)

                await session.commit()
                print(f"[IngestionService] Metadata sincronizada. Nuevas: {new_count}.")
                return new_count
            except Exception as e:
                print(f"[IngestionService] Error al sincronizar metadatos: {e}")
                await session.rollback()
                return 0

    # Procesa todas las licitaciones marcadas como is_processed=False
    async def _insertar_metadata(
        self, session: AsyncSession, codigos: list[str]
    ) -> int:
        """Inserta los códigos que falten y devuelve cuántos eran nuevos.

        Sin consultar antes: `tender_metadata.code` tiene índice único, así que
        el duplicado lo resuelve Postgres con ON CONFLICT. La versión anterior
        hacía un SELECT por licitación, y desde Chile contra Supabase en US East
        cada viaje son ~133 ms: con 2.000 licitaciones, 4,4 minutos de espera
        que no calculan nada.
        """
        if not codigos:
            return 0

        ahora = utc_now_naive()
        nuevos = 0
        for lote in _lotes(codigos, LOTE_METADATA):
            filas = [
                {
                    "id": uuid.uuid4(),
                    "code": code,
                    "is_processed": False,
                    "created_at": ahora,
                    "updated_at": ahora,
                }
                for code in lote
            ]
            stmt = (
                pg_insert(TenderMetadataModel)
                .values(filas)
                .on_conflict_do_nothing(index_elements=["code"])
                .returning(TenderMetadataModel.code)
            )
            resultado = await session.exec(stmt)  # type: ignore[call-overload]
            nuevos += len(resultado.all())
        return nuevos

    async def ultima_sincronizacion(self) -> datetime | None:
        """Fecha del registro de metadata más reciente, en UTC con zona.

        La columna se guarda naive —en UTC, por convención del proyecto—, así que
        se le pone la zona antes de devolverla: quien compara contra `ahora` está
        en hora de Chile, y restar un naive de un aware lanza TypeError.
        """
        async with AsyncSession(self.engine) as session:
            stmt = select(func.max(col(TenderMetadataModel.created_at)))
            ultima = (await session.exec(stmt)).one_or_none()  # type: ignore[call-overload]
            if ultima is None:
                return None
            return ultima.replace(tzinfo=UTC)

    async def process_unprocessed_tenders(
        self, limite: int | None = None
    ) -> ResultadoProceso:
        """Baja el detalle de un lote de pendientes y lo ingesta.

        Procesa a lo más `limite` licitaciones y vuelve, en vez de vaciar la cola
        entera: así la sesión de lectura dura lo que tarda un SELECT y el
        llamador decide si sigue. El bucle de rondas de la carga inicial es quien
        insiste hasta terminar.

        Las descargas van en paralelo hasta
        `MERCADOPUBLICO_DETAIL_CONCURRENCY`. Más del 85% del tiempo por
        licitación es red y una pausa artificial, así que solaparlas es lo único
        que mueve la aguja; el modelo de embeddings es el 6%.
        """
        pendientes = await self._pendientes(limite or LOTE_PROCESAMIENTO)
        if not pendientes:
            return ResultadoProceso()

        print(
            f"[IngestionService] Procesando {len(pendientes)} licitaciones "
            "pendientes..."
        )

        resultado = ResultadoProceso()
        # Un Event y no un `break`: con las tareas ya lanzadas no hay bucle del
        # que salir, y lo que hace falta es que las que aún no empezaron no
        # gasten sus cuatro reintentos contra una cuota que ya no existe.
        cuota_agotada = asyncio.Event()
        semaforo = asyncio.Semaphore(
            max(1, settings.mercadopublico_detail_concurrency)
        )

        await asyncio.gather(
            *(
                self._procesar_una(
                    metadata_id, code, semaforo, cuota_agotada, resultado
                )
                for metadata_id, code in pendientes
            )
        )

        resultado.cuota_agotada = cuota_agotada.is_set()
        if resultado.cuota_agotada:
            print(
                "[IngestionService] Cuota agotada. Quedan licitaciones "
                "pendientes para el próximo intento."
            )
        return resultado

    async def _pendientes(self, limite: int) -> list[tuple[uuid.UUID, str]]:
        """Los siguientes códigos por procesar, los que menos han fallado primero.

        El orden importa desde que hay LIMIT: sin él, una licitación que la API
        devuelve rota se quedaría al frente de todos los lotes y congelaría el
        avance de la cola entera.
        """
        async with AsyncSession(self.engine) as session:
            # `is_(False)` y no `not ...`: la comparación tiene que generar
            # SQL, no evaluarse en Python. La sugerencia de ruff (E712) rompe
            # la query en silencio.
            stmt = (
                select(TenderMetadataModel)
                .where(col(TenderMetadataModel.is_processed).is_(False))
                .order_by(
                    col(TenderMetadataModel.attempts).asc(),
                    col(TenderMetadataModel.created_at).asc(),
                )
                .limit(limite)
            )
            filas = (await session.exec(stmt)).all()
            # Se extraen los datos antes de cerrar la sesión: los objetos
            # quedarían expirados y cada atributo dispararía otra consulta.
            return [(m.id, m.code) for m in filas]

    async def _procesar_una(
        self,
        metadata_id: uuid.UUID,
        code: str,
        semaforo: asyncio.Semaphore,
        cuota_agotada: asyncio.Event,
        resultado: ResultadoProceso,
    ) -> None:
        """Una licitación de punta a punta, con su propia sesión.

        La sesión es por licitación y no compartida a propósito: `AsyncSession`
        no es segura entre tareas concurrentes, y de paso ninguna transacción
        vive más que la licitación que la abrió.
        """
        async with semaforo:
            if cuota_agotada.is_set():
                return

            async with AsyncSession(self.engine) as session:
                try:
                    print(f"[IngestionService] Ingestando detalles para {code}...")
                    detail_payload = await self.client.get_tender_detail(code)

                    if not detail_payload:
                        # Vacío significa que no hay nada que traer: reintentar
                        # daría lo mismo. Distinto de un error transitorio, que
                        # sí deja la licitación en la cola.
                        print(
                            f"[IngestionService] Detalle de {code} vacío o "
                            "inválido. Marcando como procesado."
                        )
                        await self._marcar_procesada(session, metadata_id)
                        resultado.procesadas += 1
                        return

                    dto = self._parse_to_dto(detail_payload)

                    if self._fuera_de_region(dto.region_name):
                        print(
                            f"[IngestionService] Omitiendo {code}: región "
                            f"'{dto.region_name}' no coincide con TARGET_REGION "
                            f"'{settings.target_region}'."
                        )
                        await self._marcar_procesada(session, metadata_id)
                        resultado.procesadas += 1
                        return

                    await self._construir_use_case(session).execute(dto)
                    await self._marcar_procesada(session, metadata_id)
                    resultado.procesadas += 1
                    print(f"[IngestionService] Licitación {code} procesada con éxito.")

                except asyncio.CancelledError:
                    await session.rollback()
                    raise
                except CuotaAgotadaError as e:
                    # No se cuenta como intento: la cuota no es culpa de esta
                    # licitación y penalizarla la mandaría al final de la cola
                    # sin motivo.
                    await session.rollback()
                    print(f"[IngestionService] {e}")
                    cuota_agotada.set()
                except ErrorTransitorioMercadoPublico as e:
                    # La licitación existe y el próximo intento la recupera.
                    # Nunca se marca procesada: eso la perdería para siempre.
                    await self._registrar_fallo(
                        session, metadata_id, str(e), rendirse=False
                    )
                    resultado.fallidas += 1
                except Exception as e:
                    print(
                        f"[IngestionService] Error al procesar licitación {code}: {e}"
                    )
                    await self._registrar_fallo(
                        session, metadata_id, str(e), rendirse=True
                    )
                    resultado.fallidas += 1

            # Piso de espera por licitación, dentro del semáforo: espacia las
            # peticiones de cada slot sin volver a serializar el conjunto.
            if settings.mercadopublico_detail_delay:
                await asyncio.sleep(settings.mercadopublico_detail_delay)

    def _fuera_de_region(self, region_name: str) -> bool:
        """Si TARGET_REGION está puesto y esta licitación no es de ahí."""
        if not settings.target_region:
            return False
        objetivo = settings.target_region.strip().lower()
        propia = region_name.strip().lower()
        return objetivo not in propia and propia not in objetivo

    def _construir_use_case(self, session: AsyncSession) -> TenderIngestionUseCase:
        if self._tender_vector_repo:
            tender_vector_repo = self._tender_vector_repo
        else:
            tender_vector_repo = QdrantTenderRepository(
                client=self.qdrant_client,  # type: ignore[arg-type]
                vector_size=settings.embedding_vector_size,
            )
        return TenderIngestionUseCase(
            repository=TenderRepository(session),
            embedding_service=self.embedding_service,
            tender_vector_repo=tender_vector_repo,
            enable_comuna_generic_heuristic=settings.enable_comuna_generic_heuristic,
        )

    async def _marcar_procesada(
        self, session: AsyncSession, metadata_id: uuid.UUID
    ) -> None:
        metadata_item = await session.get(TenderMetadataModel, metadata_id)
        if metadata_item:
            metadata_item.is_processed = True
            metadata_item.updated_at = utc_now_naive()
            session.add(metadata_item)
        await session.commit()

    async def _registrar_fallo(
        self,
        session: AsyncSession,
        metadata_id: uuid.UUID,
        motivo: str,
        *,
        rendirse: bool,
    ) -> None:
        """Anota el intento fallido y decide si se abandona la licitación.

        Antes cualquier excepción marcaba `is_processed=True` "para no bloquear
        la cola". Como el listado deduplica por código, eso la perdía para
        siempre: un error de parseo por un campo que la API cambió se llevaba la
        corrida entera sin dejar rastro.

        Con `rendirse=False` la licitación vuelve a la cola indefinidamente —el
        dato existe, fue la red la que falló—, pero cada fallo la manda más
        atrás en el orden, así que no acapara los lotes.
        """
        await session.rollback()
        try:
            metadata_item = await session.get(TenderMetadataModel, metadata_id)
            if not metadata_item:
                return
            metadata_item.attempts += 1
            metadata_item.last_error = motivo[:500]
            metadata_item.updated_at = utc_now_naive()
            if rendirse and metadata_item.attempts >= MAX_INTENTOS_INGESTA:
                print(
                    f"[IngestionService] {metadata_item.code} falló "
                    f"{metadata_item.attempts} veces. Se abandona."
                )
                metadata_item.is_processed = True
            session.add(metadata_item)
            await session.commit()
        except Exception as e:
            print(f"[IngestionService] No se pudo registrar el fallo: {e}")
            await session.rollback()

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
                return datetime.now(UTC).replace(tzinfo=None)
            try:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(
                    tzinfo=None
                )
            except Exception:
                return datetime.now(UTC).replace(tzinfo=None)

        return TenderIngestaDTO(
            CodigoExterno=str(detail.get("codigo")),
            Nombre=str(detail.get("nombre")),
            Descripcion=detail.get("descripcion"),
            # El id se conserva para el FK de tender_status; el estado real
            # lo decide EstadoCodigo. El 0 marca "no vino" sin fingir un estado.
            CodigoEstado=int(estado.get("id_estado") or 0),
            EstadoCodigo=estado.get("codigo"),
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
