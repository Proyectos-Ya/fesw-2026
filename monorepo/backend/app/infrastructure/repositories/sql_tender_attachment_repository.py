import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.tender_attachment_repository import (
    ITenderAttachmentRepository,
)
from app.domain.entities.tender_attachment import (
    OfficialAttachment,
    OfficialAttachmentList,
)
from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from app.domain.services.attachment_names import (
    extension_de,
    normalizar_nombre_anexo,
)
from app.infrastructure.repositories.tender_attachment_model import (
    TenderAttachmentModel,
)
from app.infrastructure.repositories.tender_model import TenderModel

_LOTE_CODIGOS = 1000
_LOTE_LICITACIONES = 500
# 9 columnas por fila: 9.000 parámetros por sentencia, lejos del techo de 65.535.
_LOTE_FILAS = 1000


def _trozos(elementos: Sequence[Any], tamano: int):
    for inicio in range(0, len(elementos), tamano):
        yield elementos[inicio : inicio + tamano]


def _filas(
    lote: Sequence[UUID],
    listas: Mapping[UUID, Sequence[DocumentoOficialDTO]],
    visto_en: datetime,
) -> list[dict[str, Any]]:
    """Una fila por (licitación, documento), sin repetidos y en orden estable.

    Sin repetidos: ON CONFLICT DO UPDATE no puede tocar dos veces la misma fila
    en una sentencia. Ordenadas: dos crons que escriben a la vez toman los locks
    en el mismo orden, y así se evita un deadlock.
    """
    por_clave: dict[tuple[UUID, int], dict[str, Any]] = {}
    for tender_id in lote:
        for doc in listas[tender_id]:
            por_clave[(tender_id, doc.mp_document_id)] = {
                "id": uuid.uuid4(),
                "tender_id": tender_id,
                "mp_document_id": doc.mp_document_id,
                "name": doc.nombre,
                "name_normalized": normalizar_nombre_anexo(doc.nombre),
                "ext": extension_de(doc.nombre),
                "first_seen_at": visto_en,
                "last_seen_at": visto_en,
                "removed_at": None,
            }
    return [por_clave[k] for k in sorted(por_clave)]


def _a_entidad(model: TenderAttachmentModel) -> OfficialAttachment:
    return OfficialAttachment(
        id=model.id,
        tender_id=model.tender_id,
        mp_document_id=model.mp_document_id,
        name=model.name,
        name_normalized=model.name_normalized,
        ext=model.ext,
        first_seen_at=model.first_seen_at,
        last_seen_at=model.last_seen_at,
        removed_at=model.removed_at,
    )


class SqlTenderAttachmentRepository(ITenderAttachmentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_tender_ids_by_codes(self, codes: list[str]) -> dict[str, UUID]:
        ids: dict[str, UUID] = {}
        for lote in _trozos(sorted(set(codes)), _LOTE_CODIGOS):
            resultado = await self.session.exec(
                select(TenderModel.code, TenderModel.id).where(
                    col(TenderModel.code).in_(lote)
                )
            )
            for code, tender_id in resultado.all():
                ids[code] = tender_id
        return ids

    async def sync_official_lists(
        self, listas: Mapping[UUID, Sequence[DocumentoOficialDTO]], *, visto_en: datetime
    ) -> int:
        tender_ids = sorted(listas)
        for lote in _trozos(tender_ids, _LOTE_LICITACIONES):
            for trozo in _trozos(_filas(lote, listas, visto_en), _LOTE_FILAS):
                insercion = pg_insert(TenderAttachmentModel).values(trozo)
                # `first_seen_at` no va en `set_`: se escribe solo al insertar.
                # `excluded["name"]` con subíndice: `name` podría chocar con un
                # atributo de la colección.
                stmt = insercion.on_conflict_do_update(
                    index_elements=["tender_id", "mp_document_id"],
                    set_={
                        "name": insercion.excluded["name"],
                        "name_normalized": insercion.excluded["name_normalized"],
                        "ext": insercion.excluded["ext"],
                        "last_seen_at": insercion.excluded["last_seen_at"],
                        "removed_at": None,
                    },
                )
                await self.session.exec(stmt)  # type: ignore[call-overload]

            # Retira lo que no vino. Funciona porque todas las filas vigentes de
            # esta llamada quedaron con `last_seen_at = visto_en`: un solo
            # `visto_en` por llamada, y lo que sigue con un `last_seen_at` más
            # viejo es lo que Mercado Público ya no publica.
            await self.session.exec(  # type: ignore[call-overload]
                update(TenderAttachmentModel)
                .where(
                    col(TenderAttachmentModel.tender_id).in_(lote),
                    col(TenderAttachmentModel.removed_at).is_(None),
                    col(TenderAttachmentModel.last_seen_at) < visto_en,
                )
                .values(removed_at=visto_en)
            )
            # Solo `attachments_synced_at`: `updated_at` dispara la regeneración
            # del análisis de Gemini y no se toca nunca.
            await self.session.exec(  # type: ignore[call-overload]
                update(TenderModel)
                .where(col(TenderModel.id).in_(lote))
                .values(attachments_synced_at=visto_en)
            )
            await self.session.commit()
        return len(tender_ids)

    async def get_official_attachment(
        self, tender_id: UUID, attachment_id: UUID
    ) -> OfficialAttachment | None:
        modelo = (
            await self.session.exec(
                select(TenderAttachmentModel).where(
                    col(TenderAttachmentModel.id) == attachment_id,
                    col(TenderAttachmentModel.tender_id) == tender_id,
                    col(TenderAttachmentModel.removed_at).is_(None),
                )
            )
        ).first()
        return _a_entidad(modelo) if modelo is not None else None

    async def get_attachment(self, attachment_id: UUID) -> OfficialAttachment | None:
        modelo = (
            await self.session.exec(
                select(TenderAttachmentModel).where(
                    col(TenderAttachmentModel.id) == attachment_id
                )
            )
        ).first()
        return _a_entidad(modelo) if modelo is not None else None

    async def get_official_list(self, tender_id: UUID) -> OfficialAttachmentList | None:
        # Dos columnas a propósito: con solo `attachments_synced_at`, `first()` daría
        # None tanto si la licitación no existe como si nunca se sincronizó.
        fila = (
            await self.session.exec(  # type: ignore[call-overload]
                select(TenderModel.id, TenderModel.attachments_synced_at).where(
                    col(TenderModel.id) == tender_id
                )
            )
        ).first()
        if fila is None:
            return None
        modelos = (
            await self.session.exec(
                select(TenderAttachmentModel)
                .where(
                    col(TenderAttachmentModel.tender_id) == tender_id,
                    col(TenderAttachmentModel.removed_at).is_(None),
                )
                .order_by(col(TenderAttachmentModel.mp_document_id).asc())
            )
        ).all()
        return OfficialAttachmentList(
            attachments=[_a_entidad(m) for m in modelos], synced_at=fila[1]
        )
