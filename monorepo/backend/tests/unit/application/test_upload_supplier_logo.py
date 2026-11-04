import hashlib
from uuid import uuid4

import pytest

from app.application.use_cases.supplier.upload_supplier_logo import (
    INVALID_LOGO_MESSAGE,
    MAX_LOGO_SIZE_BYTES,
    UploadSupplierLogoUseCase,
)
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import (
    SupplierLogoStorageUnavailable,
    SupplierNotFoundForUser,
    SupplierValidationError,
)
from tests.unit.application.attachment_file_fakes import FakeAttachmentStorage
from tests.unit.application.fakes import InMemorySupplierRepository

PNG_HEADER = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
JPG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 50


def _build_supplier(user_id=None) -> Supplier:
    return Supplier(
        user_id=user_id or uuid4(),
        rut="76.086.428-5",
        legal_name="Empresa Prueba SpA",
        description="Empresa de servicios tecnológicos con amplia experiencia en licitaciones.",
        regions=["Metropolitana"],
        sectors=["Tecnología"],
        years_experience=5,
        num_employees=10,
    )


@pytest.mark.asyncio
async def test_upload_png_logo_success():
    repo = InMemorySupplierRepository()
    storage = FakeAttachmentStorage()
    user_id = uuid4()
    supplier = _build_supplier(user_id=user_id)
    await repo.save(supplier)

    use_case = UploadSupplierLogoUseCase(repo=repo, storage=storage)

    result = await use_case.execute(
        user_id=user_id,
        file_bytes=PNG_HEADER,
        content_type="image/png",
        filename="logo.png",
    )

    sha16 = hashlib.sha256(PNG_HEADER).hexdigest()[:16]
    expected_key = f"logos/{supplier.id}/{sha16}.png"
    assert storage.objetos.get(expected_key) == PNG_HEADER
    expected_url = f"/api/suppliers/{supplier.id}/logo/{sha16}.png"
    assert result.logo_url == expected_url

    # Verify persisted in repository
    persisted = await repo.get_by_id(supplier.id)
    assert persisted is not None
    assert persisted.logo_url == expected_url


@pytest.mark.asyncio
async def test_upload_jpg_logo_uses_api_endpoint():
    repo = InMemorySupplierRepository()
    storage = FakeAttachmentStorage()
    user_id = uuid4()
    supplier = _build_supplier(user_id=user_id)
    await repo.save(supplier)

    use_case = UploadSupplierLogoUseCase(repo=repo, storage=storage)

    result = await use_case.execute(
        user_id=user_id,
        file_bytes=JPG_HEADER,
        content_type="image/jpeg",
        filename="corporativo.jpg",
    )

    sha16 = hashlib.sha256(JPG_HEADER).hexdigest()[:16]
    expected_key = f"logos/{supplier.id}/{sha16}.jpg"
    assert storage.objetos.get(expected_key) == JPG_HEADER
    assert result.logo_url == f"/api/suppliers/{supplier.id}/logo/{sha16}.jpg"


@pytest.mark.asyncio
async def test_upload_logo_too_large_raises_validation_error():
    repo = InMemorySupplierRepository()
    storage = FakeAttachmentStorage()
    user_id = uuid4()
    supplier = _build_supplier(user_id=user_id)
    await repo.save(supplier)

    use_case = UploadSupplierLogoUseCase(repo=repo, storage=storage)
    oversized = b"\x89PNG\r\n\x1a\n" + b"X" * (MAX_LOGO_SIZE_BYTES + 1)

    with pytest.raises(SupplierValidationError) as exc_info:
        await use_case.execute(
            user_id=user_id,
            file_bytes=oversized,
            content_type="image/png",
            filename="large.png",
        )
    assert str(exc_info.value) == INVALID_LOGO_MESSAGE
    assert len(storage.objetos) == 0


@pytest.mark.asyncio
async def test_upload_logo_invalid_format_raises_validation_error():
    repo = InMemorySupplierRepository()
    storage = FakeAttachmentStorage()
    user_id = uuid4()
    supplier = _build_supplier(user_id=user_id)
    await repo.save(supplier)

    use_case = UploadSupplierLogoUseCase(repo=repo, storage=storage)
    pdf_bytes = b"%PDF-1.4 header bytes"

    with pytest.raises(SupplierValidationError) as exc_info:
        await use_case.execute(
            user_id=user_id,
            file_bytes=pdf_bytes,
            content_type="application/pdf",
            filename="doc.pdf",
        )
    assert str(exc_info.value) == INVALID_LOGO_MESSAGE
    assert len(storage.objetos) == 0


@pytest.mark.asyncio
async def test_upload_logo_empty_file_raises_validation_error():
    repo = InMemorySupplierRepository()
    storage = FakeAttachmentStorage()
    user_id = uuid4()
    supplier = _build_supplier(user_id=user_id)
    await repo.save(supplier)

    use_case = UploadSupplierLogoUseCase(repo=repo, storage=storage)

    with pytest.raises(SupplierValidationError) as exc_info:
        await use_case.execute(
            user_id=user_id,
            file_bytes=b"",
            content_type="image/png",
            filename="empty.png",
        )
    assert str(exc_info.value) == INVALID_LOGO_MESSAGE


@pytest.mark.asyncio
async def test_upload_logo_deletes_previous_logo_best_effort():
    repo = InMemorySupplierRepository()
    storage = FakeAttachmentStorage()
    user_id = uuid4()
    supplier = _build_supplier(user_id=user_id)
    old_key = f"logos/{supplier.id}/old1234567890123.png"
    storage.objetos[old_key] = b"old"
    supplier.logo_url = f"/api/suppliers/{supplier.id}/logo/old1234567890123.png"
    await repo.save(supplier)

    use_case = UploadSupplierLogoUseCase(repo=repo, storage=storage)

    result = await use_case.execute(
        user_id=user_id,
        file_bytes=PNG_HEADER,
        content_type="image/png",
        filename="new.png",
    )

    assert old_key not in storage.objetos
    assert result.logo_url != supplier.logo_url


@pytest.mark.asyncio
async def test_upload_logo_when_storage_is_none_raises_storage_unavailable():
    repo = InMemorySupplierRepository()
    user_id = uuid4()
    supplier = _build_supplier(user_id=user_id)
    await repo.save(supplier)

    use_case = UploadSupplierLogoUseCase(repo=repo, storage=None)

    with pytest.raises(SupplierLogoStorageUnavailable):
        await use_case.execute(
            user_id=user_id,
            file_bytes=PNG_HEADER,
            content_type="image/png",
            filename="logo.png",
        )


@pytest.mark.asyncio
async def test_upload_logo_when_user_has_no_supplier_raises_not_found():
    repo = InMemorySupplierRepository()
    storage = FakeAttachmentStorage()
    use_case = UploadSupplierLogoUseCase(repo=repo, storage=storage)

    with pytest.raises(SupplierNotFoundForUser):
        await use_case.execute(
            user_id=uuid4(),
            file_bytes=PNG_HEADER,
            content_type="image/png",
            filename="logo.png",
        )
