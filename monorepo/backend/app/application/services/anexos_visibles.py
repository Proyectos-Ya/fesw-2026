"""Los anexos que una empresa ve de una licitación, listos para leer con IA (plan 233).

Lo usan la extracción de hitos y el análisis + cotización, que leen los anexos en
vez de los documentos del chat.
"""

from dataclasses import dataclass
from uuid import UUID

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.repositories.tender_attachment_repository import (
    ITenderAttachmentRepository,
)
from app.domain.entities.attachment_file import AttachmentFile, AttachmentFileStatus

# Lo que los servicios de Gemini saben mandar: PDF y PNG en línea, XLSX como texto.
TIPOS_QUE_LEE_LA_IA = frozenset({"pdf", "xlsx", "png"})


@dataclass(frozen=True)
class AnexoVisible:
    archivo: AttachmentFile
    nombre: str
    tipo: str  # extensión en minúsculas, sin punto

    @property
    def legible(self) -> bool:
        return self.tipo in TIPOS_QUE_LEE_LA_IA


async def anexos_visibles(
    files: IAttachmentFileRepository,
    attachments: ITenderAttachmentRepository,
    *,
    tender_id: UUID,
    workspace_id: UUID | None,
) -> list[AnexoVisible]:
    """Los guardados que la empresa ve (propios y compartidos), uno por contenido.

    Al promoverse un anexo, la copia privada y la canónica tienen el mismo
    contenido: se lee una sola vez y gana la canónica, que es la que queda.
    """
    guardados = [
        f
        for f in await files.list_visible_for_tender(tender_id=tender_id, workspace_id=workspace_id)
        if f.status == AttachmentFileStatus.STORED
    ]
    # Primero las canónicas, después por antigüedad: así el orden es estable.
    guardados.sort(key=lambda f: (f.workspace_id is not None, f.created_at))

    anexos: list[AnexoVisible] = []
    vistos: set[str] = set()
    for archivo in guardados:
        if archivo.sha256 in vistos:
            continue
        vistos.add(archivo.sha256)
        oficial = await attachments.get_attachment(archivo.tender_attachment_id)
        nombre = oficial.name if oficial is not None else "anexo"
        tipo = oficial.ext if oficial is not None else ""
        anexos.append(AnexoVisible(archivo=archivo, nombre=nombre, tipo=tipo.lower()))
    return anexos
