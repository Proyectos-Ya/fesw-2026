import hashlib

import pytest
from httpx import AsyncClient


async def _login(api: AsyncClient, email: str = "documentos@example.com") -> None:
    password = "supersecret"
    register = await api.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Usuario Documentos"},
    )
    assert register.status_code == 201
    login = await api.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_document_mock_requires_authentication(api: AsyncClient) -> None:
    response = await api.post(
        "/document-uploads",
        json={
            "filename": "certificado.pdf",
            "content_type": "application/pdf",
            "size_bytes": 8,
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_document_mock_rejects_non_pdf_metadata(api: AsyncClient) -> None:
    await _login(api)

    response = await api.post(
        "/document-uploads",
        json={
            "filename": "certificado.txt",
            "content_type": "text/plain",
            "size_bytes": 8,
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_document_mock_completes_async_processing(api: AsyncClient) -> None:
    await _login(api)
    pdf = b"%PDF-1.7\nmock"
    checksum = hashlib.sha256(pdf).hexdigest()

    created = await api.post(
        "/document-uploads",
        json={
            "filename": "certificado-vigencia.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(pdf),
            "checksum_sha256": checksum,
        },
    )
    assert created.status_code == 201
    upload = created.json()
    assert upload["status"] == "pending_upload"

    stored = await api.put(
        upload["upload_url"], content=pdf, headers={"Content-Type": "application/pdf"}
    )
    assert stored.status_code == 204

    accepted = await api.post(f"/documents/{upload['document_id']}/process")
    assert accepted.status_code == 202
    job = accepted.json()
    assert job["status"] == "queued"
    assert job["progress"] == 0

    processing = await api.get(f"/document-jobs/{job['job_id']}")
    assert processing.status_code == 200
    assert processing.json()["status"] == "processing"
    assert processing.json()["progress"] == 50

    completed = await api.get(f"/document-jobs/{job['job_id']}")
    assert completed.status_code == 200
    body = completed.json()
    assert body["status"] == "completed"
    assert body["progress"] == 100
    assert body["result"]["rut"] == "76.123.456-7"
    assert body["result"]["confidence"] == pytest.approx(0.97)


@pytest.mark.asyncio
async def test_document_mock_can_simulate_processing_failure(api: AsyncClient) -> None:
    await _login(api, "fallo-documento@example.com")
    pdf = b"%PDF-1.7\nmock"

    created = await api.post(
        "/document-uploads",
        json={
            "filename": "ilegible.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(pdf),
        },
    )
    upload = created.json()
    await api.put(
        upload["upload_url"], content=pdf, headers={"Content-Type": "application/pdf"}
    )

    accepted = await api.post(
        f"/documents/{upload['document_id']}/process",
        headers={"X-Mock-Outcome": "failed"},
    )
    job_id = accepted.json()["job_id"]

    await api.get(f"/document-jobs/{job_id}")
    failed = await api.get(f"/document-jobs/{job_id}")

    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert failed.json()["error"]["code"] == "ocr_low_confidence"


@pytest.mark.asyncio
async def test_document_mock_rejects_corrupted_or_incomplete_upload(
    api: AsyncClient,
) -> None:
    await _login(api, "corrupto@example.com")
    created = await api.post(
        "/document-uploads",
        json={
            "filename": "certificado.pdf",
            "content_type": "application/pdf",
            "size_bytes": 100,
        },
    )
    upload = created.json()

    response = await api.put(
        upload["upload_url"],
        content=b"esto no es un pdf",
        headers={"Content-Type": "application/pdf"},
    )

    assert response.status_code == 422
