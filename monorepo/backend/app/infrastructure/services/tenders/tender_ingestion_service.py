import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from qdrant_client import AsyncQdrantClient
from sqlalchemy import case, func, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.lexical_tender_repository import (
    ILexicalTenderRepository,
)
from app.application.repositories.tender_item_vector_repository import (
    ITenderItemVectorRepository,
)
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.tender_ingestion_queue import ITenderIngestionQueue
from app.application.services.tender_ingestion_service import (
    ITenderIngestionService,
    ModoCola,
)
from app.application.use_cases.tender_ingestion_use_case import TenderIngestionUseCase
from app.config import settings
from app.domain.models.cambio_estado import (
    CambioDeEstado,
    Intencion,
    PunteroDeCambio,
    ResultadoPunteros,
)
from app.domain.models.tender_ingestion_dto import (
    DocumentoOficialDTO,
    ItemLicitacionDTO,
    TenderIngestaDTO,
)
from app.infrastructure.repositories.qdrant_lexical_tender_repository import (
    QdrantLexicalTenderRepository,
)
from app.infrastructure.repositories.qdrant_tender_item_vector_repository import (
    QdrantTenderItemVectorRepository,
)
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.repositories.sql_tender_attachment_repository import (
    SqlTenderAttachmentRepository,
)
from app.infrastructure.repositories.tender_model import (
    IngestionRunModel,
    TenderMetadataModel,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.infrastructure.services.tenders.documentos_mp import (
    documentos_desde_payload,
    documentos_por_codigo,
)
from app.infrastructure.services.tenders.listado_cambios import cambio_desde_item
from app.infrastructure.services.tenders.llamados import leer_llamado
from app.infrastructure.services.tenders.mercado_publico_client import (
    CuotaAgotadaError,
    ErrorTransitorioMercadoPublico,
    MercadoPublicoClient,
)
from app.shared.constants import ACTIVE_TENDER_STATUSES
from app.shared.datetime_utils import fecha_mp_a_utc, leer_fecha_mp, utc_now_naive
from app.shared.ingestion_window import calcular_ventana
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

# Reintentos nocturnos antes de dar una licitación por perdida (plan 305). Medido
# el 2026-10-12: 240 compras con 13 a 21 intentos que daban 504 siempre, también
# en la página oficial. Cinco noches separan una falla del día de una que no se
# va a arreglar.
MAX_REINTENTOS_NOCTURNOS = 5

# Errores transitorios seguidos que cortan la pasada. Con la API caída, cada
# licitación que se pide igual gasta sus intentos y su cuota. Diez seguidos ya no
# son una licitación rota sino el gateway.
UMBRAL_CORTACIRCUITO = 10


@dataclass
class ResultadoListado:
    """Qué dejó la fase de listado, y si alcanzó a recorrer la ventana entera.

    `completo` decide si el cursor avanza. Devolver solo el número de nuevas no
    alcanzaba: cero significa tanto "no había nada" como "falló", y con un cron
    diario confundir las dos cosas deja huecos permanentes.
    """

    nuevas: int = 0
    listadas: int = 0
    completo: bool = False
    # La lista oficial de anexos de cada listada, por código. Se aplica al final
    # de la corrida, cuando las nuevas ya existen en `tender` (clave foránea), y
    # no cuesta peticiones: sale del mismo listado.
    documentos: dict[str, list[DocumentoOficialDTO]] = field(default_factory=dict)


@dataclass
class ListadoCambios:
    """Lo que devolvió el listado de cambios, ya traducido.

    `listadas` cuenta los ítems crudos, incluidos los ilegibles: es lo que se
    compara contra el tope de la corrida para saber si quedaron sin mirar.
    """

    cambios: list[CambioDeEstado]
    listadas: int
    ilegibles: int
    completo: bool


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
    # El cortacircuito saltó: la API devolvió errores transitorios seguidos.
    api_caida: bool = False
    # El cron de estados vio un cambio posterior al pedido del detalle: no se
    # escribió y la fila quedó pendiente para la corrida siguiente.
    desactualizadas: int = 0


def _en_utc_naive(momento: datetime) -> datetime:
    """Un instante del sistema, listo para persistir.

    No es `to_utc_naive`: ese conversor es para las fechas de Mercado Público y
    supone que un naive viene en hora de Chile. La ventana la calcula
    `utc_now_naive()`, así que un naive acá **ya está en UTC** y convertirlo lo
    corría 3-4 h hacia el futuro.
    """
    if momento.tzinfo is None:
        return momento
    return momento.astimezone(UTC).replace(tzinfo=None)


def _describir(error: Exception) -> str:
    """Motivo legible para `tender_metadata.last_error`.

    Con el tipo delante: un timeout de red tiene `str(e) == ""`, y la segunda
    corrida en `dev test` dejó 46 filas con el error vacío.
    """
    mensaje = str(error)
    nombre = type(error).__name__
    return f"{nombre}: {mensaje}" if mensaje else nombre


def _lotes(elementos: list, tamano: int):
    """Trocea una lista en sublistas de a lo más `tamano`."""
    for inicio in range(0, len(elementos), tamano):
        yield elementos[inicio : inicio + tamano]


def _cierre_ya_vencio(fecha_cierre: str | None, ahora_utc_naive: datetime) -> bool:
    """Si el plazo de cotización ya pasó. Ante la duda, False: se conserva.

    La lectura la hace `fecha_mp_a_utc`, el parser compartido con el cron de
    estados: toda fecha de Mercado Público es hora de Chile, aunque venga con
    "Z" (verificado el 2026-09-28). Antes se tomaba la Z como UTC, lo que habría
    descartado con 3-4 h de error licitaciones que seguían abiertas.

    Descartar una licitación viva es peor que ingerir una ya cerrada: lo segundo
    lo corrige el barrido de vencidas, lo primero no lo nota nadie.
    """
    cierre = fecha_mp_a_utc(fecha_cierre)
    return cierre is not None and cierre <= ahora_utc_naive


class _Cortacircuito:
    """Cuenta errores transitorios seguidos entre las tareas de una pasada."""

    def __init__(self) -> None:
        self.seguidos = 0
        self.abierto = asyncio.Event()

    def fallo(self) -> None:
        self.seguidos += 1
        if self.seguidos >= UMBRAL_CORTACIRCUITO:
            self.abierto.set()

    def exito(self) -> None:
        self.seguidos = 0


def condiciones_cola(modo: ModoCola, antes_de: datetime | None = None) -> list:
    """Qué filas de la cola toma un modo. La comparten el SELECT y el conteo.

    Si el conteo de `vaciar_cola` no filtrara igual que el SELECT, la cola nunca
    se vería vacía y las rondas seguirían sin nada que hacer.
    """
    condiciones = [
        # `is_(False)` y no `not ...`: la comparación tiene que generar SQL, no
        # evaluarse en Python. La sugerencia de ruff (E712) rompe la query.
        col(TenderMetadataModel.is_processed).is_(False),
        col(TenderMetadataModel.discarded_at).is_(None),
    ]
    if modo is ModoCola.NUEVAS:
        condiciones.append(col(TenderMetadataModel.attempts) == 0)
    elif modo is ModoCola.REINTENTOS:
        condiciones.append(col(TenderMetadataModel.attempts) >= 1)
        if antes_de is not None:
            condiciones.append(col(TenderMetadataModel.updated_at) < antes_de)
    return condiciones


def _orden_cola(modo: ModoCola) -> list:
    if modo is ModoCola.NUEVAS:
        # Primero lo que baja la latencia de entrada: lo que no tenemos.
        nueva_primero = case(
            (col(TenderMetadataModel.pending_reason) == "nueva", 0), else_=1
        )
        return [nueva_primero, col(TenderMetadataModel.created_at).asc()]
    if modo is ModoCola.REINTENTOS:
        return [
            col(TenderMetadataModel.night_retries).asc(),
            col(TenderMetadataModel.updated_at).asc(),
        ]
    return [
        col(TenderMetadataModel.attempts).asc(),
        col(TenderMetadataModel.created_at).asc(),
    ]


# Margen al comparar `fecha_ultimo_cambio` con la última bajada del detalle. La
# hora de la API viene en hora de Chile y se convierte, y el cambio pudo no
# alcanzar a salir en un detalle pedido segundos después. Mejor una bajada de más
# que un cambio sin ver.
MARGEN_CAMBIO = timedelta(minutes=5)

# Lo que entra a cada sentencia del puntero, como columnas de una tabla.
_VALORES = """
    unnest(
        CAST(:ids AS uuid[]),
        CAST(:codes AS varchar[]),
        CAST(:estados AS varchar[]),
        CAST(:cambios AS timestamp[])
    ) AS v(id, code, estado, cambio)
"""

# Si los datos de la API traen algo que no estaba: estado distinto o fecha más
# nueva. Sin esto, cada pasada reescribiría filas idénticas.
_API_CAMBIO = """
    tm.api_status_code IS DISTINCT FROM EXCLUDED.api_status_code
    OR EXCLUDED.api_changed_at > COALESCE(tm.api_changed_at, CAST('-infinity' AS timestamp))
"""

_API_SET = """
    api_status_code = EXCLUDED.api_status_code,
    api_changed_at = GREATEST(tm.api_changed_at, EXCLUDED.api_changed_at)
"""

# Cuándo una conocida que ya está en la cola tiene que volver a bajarse.
_HAY_QUE_BAJAR = {
    Intencion.ACTUALIZAR_SI_CAMBIO: """
        tm.discarded_at IS NULL
        AND EXCLUDED.api_changed_at IS NOT NULL
        AND EXCLUDED.api_changed_at
            > COALESCE(
                tm.detail_fetched_at - CAST(:margen AS interval),
                CAST('-infinity' AS timestamp)
            )
        AND (tm.is_processed OR tm.pending_reason IS DISTINCT FROM 'actualizar')
    """,
    # Una reapertura se baja siempre. Revive lo que se descartó por inactivo,
    # que justamente dejó de estarlo, pero no lo que falla siempre.
    Intencion.REABIERTA: """
        (tm.discarded_at IS NULL OR tm.discard_reason = 'inactiva_en_listado')
        AND (
            tm.is_processed
            OR tm.discarded_at IS NOT NULL
            OR tm.pending_reason IS DISTINCT FROM 'actualizar'
        )
    """,
}


def _sql_actualizar(intencion: Intencion) -> str:
    bajar = _HAY_QUE_BAJAR[intencion]
    return f"""
        INSERT INTO tender_metadata AS tm (
            id, code, is_processed, attempts, night_retries, pending_reason,
            api_status_code, api_changed_at, created_at, updated_at
        )
        SELECT v.id, v.code, false, 0, 0, 'actualizar', v.estado, v.cambio,
               :ahora, :ahora
          FROM {_VALORES}
        ON CONFLICT (code) DO UPDATE SET
            {_API_SET},
            pending_reason = CASE WHEN {bajar} THEN 'actualizar'
                                  ELSE tm.pending_reason END,
            -- Solo vuelve a 0 si venía procesada: una pendiente que falla
            -- siempre tiene que llegar a la noche, no empezar de nuevo.
            attempts = CASE WHEN ({bajar}) AND tm.is_processed THEN 0
                            ELSE tm.attempts END,
            is_processed = CASE WHEN {bajar} THEN false ELSE tm.is_processed END,
            discard_reason = CASE WHEN {bajar} THEN NULL ELSE tm.discard_reason END,
            discarded_at = CASE WHEN {bajar} THEN NULL ELSE tm.discarded_at END,
            updated_at = CASE WHEN {bajar} THEN :ahora ELSE tm.updated_at END
        WHERE {_API_CAMBIO} OR ({bajar})
        RETURNING tm.updated_at = :ahora
    """


_SQL_PUNTEROS: dict[Intencion, str] = {
    # Solo crea: una fila que ya estaba (procesada, pendiente o terminal) no
    # cambia de estado por aparecer de nuevo en el listado.
    Intencion.NUEVA: f"""
        INSERT INTO tender_metadata AS tm (
            id, code, is_processed, attempts, night_retries, pending_reason,
            api_status_code, api_changed_at, created_at, updated_at
        )
        SELECT v.id, v.code, false, 0, 0, 'nueva', v.estado, v.cambio,
               :ahora, :ahora
          FROM {_VALORES}
        ON CONFLICT (code) DO UPDATE SET {_API_SET}
        WHERE {_API_CAMBIO}
        RETURNING (xmax = 0)
    """,
    Intencion.ACTUALIZAR_SI_CAMBIO: _sql_actualizar(Intencion.ACTUALIZAR_SI_CAMBIO),
    Intencion.REABIERTA: _sql_actualizar(Intencion.REABIERTA),
    # No crea filas: una que no tenemos y ya no está activa no hay que bajarla.
    # La pendiente pasa a terminal sin gastar intentos.
    Intencion.INACTIVA: f"""
        UPDATE tender_metadata AS tm SET
            api_status_code = v.estado,
            api_changed_at = GREATEST(tm.api_changed_at, v.cambio),
            discarded_at = CASE WHEN tm.is_processed = false
                                     AND tm.discarded_at IS NULL
                                THEN :ahora ELSE tm.discarded_at END,
            discard_reason = CASE WHEN tm.is_processed = false
                                       AND tm.discarded_at IS NULL
                                  THEN 'inactiva_en_listado'
                                  ELSE tm.discard_reason END,
            pending_reason = CASE WHEN tm.is_processed = false
                                       AND tm.discarded_at IS NULL
                                  THEN NULL ELSE tm.pending_reason END,
            updated_at = CASE WHEN tm.is_processed = false
                                   AND tm.discarded_at IS NULL
                              THEN :ahora ELSE tm.updated_at END
          FROM {_VALORES}
         WHERE tm.code = v.code
           AND (
               tm.api_status_code IS DISTINCT FROM v.estado
               OR v.cambio > COALESCE(tm.api_changed_at, CAST('-infinity' AS timestamp))
               OR (tm.is_processed = false AND tm.discarded_at IS NULL)
           )
        RETURNING tm.discarded_at = :ahora
    """,
}


class TenderIngestionService(ITenderIngestionService, ITenderIngestionQueue):
    def __init__(
        self,
        engine: AsyncEngine,
        client: MercadoPublicoClient,
        embedding_service: IEmbeddingService,
        qdrant_client: AsyncQdrantClient | None = None,
        tender_vector_repo: ITenderVectorRepository | None = None,
        tender_item_vector_repo: ITenderItemVectorRepository | None = None,
        lexical_tender_repo: ILexicalTenderRepository | None = None,
    ):
        self.engine = engine
        self.client = client
        self.embedding_service = embedding_service
        self.qdrant_client = qdrant_client
        self._tender_vector_repo = tender_vector_repo
        self._tender_item_vector_repo = tender_item_vector_repo
        self._lexical_tender_repo = lexical_tender_repo

    # Obtiene listado de cambios recientes y guarda códigos en tender_metadata si no existen
    async def fetch_tenders_metadata(
        self,
        *,
        dias: int | None = None,
        por_publicacion: bool = False,
        estado: str | None = None,
        limite: int | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> ResultadoListado:
        """Lista la ventana pedida y encola los códigos que falten.

        `desde`/`hasta` mandan sobre `dias` cuando vienen: es como el cron le
        pasa la ventana que salió del cursor. Sin ellos se conserva el
        comportamiento de siempre, una ventana relativa a `ahora`.
        """
        async with AsyncSession(self.engine) as session:
            to_date = hasta or datetime.now(UTC)
            from_date = desde or (to_date - timedelta(days=dias or 1))
            limit = limite or settings.mercadopublico_fetching_limit

            print(
                f"[IngestionService] Consultando licitaciones recientes (límite: {limit})..."
            )
            try:
                listado = await self.client.get_tenders(
                    from_date,
                    to_date,
                    limit,
                    por_publicacion=por_publicacion,
                    estado=estado,
                )
                # De todos los ítems, también de los que se filtran más abajo:
                # si ya tenemos la licitación, igual conviene refrescar su lista.
                documentos = documentos_por_codigo(listado.items)
                codigos_candidatos: list[str] = []
                for item in listado.items:
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
                    codigo_estado = str(estado_item.get("codigo") or "").strip().lower()
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
                print(
                    f"[IngestionService] Metadata sincronizada. Nuevas: {new_count}."
                    + ("" if listado.completo else " (listado INCOMPLETO)")
                )
                return ResultadoListado(
                    nuevas=new_count,
                    listadas=len(listado.items),
                    completo=listado.completo,
                    documentos=documentos,
                )
            except Exception as e:
                print(f"[IngestionService] Error al sincronizar metadatos: {e}")
                await session.rollback()
                # `completo=False` es lo que impide que el cursor avance sobre
                # una ventana que no se alcanzó a listar.
                return ResultadoListado()

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

    async def listar_cambios(
        self,
        ventana: timedelta,
        limite: int,
        al_recibir: Callable[[list[CambioDeEstado]], Awaitable[None]] | None = None,
    ) -> ListadoCambios:
        """Lo que cambió en la API en las últimas `ventana`, sin filtro de estado.

        Ventana de **cambios** (`ttl_cambio_ms`), siempre contada hacia atrás
        desde ahora: no admite cursor. Sin filtro de estado porque justamente
        interesan las que pasaron a desierta, cancelada o cerrada.

        `al_recibir` recibe los cambios legibles de cada página antes de que se
        pida la siguiente, para aplicarlos a medida que llegan (plan 305).
        """
        hasta = utc_now_naive()

        async def traducir_pagina(items: list[dict]) -> None:
            assert al_recibir is not None
            await al_recibir(
                [c for c in (cambio_desde_item(i) for i in items) if c is not None]
            )

        # Solo se pasa si hay a quién entregar: así un cliente sin soporte de
        # páginas (los dobles de los tests) sigue sirviendo.
        por_pagina = {"al_recibir_pagina": traducir_pagina} if al_recibir else {}
        listado = await self.client.get_tenders(
            hasta - ventana,
            hasta,
            limite,
            por_publicacion=False,
            estado=None,
            **por_pagina,
        )
        cambios = [
            cambio
            for cambio in (cambio_desde_item(item) for item in listado.items)
            if cambio is not None
        ]
        return ListadoCambios(
            cambios=cambios,
            listadas=len(listado.items),
            ilegibles=len(listado.items) - len(cambios),
            completo=listado.completo,
        )

    async def reencolar(self, codigos: list[str]) -> int:
        """Devuelve esos códigos a la cola, procesados o no.

        Es el `_insertar_metadata` al revés: `ON CONFLICT DO UPDATE` en vez de
        `DO NOTHING`. Reinicia `attempts` y `last_error` porque la licitación
        vuelve por un cambio en la API, no por el error de antes. Un código sin
        fila (cargado desde un dump) se inserta.
        """
        # Sin repetidos: un ON CONFLICT DO UPDATE no puede tocar dos veces la
        # misma fila en una sentencia, y Postgres lo rechaza.
        unicos = sorted(set(codigos))
        if not unicos:
            return 0

        ahora = utc_now_naive()
        reencoladas = 0
        async with AsyncSession(self.engine) as session:
            for lote in _lotes(unicos, LOTE_METADATA):
                insercion = pg_insert(TenderMetadataModel).values(
                    [
                        {
                            "id": uuid.uuid4(),
                            "code": code,
                            "is_processed": False,
                            "created_at": ahora,
                            "updated_at": ahora,
                        }
                        for code in lote
                    ]
                )
                stmt = insercion.on_conflict_do_update(
                    index_elements=["code"],
                    set_={
                        "is_processed": False,
                        "attempts": 0,
                        "last_error": None,
                        "updated_at": ahora,
                    },
                ).returning(TenderMetadataModel.code)
                resultado = await session.exec(stmt)  # type: ignore[call-overload]
                reencoladas += len(resultado.all())
            await session.commit()
        return reencoladas

    async def registrar_punteros(
        self, punteros: list[PunteroDeCambio]
    ) -> ResultadoPunteros:
        """Deja en la cola el puntero de cada código listado (plan 305).

        Una sentencia por intención y por lote. Si una conocida tiene que volver
        a bajarse se decide acá, en el mismo upsert, contra `detail_fetched_at`:
        el ingest la escribe en paralelo, y comparar contra una lectura previa
        dejaría pasar un cambio que llegó entre la lectura y la escritura.
        """
        # Un ON CONFLICT DO UPDATE no puede tocar dos veces la misma fila en una
        # sentencia. El caso de uso ya deja un cambio por código; esto es por si
        # otro llamador no lo hace. Gana el último.
        unicos = list({p.code: p for p in punteros}.values())
        resultado = ResultadoPunteros()
        if not unicos:
            return resultado

        por_intencion: dict[Intencion, list[PunteroDeCambio]] = {}
        for puntero in unicos:
            por_intencion.setdefault(puntero.intencion, []).append(puntero)

        ahora = utc_now_naive()
        async with AsyncSession(self.engine) as session:
            for intencion, grupo in por_intencion.items():
                sql = _SQL_PUNTEROS[intencion]
                for lote in _lotes(grupo, LOTE_METADATA):
                    filas = await session.exec(  # type: ignore[call-overload]
                        text(sql),
                        params={
                            "ids": [uuid.uuid4() for _ in lote],
                            "codes": [p.code for p in lote],
                            "estados": [p.status_code for p in lote],
                            "cambios": [p.changed_at for p in lote],
                            "ahora": ahora,
                            "margen": MARGEN_CAMBIO,
                        },
                    )
                    cambiadas = sum(1 for (cambio,) in filas.all() if cambio)
                    if intencion is Intencion.NUEVA:
                        resultado.nuevas += cambiadas
                    elif intencion is Intencion.INACTIVA:
                        resultado.descartadas += cambiadas
                    else:
                        resultado.actualizar += cambiadas
            await session.commit()
        return resultado

    async def ventana_a_sincronizar(self) -> tuple[datetime, datetime]:
        """De cuándo a cuándo preguntar, según hasta dónde llegó la última buena.

        Solo cuentan las corridas con estado `ok`, que es "se listó la ventana
        entera". Una `partial` —el listado se cortó a mitad— o una `failed` no
        mueven el cursor: si lo movieran, el tramo que no se alcanzó a listar no
        se volvería a pedir nunca, que es justo el agujero que esto tapa.

        Y solo los tramos de la nocturna (plan 305), más las filas de antes, sin
        tipo. La fila de la corrida nocturna entera y la de cada frecuente también
        terminan en `ok`, pero no listaron su ventana por tramos.
        """
        async with AsyncSession(self.engine) as session:
            stmt = select(func.max(col(IngestionRunModel.window_to))).where(
                IngestionRunModel.status == "ok",
                col(IngestionRunModel.kind).is_(None)
                | (col(IngestionRunModel.kind) == "tramo"),
            )
            ultimo_cierre = (await session.exec(stmt)).one_or_none()  # type: ignore[call-overload]
        return calcular_ventana(ultimo_cierre, utc_now_naive())

    async def registrar_inicio(
        self, desde: datetime, hasta: datetime, *, kind: str = "tramo"
    ) -> uuid.UUID:
        """Abre la corrida en estado `running`.

        Se escribe al empezar y no al terminar a propósito: si el proceso muere
        a mitad, la fila queda visible como colgada en vez de no existir. Y como
        `running` no mueve el cursor, una corrida interrumpida no se lleva por
        delante la ventana que no alcanzó a listar.
        """
        run_id = uuid.uuid4()
        async with AsyncSession(self.engine) as session:
            session.add(
                IngestionRunModel(
                    id=run_id,
                    window_from=_en_utc_naive(desde),
                    window_to=_en_utc_naive(hasta),
                    status="running",
                    kind=kind,
                )
            )
            await session.commit()
        return run_id

    async def registrar_fin(
        self,
        run_id: uuid.UUID,
        *,
        status: str,
        listed: int = 0,
        processed: int = 0,
        failed: int = 0,
        requests: int | None = None,
    ) -> None:
        """Cierra la corrida. Solo un tramo `ok` mueve el cursor."""
        async with AsyncSession(self.engine) as session:
            corrida = await session.get(IngestionRunModel, run_id)
            if corrida is None:
                return
            corrida.status = status
            corrida.listed = listed
            corrida.processed = processed
            corrida.failed = failed
            corrida.requests = requests
            corrida.finished_at = utc_now_naive()
            session.add(corrida)
            await session.commit()

    async def cerrar_corridas_colgadas(self, antes_de: datetime) -> int:
        """Pasa a `failed` las `running` que empezaron antes de `antes_de`.

        `failed` y no `partial`: no se sabe hasta dónde llegó, y ninguno de los
        dos mueve el cursor, así que la ventana se vuelve a pedir igual.
        """
        async with AsyncSession(self.engine) as session:
            stmt = (
                update(IngestionRunModel)
                .where(
                    col(IngestionRunModel.status) == "running",
                    col(IngestionRunModel.started_at) < _en_utc_naive(antes_de),
                )
                .values(status="failed", finished_at=utc_now_naive())
            )
            resultado = await session.exec(stmt)  # type: ignore[call-overload]
            await session.commit()
            return resultado.rowcount or 0

    async def hay_corrida_en_curso(self) -> bool:
        async with AsyncSession(self.engine) as session:
            stmt = (
                select(IngestionRunModel.id)
                .where(IngestionRunModel.status == "running")
                .limit(1)
            )
            return (await session.exec(stmt)).first() is not None

    async def process_unprocessed_tenders(
        self,
        limite: int | None = None,
        *,
        modo: ModoCola = ModoCola.TODAS,
        antes_de: datetime | None = None,
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
        pendientes = await self._pendientes(
            limite or LOTE_PROCESAMIENTO, modo, antes_de
        )
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
        cortacircuito = _Cortacircuito()
        semaforo = asyncio.Semaphore(max(1, settings.mercadopublico_detail_concurrency))

        await asyncio.gather(
            *(
                self._procesar_una(
                    metadata_id,
                    code,
                    semaforo,
                    cuota_agotada,
                    resultado,
                    cortacircuito=cortacircuito,
                    nocturno=modo is ModoCola.REINTENTOS,
                )
                for metadata_id, code in pendientes
            )
        )

        resultado.cuota_agotada = cuota_agotada.is_set()
        resultado.api_caida = cortacircuito.abierto.is_set()
        if resultado.api_caida:
            print(
                f"[IngestionService] {UMBRAL_CORTACIRCUITO} errores transitorios "
                "seguidos: se corta la pasada sin cobrar intentos a las que "
                "faltaban."
            )
        if resultado.cuota_agotada:
            print(
                "[IngestionService] Cuota agotada. Quedan licitaciones "
                "pendientes para el próximo intento."
            )
        return resultado

    async def _pendientes(
        self,
        limite: int,
        modo: ModoCola = ModoCola.TODAS,
        antes_de: datetime | None = None,
    ) -> list[tuple[uuid.UUID, str]]:
        """Los siguientes códigos por procesar, en el orden de su modo.

        El orden importa desde que hay LIMIT: sin él, una licitación que la API
        devuelve rota se quedaría al frente de todos los lotes y congelaría el
        avance de la cola entera.
        """
        async with AsyncSession(self.engine) as session:
            stmt = (
                select(TenderMetadataModel)
                .where(*condiciones_cola(modo, antes_de))
                .order_by(*_orden_cola(modo))
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
        *,
        cortacircuito: _Cortacircuito | None = None,
        nocturno: bool = False,
    ) -> None:
        """Una licitación de punta a punta, con su propia sesión.

        La sesión es por licitación y no compartida a propósito: `AsyncSession`
        no es segura entre tareas concurrentes, y de paso ninguna transacción
        vive más que la licitación que la abrió.
        """
        cortacircuito = cortacircuito or _Cortacircuito()
        async with semaforo:
            if cuota_agotada.is_set() or cortacircuito.abierto.is_set():
                return

            async with AsyncSession(self.engine) as session:
                try:
                    print(f"[IngestionService] Ingestando detalles para {code}...")
                    # El instante del pedido, no el de la escritura: un cambio
                    # que llegó mientras se bajaba tiene que quedar pendiente.
                    pedido_en = utc_now_naive()
                    detail_payload = await self.client.get_tender_detail(code)
                    cortacircuito.exito()

                    if await self._cambio_posterior(session, metadata_id, pedido_en):
                        # El cron de estados ya aplicó algo más nuevo desde el
                        # listado. Escribir este detalle lo pisaría.
                        print(
                            f"[IngestionService] {code} cambió después del pedido. "
                            "Queda para la próxima corrida."
                        )
                        await self._dejar_pendiente(session, metadata_id)
                        resultado.desactualizadas += 1
                        return

                    if not detail_payload:
                        # Vacío significa que no hay nada que traer: reintentar
                        # daría lo mismo. Distinto de un error transitorio, que
                        # sí deja la licitación en la cola.
                        print(
                            f"[IngestionService] Detalle de {code} vacío o "
                            "inválido. Marcando como procesado."
                        )
                        await self._marcar_procesada(session, metadata_id, pedido_en)
                        resultado.procesadas += 1
                        return

                    dto = self._parse_to_dto(detail_payload)

                    if self._fuera_de_region(dto.region_name):
                        print(
                            f"[IngestionService] Omitiendo {code}: región "
                            f"'{dto.region_name}' no coincide con TARGET_REGION "
                            f"'{settings.target_region}'."
                        )
                        await self._marcar_procesada(session, metadata_id, pedido_en)
                        resultado.procesadas += 1
                        return

                    await self._construir_use_case(session).execute(dto)
                    await self._marcar_procesada(session, metadata_id, pedido_en)
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
                    cortacircuito.fallo()
                    await self._registrar_fallo(
                        session,
                        metadata_id,
                        _describir(e),
                        rendirse=False,
                        nocturno=nocturno,
                    )
                    resultado.fallidas += 1
                except Exception as e:
                    print(
                        f"[IngestionService] Error al procesar licitación {code}: {e}"
                    )
                    await self._registrar_fallo(
                        session,
                        metadata_id,
                        _describir(e),
                        rendirse=True,
                        nocturno=nocturno,
                    )
                    resultado.fallidas += 1

            # Piso de espera por licitación, dentro del semáforo: espacia las
            # peticiones de cada slot sin volver a serializar el conjunto.
            if settings.mercadopublico_detail_delay:
                await asyncio.sleep(settings.mercadopublico_detail_delay)

    async def refresh_tender(self, code: str) -> TenderIngestaDTO | None:
        """Vuelve a traer una licitación ya ingerida y la actualiza (HU-16).

        Pasa por el mismo caso de uso que la ingesta, así SQL y el payload de
        Qdrant quedan alineados. Si Mercado Público no trae las dos fechas
        oficiales no se toca nada: el parser las reemplazaría por "ahora" y eso
        se leería como un cambio de fecha.
        """
        detalle = await self.client.get_tender_detail(code)
        fechas = (detalle or {}).get("fechas") or {}
        if (
            not detalle
            or not fechas.get("fecha_publicacion")
            or not fechas.get("fecha_cierre")
        ):
            return None
        dto = self._parse_to_dto(detalle)
        async with AsyncSession(self.engine) as session:
            await self._construir_use_case(session).execute(dto)
        return dto

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

        # Mismo criterio que el de arriba, con una diferencia: sin repositorio
        # inyectado ni cliente Qdrant no hay contra qué armarlo, así que se
        # omite (la ingesta funciona igual, solo que sin vectores de partidas)
        # en vez de fallar al primer upsert.
        tender_item_vector_repo: ITenderItemVectorRepository | None
        if self._tender_item_vector_repo is not None:
            tender_item_vector_repo = self._tender_item_vector_repo
        elif self.qdrant_client is not None:
            tender_item_vector_repo = QdrantTenderItemVectorRepository(
                client=self.qdrant_client,
                vector_size=settings.embedding_vector_size,
            )
        else:
            tender_item_vector_repo = None

        lexical_tender_repo: ILexicalTenderRepository | None
        if self._lexical_tender_repo is not None:
            lexical_tender_repo = self._lexical_tender_repo
        elif self.qdrant_client is not None:
            lexical_tender_repo = QdrantLexicalTenderRepository(
                client=self.qdrant_client,
            )
        else:
            lexical_tender_repo = None

        return TenderIngestionUseCase(
            repository=TenderRepository(session),
            embedding_service=self.embedding_service,
            tender_vector_repo=tender_vector_repo,
            enable_comuna_generic_heuristic=settings.enable_comuna_generic_heuristic,
            tender_item_vector_repo=tender_item_vector_repo,
            # La misma sesión que `TenderRepository`: el rollback del caso de
            # uso también cubre lo que se escribió en `tender_attachment`.
            attachment_repo=SqlTenderAttachmentRepository(session),
            lexical_tender_repo=lexical_tender_repo,
        )

    async def _cambio_posterior(
        self, session: AsyncSession, metadata_id: uuid.UUID, pedido_en: datetime
    ) -> bool:
        """Si el listado vio un cambio de la licitación después del pedido."""
        fila = await session.get(
            TenderMetadataModel, metadata_id, populate_existing=True
        )
        return bool(fila and fila.api_changed_at and fila.api_changed_at > pedido_en)

    async def _dejar_pendiente(
        self, session: AsyncSession, metadata_id: uuid.UUID
    ) -> None:
        """Sin cobrar intento: la licitación no falló, el detalle quedó viejo."""
        await session.rollback()
        fila = await session.get(
            TenderMetadataModel, metadata_id, populate_existing=True
        )
        if fila:
            fila.pending_reason = "actualizar"
            fila.updated_at = utc_now_naive()
            session.add(fila)
        await session.commit()

    async def _marcar_procesada(
        self,
        session: AsyncSession,
        metadata_id: uuid.UUID,
        pedido_en: datetime | None = None,
    ) -> None:
        """Deja la fila procesada, salvo que haya un cambio que pudo no salir.

        Si el listado reporta un cambio a menos de `MARGEN_CAMBIO` antes del
        pedido, el detalle pudo no traerlo todavía: la fila queda como
        `actualizar` para una bajada más. Cuesta a lo más una petición extra.
        """
        pedido_en = pedido_en or utc_now_naive()
        fila = await session.get(
            TenderMetadataModel, metadata_id, populate_existing=True
        )
        if fila:
            # Si falló antes y ahora entró, el error viejo haría que una
            # licitación ya ingerida pareciera fallida al revisar la cola.
            fila.last_error = None
            fila.detail_fetched_at = pedido_en
            fila.updated_at = utc_now_naive()
            reciente = (
                fila.api_changed_at is not None
                and fila.api_changed_at > pedido_en - MARGEN_CAMBIO
            )
            fila.is_processed = not reciente
            fila.pending_reason = "actualizar" if reciente else None
            session.add(fila)
        await session.commit()

    async def _registrar_fallo(
        self,
        session: AsyncSession,
        metadata_id: uuid.UUID,
        motivo: str,
        *,
        rendirse: bool,
        nocturno: bool = False,
    ) -> None:
        """Anota el intento fallido y decide si la licitación pasa a terminal.

        Antes cualquier excepción marcaba `is_processed=True` "para no bloquear
        la cola". Como el listado deduplica por código, eso la perdía para
        siempre y sin dejar rastro. Ahora el abandono queda explícito en
        `discarded_at`, con su motivo:

        - `abandono_por_error`: un error que no es de la API (`rendirse=True`)
          al llegar a `MAX_INTENTOS_INGESTA`.
        - `reintentos_agotados`: en la pasada nocturna (`nocturno=True`), al
          gastar `MAX_REINTENTOS_NOCTURNOS`.

        Con `rendirse=False` y de día, la licitación queda pendiente para la
        noche: el dato existe, fue la red la que falló.
        """
        await session.rollback()
        try:
            fila = await session.get(
                TenderMetadataModel, metadata_id, populate_existing=True
            )
            if not fila:
                return
            ahora = utc_now_naive()
            fila.attempts += 1
            fila.last_error = motivo[:500]
            fila.updated_at = ahora
            if nocturno:
                fila.night_retries += 1
            motivo_terminal = None
            if rendirse and fila.attempts >= MAX_INTENTOS_INGESTA:
                motivo_terminal = "abandono_por_error"
            elif nocturno and fila.night_retries >= MAX_REINTENTOS_NOCTURNOS:
                motivo_terminal = "reintentos_agotados"
            if motivo_terminal:
                print(
                    f"[IngestionService] {fila.code} falló {fila.attempts} veces "
                    f"({motivo_terminal}). Pasa a terminal."
                )
                fila.discarded_at = ahora
                fila.discard_reason = motivo_terminal
                fila.pending_reason = None
            session.add(fila)
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
        llamado = leer_llamado(detail)

        # Sin las dos fechas oficiales no se ingesta: antes se rellenaban con
        # "ahora", y `_actualizar` lo leía como un cambio de cierre. El error
        # cuenta como intento y, si se repite, la licitación pasa a terminal.
        faltan = [
            campo
            for campo in ("fecha_publicacion", "fecha_cierre")
            if not leer_fecha_mp(fechas.get(campo))
        ]
        if faltan:
            raise ValueError(f"El detalle no trae {' ni '.join(faltan)}.")

        def parse_date(date_str) -> datetime:
            # Naive en hora de Chile: el DTO la pasa a UTC (`normalize_to_utc`).
            # Mismo lector que el listado y el cron de estados.
            leida = leer_fecha_mp(date_str)
            return leida if leida else datetime.now(UTC).replace(tzinfo=None)

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
            # Hora de Chile naive, como las dos de arriba: el DTO las pasa a UTC.
            NumeroLlamado=llamado.numero,
            FechaCierrePrimerLlamado=llamado.cierre_primer_llamado,
            FechaCierreSegundoLlamado=llamado.cierre_segundo_llamado,
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
            # `None` si el detalle no la trae: solo está confirmado en el
            # listado (plan 233, fase 0), y la ausencia no es "sin anexos".
            documentos=documentos_desde_payload(detail),
        )
