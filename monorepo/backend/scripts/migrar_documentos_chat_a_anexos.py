"""Script idempotente de migración de documentos de chat histórico a anexos oficiales (Plan 233, Decisión 5).

Requisitos:
- Ejecutable con `python -m scripts.migrar_documentos_chat_a_anexos`.
- Opciones:
  - `--dry-run` / `--aplicar`: por defecto dry-run.
  - `--confirmar-produccion`: obligatorio para aplicar cambios en entornos productivos.
  - `--limit N`: lote máximo de documentos a procesar.
"""

import argparse
import asyncio
from dataclasses import dataclass
import hashlib
import logging
from pathlib import Path
import sys
from typing import Optional
from uuid import uuid4

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.attachment_processing_job_repository import (
    IAttachmentProcessingJobRepository,
)
from app.application.services.attachment_storage import IAttachmentStorage
from app.config import settings
from app.domain.services.attachment_names import normalizar_nombre_anexo
from app.infrastructure.repositories.attachment_file_model import AttachmentFileModel
from app.infrastructure.repositories.supplier_member_model import SupplierMemberModel
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.tender_attachment_model import TenderAttachmentModel
from app.infrastructure.repositories.tender_chat_model import TenderChatDocumentModel
from app.shared.datetime_utils import utc_now_naive

logger = logging.getLogger("migrar_documentos_chat_a_anexos")


@dataclass
class ReporteMigracion:
    total_revisados: int = 0
    migrados: int = 0
    ya_migrados: int = 0
    omitidos_sin_archivo: int = 0
    omitidos_sin_empresa: int = 0
    no_emparejados: int = 0
    errores: int = 0
    dry_run: bool = True

    def imprimir(self) -> None:
        modo = "DRY-RUN (Simulación sin escrituras)" if self.dry_run else "EJECUCIÓN REAL (Cambios aplicados)"
        print("\n" + "=" * 60)
        print(f"REPORTE DE MIGRACIÓN: {modo}")
        print("=" * 60)
        print(f"Total revisados:                {self.total_revisados}")
        print(f"Migrados exitosamente:          {self.migrados}")
        print(f"Ya migrados previamente:        {self.ya_migrados}")
        print(f"Omitidos por falta de archivo:  {self.omitidos_sin_archivo}")
        print(f"Omitidos por falta de empresa:  {self.omitidos_sin_empresa}")
        print(f"No emparejados con oficial:     {self.no_emparejados}")
        print(f"Errores encontrados:            {self.errores}")
        print("=" * 60 + "\n")


async def migrar_documentos_chat_a_anexos(
    session: AsyncSession,
    storage: Optional[IAttachmentStorage] = None,
    job_repo: Optional[IAttachmentProcessingJobRepository] = None,
    dry_run: bool = True,
    limit: Optional[int] = None,
) -> ReporteMigracion:
    """Procesa los documentos de chat histórico e inserta en attachment_file si coinciden."""
    reporte = ReporteMigracion(dry_run=dry_run)

    query = select(TenderChatDocumentModel).order_by(TenderChatDocumentModel.created_at.asc())
    if limit is not None and limit > 0:
        query = query.limit(limit)

    result = await session.exec(query)
    docs = result.all()

    for doc in docs:
        reporte.total_revisados += 1
        try:
            # 1. Identificar la empresa del usuario
            supplier_res = await session.exec(
                select(SupplierModel).where(SupplierModel.user_id == doc.user_id)
            )
            supplier = supplier_res.first()
            if not supplier:
                member_res = await session.exec(
                    select(SupplierMemberModel).where(
                        SupplierMemberModel.user_id == doc.user_id,
                        SupplierMemberModel.status == "active",
                    )
                )
                member = member_res.first()
                if member:
                    sup_res = await session.exec(
                        select(SupplierModel).where(SupplierModel.id == member.supplier_id)
                    )
                    supplier = sup_res.first()

            if not supplier:
                logger.info(
                    "Doc %s (user %s): omitido sin empresa asociada",
                    doc.id,
                    doc.user_id,
                )
                reporte.omitidos_sin_empresa += 1
                continue

            workspace_id = supplier.id

            # 2. Verificar existencia física del archivo
            file_path = Path(doc.storage_path)
            if not file_path.is_file():
                logger.info(
                    "Doc %s: archivo físico no existe en disco (%s)",
                    doc.id,
                    doc.storage_path,
                )
                reporte.omitidos_sin_archivo += 1
                continue

            raw_bytes = file_path.read_bytes()
            if not raw_bytes:
                logger.info("Doc %s: archivo vacío", doc.id)
                reporte.omitidos_sin_archivo += 1
                continue

            # 3. Calcular huella SHA-256
            sha256 = hashlib.sha256(raw_bytes).hexdigest()

            # 4. Buscar anexo oficial coincidente en tender_attachment
            nombre_norm = normalizar_nombre_anexo(doc.file_name)
            att_res = await session.exec(
                select(TenderAttachmentModel).where(
                    TenderAttachmentModel.tender_id == doc.tender_id,
                    TenderAttachmentModel.name_normalized == nombre_norm,
                )
            )
            anexo = att_res.first()
            if not anexo:
                logger.info(
                    "Doc %s ('%s'): no coincide con lista oficial de Mercado Público",
                    doc.id,
                    doc.file_name,
                )
                reporte.no_emparejados += 1
                continue

            # 5. Idempotencia: verificar si ya existe attachment_file para esa clave
            existente_res = await session.exec(
                select(AttachmentFileModel).where(
                    AttachmentFileModel.tender_attachment_id == anexo.id,
                    AttachmentFileModel.sha256 == sha256,
                    AttachmentFileModel.workspace_id == workspace_id,
                )
            )
            if existente_res.first() is not None:
                logger.info(
                    "Doc %s ('%s'): ya registrado previamente en attachment_file",
                    doc.id,
                    doc.file_name,
                )
                reporte.ya_migrados += 1
                continue

            # 6. Procesar migración
            if dry_run:
                logger.info(
                    "[DRY-RUN] Migraría doc %s ('%s') a anexo %s de empresa %s",
                    doc.id,
                    doc.file_name,
                    anexo.id,
                    workspace_id,
                )
                reporte.migrados += 1
                continue

            # Modo REAL: guardar en storage y persistir fila
            ext = doc.file_type or "bin"
            storage_key = f"private/{workspace_id}/{sha256}.{ext}"

            if storage is not None:
                await storage.put_bytes(storage_key, raw_bytes)

            nuevo_archivo = AttachmentFileModel(
                id=uuid4(),
                tender_attachment_id=anexo.id,
                tender_id=doc.tender_id,
                sha256=sha256,
                size_bytes=len(raw_bytes),
                storage_key=storage_key,
                source="legacy_chat",
                uploader_user_id=doc.user_id,
                workspace_id=workspace_id,
                visibility="private",
                trust="pending",
                status="stored",
                created_at=doc.created_at,
                completed_at=utc_now_naive(),
            )
            session.add(nuevo_archivo)
            await session.commit()

            # Encolar procesamiento de extracción si la cola está disponible
            if job_repo is not None:
                try:
                    await job_repo.enqueue_extract(
                        attachment_file_id=nuevo_archivo.id,
                        tender_id=doc.tender_id,
                        priority=0,
                        now=utc_now_naive(),
                    )
                except Exception as exc:
                    logger.warning(
                        "No se pudo encolar extracción para archivo %s: %s",
                        nuevo_archivo.id,
                        exc,
                    )

            reporte.migrados += 1
            logger.info(
                "Doc %s ('%s') migrado exitosamente con ID %s",
                doc.id,
                doc.file_name,
                nuevo_archivo.id,
            )

        except Exception as exc:
            logger.error("Error al procesar doc %s: %s", doc.id, exc, exc_info=True)
            reporte.errores += 1

    return reporte


async def _main_async(aplicar: bool, confirmar_prod: bool, limit: Optional[int]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    dry_run = not aplicar
    if not dry_run and not settings.is_dev and not confirmar_prod:
        print(
            "ERROR: Para aplicar cambios en base de datos productiva es OBLIGATORIO "
            "incluir el flag --confirmar-produccion.",
            file=sys.stderr,
        )
        sys.exit(1)

    from app.bootstrap import build_attachment_storage
    from app.infrastructure.db import async_session_maker

    storage = build_attachment_storage()

    async with async_session_maker() as session:
        reporte = await migrar_documentos_chat_a_anexos(
            session=session,
            storage=storage,
            job_repo=None,
            dry_run=dry_run,
            limit=limit,
        )
        reporte.imprimir()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migra documentos históricos del chat a anexos oficiales (Plan 233, Decisión 5)."
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Aplica los cambios en la base de datos y almacenamiento (por defecto es dry-run).",
    )
    parser.add_argument(
        "--confirmar-produccion",
        action="store_true",
        help="Confirmación requerida para aplicar cambios en entornos productivos.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cantidad máxima de documentos a procesar.",
    )
    args = parser.parse_args()

    asyncio.run(_main_async(args.aplicar, args.confirmar_produccion, args.limit))


if __name__ == "__main__":
    main()
