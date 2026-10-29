import hashlib
import re
from typing import Literal
from uuid import UUID

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.services.attachment_storage import IAttachmentStorage
from app.application.use_cases.supplier.resolver_empresa import resolver_empresa
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import (
    SupplierLogoStorageUnavailable,
    SupplierNotFoundForUser,
    SupplierValidationError,
)
from app.shared.datetime_utils import utc_now_naive

MAX_LOGO_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
INVALID_LOGO_MESSAGE = "Formato inválido o archivo muy pesado"

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"

_VALID_FILENAMES = re.compile(r"^[0-9a-f]{16}\.(png|jpg)$")


def detect_valid_logo_extension(
    file_bytes: bytes,
    content_type: str | None = None,
    filename: str | None = None,
) -> Literal["png", "jpg"]:
    """Valida tamaño, firma binaria (magic bytes) y extensión del logo corporativo."""
    if not file_bytes or len(file_bytes) > MAX_LOGO_SIZE_BYTES:
        raise SupplierValidationError(INVALID_LOGO_MESSAGE)

    ext: Literal["png", "jpg"] | None = None
    if file_bytes.startswith(PNG_SIGNATURE):
        ext = "png"
    elif file_bytes.startswith(JPEG_SIGNATURE):
        ext = "jpg"
    else:
        raise SupplierValidationError(INVALID_LOGO_MESSAGE)

    if content_type:
        clean_ct = content_type.lower().split(";")[0].strip()
        allowed_cts = (
            {"image/png", "application/octet-stream"}
            if ext == "png"
            else {"image/jpeg", "image/jpg", "application/octet-stream"}
        )
        if clean_ct not in allowed_cts:
            raise SupplierValidationError(INVALID_LOGO_MESSAGE)

    if filename:
        clean_name = filename.lower()
        allowed_exts = (".png",) if ext == "png" else (".jpg", ".jpeg")
        if not clean_name.endswith(allowed_exts):
            raise SupplierValidationError(INVALID_LOGO_MESSAGE)

    return ext


class UploadSupplierLogoUseCase:
    """Valida, sube a la nube y persiste el logo de la empresa en PostgreSQL."""

    def __init__(
        self,
        repo: ISupplierRepository,
        storage: IAttachmentStorage | None,
        public_base_url: str | None = None,
    ):
        self.repo = repo
        self.storage = storage
        self.public_base_url = public_base_url

    async def execute(
        self,
        user_id: UUID,
        file_bytes: bytes,
        content_type: str | None = None,
        filename: str | None = None,
        supplier_id: UUID | None = None,
    ) -> Supplier:
        if self.storage is None:
            raise SupplierLogoStorageUnavailable()

        supplier = await resolver_empresa(self.repo, user_id, supplier_id)
        if supplier is None:
            raise SupplierNotFoundForUser(user_id)

        ext = detect_valid_logo_extension(
            file_bytes=file_bytes,
            content_type=content_type,
            filename=filename,
        )

        sha16 = hashlib.sha256(file_bytes).hexdigest()[:16]
        object_name = f"{sha16}.{ext}"
        key = f"logos/{supplier.id}/{object_name}"

        await self.storage.put_bytes(key, file_bytes)

        # Limpieza en best-effort del logo anterior si existía y era distinto
        if supplier.logo_url:
            await self._cleanup_old_logo_best_effort(supplier.id, supplier.logo_url, object_name)

        if self.public_base_url:
            logo_url = f"{self.public_base_url.rstrip('/')}/{key}"
        else:
            logo_url = f"/api/suppliers/{supplier.id}/logo/{object_name}"

        now = utc_now_naive()
        updated_supplier = supplier.model_copy(
            update={
                "logo_url": logo_url,
                "updated_at": now,
            }
        )
        return await self.repo.update(updated_supplier)

    async def _cleanup_old_logo_best_effort(
        self, supplier_id: UUID, old_logo_url: str, new_object_name: str
    ) -> None:
        try:
            match = re.search(r"logos/[^/]+/([a-zA-Z0-9_\-]+\.(?:png|jpg))", old_logo_url)
            if not match:
                match = re.search(r"/logo/([a-zA-Z0-9_\-]+\.(?:png|jpg))", old_logo_url)
            if match:
                old_file = match.group(1)
                if old_file != new_object_name and self.storage:
                    await self.storage.delete(f"logos/{supplier_id}/{old_file}")
        except Exception:
            pass
