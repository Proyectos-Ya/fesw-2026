"""Dobles en memoria para la lista oficial de anexos (plan 233, decisión 1).

Van aparte de `fakes.py` (mismo patrón que `milestone_fakes.py`): ese archivo
diverge mucho respecto de `develop` y cada cambio ahí es un conflicto de merge.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID, uuid4

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


class InMemoryTenderAttachmentRepository(ITenderAttachmentRepository):
    """Mismas reglas que el repositorio SQL: inserta, actualiza, retira y revive."""

    def __init__(
        self,
        licitaciones: dict[str, UUID] | None = None,
        *,
        log: list[str] | None = None,
        falla_con: Exception | None = None,
    ) -> None:
        self.licitaciones = dict(licitaciones or {})
        self.filas: dict[tuple[UUID, int], OfficialAttachment] = {}
        self.sincronizadas: dict[UUID, datetime] = {}
        self.llamadas: list[tuple[dict[UUID, list[DocumentoOficialDTO]], datetime]] = []
        self.log = log
        self.falla_con = falla_con

    async def get_tender_ids_by_codes(self, codes: list[str]) -> dict[str, UUID]:
        return {c: self.licitaciones[c] for c in codes if c in self.licitaciones}

    async def sync_official_lists(
        self, listas: Mapping[UUID, Sequence[DocumentoOficialDTO]], *, visto_en: datetime
    ) -> int:
        if self.log is not None:
            self.log.append("anexos")
        if self.falla_con is not None:
            raise self.falla_con
        self.llamadas.append(({tid: list(docs) for tid, docs in listas.items()}, visto_en))

        for tender_id, documentos in listas.items():
            vistos: set[int] = set()
            for doc in documentos:
                vistos.add(doc.mp_document_id)
                clave = (tender_id, doc.mp_document_id)
                actual = self.filas.get(clave)
                if actual is None:
                    self.filas[clave] = OfficialAttachment(
                        id=uuid4(),
                        tender_id=tender_id,
                        mp_document_id=doc.mp_document_id,
                        name=doc.nombre,
                        name_normalized=normalizar_nombre_anexo(doc.nombre),
                        ext=extension_de(doc.nombre),
                        first_seen_at=visto_en,
                        last_seen_at=visto_en,
                    )
                else:
                    # El id y `first_seen_at` se conservan: la subida (decisión 2)
                    # colgará archivos de esta fila.
                    self.filas[clave] = actual.model_copy(
                        update={
                            "name": doc.nombre,
                            "name_normalized": normalizar_nombre_anexo(doc.nombre),
                            "ext": extension_de(doc.nombre),
                            "last_seen_at": visto_en,
                            "removed_at": None,
                        }
                    )
            for (tid, doc_id), fila in list(self.filas.items()):
                if tid == tender_id and doc_id not in vistos and fila.removed_at is None:
                    self.filas[(tid, doc_id)] = fila.model_copy(update={"removed_at": visto_en})
            self.sincronizadas[tender_id] = visto_en
        return len(listas)

    async def get_official_attachment(
        self, tender_id: UUID, attachment_id: UUID
    ) -> OfficialAttachment | None:
        for (tid, _), fila in self.filas.items():
            if fila.id == attachment_id and tid == tender_id and fila.removed_at is None:
                return fila
        return None

    async def get_attachment(self, attachment_id: UUID) -> OfficialAttachment | None:
        for fila in self.filas.values():
            if fila.id == attachment_id:
                return fila
        return None

    async def get_official_list(self, tender_id: UUID) -> OfficialAttachmentList | None:
        if tender_id not in self.licitaciones.values():
            return None
        vigentes = sorted(
            (f for (tid, _), f in self.filas.items() if tid == tender_id and f.removed_at is None),
            key=lambda f: f.mp_document_id,
        )
        return OfficialAttachmentList(
            attachments=vigentes, synced_at=self.sincronizadas.get(tender_id)
        )
