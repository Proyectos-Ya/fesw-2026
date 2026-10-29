"""Siembra compartida de los tests de integración de anexos (plan 233, decisión 6).

Sin `test_` en el nombre para que pytest no lo recoja. Cada función deja la sesión
confirmada: los tests de concurrencia abren sesiones aparte y tienen que ver lo
sembrado.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.services.attachment_names import normalizar_nombre_anexo
from app.infrastructure.repositories.supplier_member_model import SupplierMemberModel
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.tender_attachment_model import (
    TenderAttachmentModel,
)
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    RegionModel,
    TenderModel,
    TenderStatusModel,
)
from app.infrastructure.repositories.user_model import UserModel
from app.shared.regions import CHILE_REGIONS

AHORA = datetime(2026, 10, 3, 15, 0)
MP_DOCUMENT_ID = 1931002
NOMBRE_ANEXO = "Anexo 3.xlsx"


@dataclass(frozen=True)
class MundoAnexo:
    tender_id: UUID
    attachment_id: UUID


async def sembrar_anexo(session: AsyncSession) -> MundoAnexo:
    """Una licitación con un anexo oficial xlsx."""
    session.add(RegionModel(id=13, name=CHILE_REGIONS[13]))
    session.add(TenderStatusModel(id=2, code="publicada", name="Publicada"))
    session.add(
        BuyerInstitutionModel(
            rut="12.345.678-9",
            name="Municipalidad de Santiago",
            region_id=13,
            created_at=AHORA,
            updated_at=AHORA,
        )
    )
    tender_id, attachment_id = uuid4(), uuid4()
    session.add(
        TenderModel(
            id=tender_id,
            code="1057539-1-COT26",
            name="Materiales Eléctricos",
            description="Compra de cables y enchufes",
            status_id=2,
            published_at=AHORA,
            closing_at=AHORA + timedelta(hours=48),
            last_change_at=AHORA,
            buyer_rut="12.345.678-9",
            buyer_unit="Operaciones",
            available_amount_clp=500000.0,
            created_at=AHORA,
            updated_at=AHORA,
        )
    )
    # El anexo apunta a la licitación: se confirma antes.
    await session.commit()
    session.add(
        TenderAttachmentModel(
            id=attachment_id,
            tender_id=tender_id,
            mp_document_id=MP_DOCUMENT_ID,
            name=NOMBRE_ANEXO,
            name_normalized=normalizar_nombre_anexo(NOMBRE_ANEXO),
            ext="xlsx",
            first_seen_at=AHORA,
            last_seen_at=AHORA,
        )
    )
    await session.commit()
    return MundoAnexo(tender_id=tender_id, attachment_id=attachment_id)


async def _usuario(session: AsyncSession, user_id: UUID) -> None:
    if await session.get(UserModel, user_id) is None:
        session.add(
            UserModel(
                id=user_id,
                email=f"{user_id}@example.com",
                full_name="Usuario de Prueba",
                created_at=AHORA,
                updated_at=AHORA,
            )
        )


async def sembrar_empresa(
    session: AsyncSession, rut: str, *, miembros: Mapping[UUID, str] | None = None
) -> tuple[UUID, UUID]:
    """Una empresa con su dueño legado y una membresía por `{usuario: estado}`.

    Devuelve `(empresa, dueño)`. Los usuarios que ya existan no se vuelven a crear,
    para sembrar a una misma persona en dos empresas.
    """
    dueno, empresa = uuid4(), uuid4()
    await _usuario(session, dueno)
    for usuario in miembros or {}:
        await _usuario(session, usuario)
    await session.flush()
    session.add(
        SupplierModel(
            id=empresa,
            user_id=dueno,
            rut=rut,
            legal_name=f"Empresa {rut}",
            created_at=AHORA,
            updated_at=AHORA,
        )
    )
    await session.flush()
    for usuario, estado in (miembros or {}).items():
        session.add(
            SupplierMemberModel(
                id=uuid4(),
                user_id=usuario,
                supplier_id=empresa,
                status=estado,
                created_at=AHORA,
                updated_at=AHORA,
            )
        )
    await session.commit()
    return empresa, dueno


def aporte(
    m: MundoAnexo,
    empresa: UUID,
    autor: UUID | None,
    *,
    sha: str,
    size_bytes: int = 4,
    estado: AttachmentFileStatus = AttachmentFileStatus.STORED,
    fuente: AttachmentFileSource = AttachmentFileSource.MANUAL,
    trust: AttachmentTrust = AttachmentTrust.PENDING,
    completado: datetime = AHORA,
) -> AttachmentFile:
    """El archivo que una empresa subió para el anexo, ya guardado por defecto."""
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=m.attachment_id,
        tender_id=m.tender_id,
        sha256=sha,
        size_bytes=size_bytes,
        mime_declared="application/octet-stream",
        storage_key=f"private/{empresa}/{sha}.xlsx",
        source=fuente,
        uploader_user_id=autor,
        workspace_id=empresa,
        trust=trust,
        status=estado,
        created_at=completado - timedelta(minutes=1),
        completed_at=completado,
    )


def canonica(
    m: MundoAnexo,
    *,
    sha: str,
    visibilidad: AttachmentVisibility = AttachmentVisibility.SHARED,
    trust: AttachmentTrust = AttachmentTrust.CORROBORATED,
    creado: datetime = AHORA,
) -> AttachmentFile:
    """La versión compartida de un anexo: sin empresa ni autor."""
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=m.attachment_id,
        tender_id=m.tender_id,
        sha256=sha,
        size_bytes=4,
        storage_key=f"shared/{m.tender_id}/{MP_DOCUMENT_ID}/{sha}.xlsx",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=None,
        workspace_id=None,
        visibility=visibilidad,
        trust=trust,
        status=AttachmentFileStatus.STORED,
        created_at=creado,
        completed_at=creado,
    )
