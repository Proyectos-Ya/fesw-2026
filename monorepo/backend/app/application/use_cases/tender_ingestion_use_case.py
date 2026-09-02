import uuid
from dataclasses import dataclass
from typing import Any

from app.application.repositories.tender_repository import ITenderRepository
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.text_builder import TextBuilder
from app.domain.entities.tender import utc_now_naive
from app.domain.models.tender_ingestion_dto import TenderIngestaDTO
from app.infrastructure.repositories.tender_model import TenderItemModel, TenderModel
from app.shared.comunas import resolve_comuna
from app.shared.datetime_utils import to_utc_epoch


@dataclass
class _TenderTexto:
    """Lo mínimo que `TextBuilder` necesita de una licitación.

    Existe para poder armar el texto del detalle nuevo sin construir un
    `TenderModel` completo solo para compararlo y tirarlo.
    """

    name: str
    description: str | None


class TenderIngestionUseCase:
    def __init__(
        self,
        repository: ITenderRepository,
        embedding_service: IEmbeddingService,
        tender_vector_repo: ITenderVectorRepository,
        enable_comuna_generic_heuristic: bool = False,
    ):
        self.repo = repository
        self.embedding_service = embedding_service
        self.tender_vector_repo = tender_vector_repo
        self.text_builder = TextBuilder()
        # Ver settings.enable_comuna_generic_heuristic: apagado por defecto
        # hasta decidir si el riesgo de falso positivo de la heurística
        # genérica (app/shared/comunas.py) vale la pena.
        self.enable_comuna_generic_heuristic = enable_comuna_generic_heuristic

    async def execute(self, dto: TenderIngestaDTO) -> dict[str, Any]:
        """Ingesta una licitación. La cola de pendientes la maneja el servicio."""
        try:
            existente = await self.repo.get_by_code(dto.code)
            if existente:
                return await self._actualizar(existente, dto)

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

            tender_items = self._construir_items(tender_id, dto)

            text = self.text_builder.build_from_tender(new_tender, tender_items)
            vectors = await self.embedding_service.embed([text])
            status_code = dto.status_semantic_code

            # Resolución de comuna/provincia: son lecturas puras (sin
            # escritura), así que da igual que ocurran antes de abrir la
            # transacción SQL. Tienen que estar listas antes del upsert a
            # Qdrant para poder viajar en su payload -- es ahí donde
            # `/tenders/search` filtra por provincia/comuna, igual que ya
            # hace con región.
            comuna_name, comuna_source = resolve_comuna(
                dto.buyer_name,
                use_generic_fallback=self.enable_comuna_generic_heuristic,
            )
            comuna_id = (
                await self.repo.get_comuna_id_by_name(comuna_name)
                if comuna_name
                else None
            )
            provincia_id = (
                await self.repo.get_provincia_id_by_comuna_id(comuna_id)
                if comuna_id
                else None
            )

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
                    "provincia_id": provincia_id,
                    "comuna_id": comuna_id,
                    "available_amount_clp": dto.available_amount_clp,
                    # Como epoch entero: Qdrant no compara `datetime`, y el
                    # buscador manual pre-filtra por rango de fechas sobre el
                    # payload. Sin esto, filtrar por fecha obligaría a traer
                    # top-K y descartar después, que devuelve casi nada en
                    # cuanto el filtro es algo específico.
                    "closing_at": to_utc_epoch(dto.closing_at),
                    "published_at": to_utc_epoch(dto.published_at),
                },
            )

            # Recién acá se abre la transacción SQL. Ambos get_or_create
            # hacen flush, así que dejarlos antes del embedding mantendría
            # los locks tomados durante toda la inferencia del modelo.
            # Son las claves foráneas de new_tender: deben existir al commit.
            await self.repo.get_or_create_buyer(
                rut=safe_buyer_rut,
                name=dto.buyer_name,
                region_id=region_id,
                comuna_id=comuna_id,
                comuna_resolution_source=comuna_source if comuna_id else None,
            )
            await self.repo.get_or_create_status(
                status_id=dto.status_code, code=dto.status_semantic_code
            )
            await self.repo.save_complex_tender(new_tender, tender_items)

            return {"status": "success", "tender_code": dto.code}

        except Exception as e:
            # get_or_create_buyer/status hacen flush dentro de la misma
            # transacción: sin rollback quedarían pendientes en la sesión.
            print(f"[Error Ingesta] Falló procesamiento de licitación {dto.code}: {e}")
            await self.repo.rollback()
            raise

    async def _actualizar(
        self, existente: TenderModel, dto: TenderIngestaDTO
    ) -> dict[str, Any]:
        """Refleja en la licitación guardada lo que cambió en la API.

        Antes esto era un `return {"status": "skipped"}`: se le pedía a Mercado
        Público el endpoint de **cambios** y se descartaban justamente los
        cambios, así que monto, fecha de cierre y estado quedaban congelados en
        lo que se vio el día de la ingesta.

        Se separan dos casos porque tienen precios muy distintos:

        - **Cambio semántico** — nombre, descripción o partidas, que es lo que
          `TextBuilder` mete en el texto. Cambia el vector, así que hay que pagar
          una inferencia y reescribir el punto entero.
        - **Cambio de metadatos** — estado, cierre, monto. No cambia lo que la
          licitación pide: basta actualizar SQL y el payload. Es el caso
          frecuente, porque lo que se mueve a diario son las fechas y el estado.

        Para distinguirlos no hace falta una columna nueva: se reconstruye el
        texto desde lo persistido y se compara con el que saldría del detalle
        nuevo.
        """
        items_nuevos = self._construir_items(existente.id, dto)
        items_actuales = await self.repo.get_items_by_tender_id(existente.id)

        texto_actual = self.text_builder.build_from_tender(existente, items_actuales)
        texto_nuevo = self.text_builder.build_from_tender(
            _TenderTexto(name=dto.name, description=dto.description), items_nuevos
        )
        cambio_semantico = texto_actual != texto_nuevo
        cambio_metadatos = self._metadatos_cambiaron(existente, dto)

        if not cambio_semantico and not cambio_metadatos:
            # No escribir es parte del contrato, no una optimización: mover
            # `updated_at` sin motivo haría que el análisis de Gemini se
            # regenerara para cada proveedor todos los días (ver 6.4).
            return {"status": "unchanged", "tender_code": dto.code}

        payload = {
            "status_code": dto.status_semantic_code,
            "region_id": dto.region_id,
            "available_amount_clp": dto.available_amount_clp,
            "closing_at": to_utc_epoch(dto.closing_at),
            "published_at": to_utc_epoch(dto.published_at),
        }

        # Qdrant antes que SQL, igual que en el alta y por lo mismo: las dos
        # escrituras no comparten transacción. Si SQL falla después, la corrida
        # siguiente vuelve a ver la diferencia y se autocorrige.
        if cambio_semantico:
            vectors = await self.embedding_service.embed([texto_nuevo])
            await self.tender_vector_repo.upsert(
                tender_id=existente.id, embedding=vectors[0], payload=payload
            )
            await self.repo.replace_tender_items(existente.id, items_nuevos)
        else:
            await self.tender_vector_repo.set_payload(existente.id, payload)

        self._aplicar_cambios(existente, dto)
        await self.repo.update_tender(existente)

        return {
            "status": "updated",
            "tender_code": dto.code,
            "semantico": cambio_semantico,
        }

    def _construir_items(
        self, tender_id: uuid.UUID, dto: TenderIngestaDTO
    ) -> list[TenderItemModel]:
        return [
            TenderItemModel(
                id=uuid.uuid4(),
                tender_id=tender_id,
                product_code=str(item.codigo_unspsc) if item.codigo_unspsc else "0",
                name=item.nombre_producto,
                description=item.descripcion,
                quantity=item.cantidad,
                unit_of_measure=item.unidad_medida,
            )
            for item in dto.items
        ]

    @staticmethod
    def _metadatos_cambiaron(existente: TenderModel, dto: TenderIngestaDTO) -> bool:
        return (
            existente.status_id != dto.status_code
            or existente.closing_at != dto.closing_at
            or existente.published_at != dto.published_at
            or existente.available_amount_clp != dto.available_amount_clp
            or existente.buyer_unit != dto.buyer_unit
        )

    @staticmethod
    def _aplicar_cambios(existente: TenderModel, dto: TenderIngestaDTO) -> None:
        """Vuelca el detalle sobre la fila. No toca `code` ni `created_at`.

        `buyer_rut` tampoco: si el organismo cambiara habría que crear el nuevo
        comprador antes, y no se ha visto que pase. Se deja fuera a propósito en
        vez de arriesgar una violación de clave foránea en la corrida diaria.
        """
        existente.name = dto.name
        existente.description = dto.description
        existente.status_id = dto.status_code
        existente.published_at = dto.published_at
        existente.closing_at = dto.closing_at
        existente.available_amount_clp = dto.available_amount_clp
        existente.buyer_unit = dto.buyer_unit
        existente.last_change_at = utc_now_naive()
        existente.updated_at = utc_now_naive()
