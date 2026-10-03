from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime

from app.application.repositories.tender_attachment_repository import (
    ITenderAttachmentRepository,
)
from app.domain.models.cambio_estado import CambioDeEstado
from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from app.shared.datetime_utils import utc_now_naive


def listas_desde_cambios(
    cambios: Iterable[CambioDeEstado],
) -> dict[str, list[DocumentoOficialDTO]]:
    """La lista más reciente de cada código, entre los cambios que la traen.

    Mismo criterio que `_mas_reciente_por_codigo` del cron de estados: el
    listado pagina mientras la API cambia y un código puede venir dos veces.
    """
    elegidos: dict[str, CambioDeEstado] = {}
    for cambio in cambios:
        if cambio.documentos is None:
            continue
        actual = elegidos.get(cambio.code)
        if actual is None or (cambio.changed_at or datetime.min) > (
            actual.changed_at or datetime.min
        ):
            elegidos[cambio.code] = cambio
    return {code: list(c.documentos or ()) for code, c in elegidos.items()}


class SyncOfficialAttachmentsUseCase:
    """Refresca la lista oficial con lo que los crons **ya listaron** (no gasta cuota).

    Las licitaciones que no tenemos se ignoran: la clave foránea no deja
    guardarlas, y su lista llega cuando la ingesta las traiga.
    """

    def __init__(self, attachments: ITenderAttachmentRepository) -> None:
        self.attachments = attachments

    async def execute(
        self, listas_por_codigo: Mapping[str, Sequence[DocumentoOficialDTO]]
    ) -> int:
        """Devuelve cuántas licitaciones conocidas quedaron sincronizadas."""
        if not listas_por_codigo:
            return 0
        ids = await self.attachments.get_tender_ids_by_codes(list(listas_por_codigo))
        listas = {tid: list(listas_por_codigo[code]) for code, tid in ids.items()}
        if not listas:
            return 0
        # Un solo `visto_en` por llamada: el repositorio retira lo que no vino
        # comparando contra él.
        return await self.attachments.sync_official_lists(
            listas, visto_en=utc_now_naive()
        )
