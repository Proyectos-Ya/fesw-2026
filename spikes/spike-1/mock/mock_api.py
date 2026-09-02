"""API aislada del SPIKE 1.3. Solo demostración local; no montar en producción."""

import hashlib
from copy import deepcopy
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field, model_validator

from engine import FIXTURES, compare, extract

MAX_BYTES = 5 * 1024 * 1024
Kind = Literal["bases", "propuesta"]


class CaseInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class UploadInput(BaseModel):
    kind: Kind
    fixture: str
    filename: str = Field(min_length=5, max_length=200)
    size_bytes: int = Field(gt=0, le=MAX_BYTES)
    checksum_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    replaces_document_id: UUID | None = None

    @model_validator(mode="after")
    def valid_fixture(self):
        if self.fixture not in FIXTURES or FIXTURES[self.fixture]["kind"] != self.kind:
            raise ValueError("Fixture incompatible con el tipo de carga")
        if not self.filename.lower().endswith(".pdf"):
            raise ValueError("Solo se aceptan nombres PDF en esta demo")
        return self


class ProcessInput(BaseModel):
    kind: Kind
    simulate_failure: bool = False


class Confirmation(BaseModel):
    version: int = Field(gt=0)


def demo_user(x_demo_user: Annotated[UUID | None, Header()] = None) -> str:
    if x_demo_user is None:
        raise HTTPException(
            401, "Falta X-Demo-User. Identidad simulada, no autenticación real."
        )
    return str(x_demo_user)


Owner = Annotated[str, Depends(demo_user)]


def create_app() -> FastAPI:
    app = FastAPI(
        title="SPIKE 1.3 - MOCK de revisión documental",
        description="SIMULADO. No ejecuta OCR, no verifica firmas, no usa BD. "
        "X-Demo-User es una identidad manipulable de prueba, NO un mecanismo de seguridad. "
        "Los trabajos avanzan al consultar: processing y luego completed/failed.",
    )
    cases: dict[str, dict] = {}
    jobs: dict[str, dict] = {}

    def owned(case_id: str, owner: str) -> dict:
        case = cases.get(case_id)
        if case is None or case["owner"] != owner:
            raise HTTPException(404, "Expediente no encontrado")
        return case

    def enqueue(case: dict, kind: str, result: dict, fail: bool = False) -> dict:
        if len(jobs) >= 1000:
            raise HTTPException(429, "Límite de trabajos de demo; reinicie la API")
        job_id = str(uuid4())
        jobs[job_id] = {
            "id": job_id,
            "case_id": case["id"],
            "owner": case["owner"],
            "kind": kind,
            "status": "queued",
            "polls": 0,
            "fail": fail,
            "snapshot": deepcopy(result),
            "bases_version": case["bases_version"],
            "propuesta_version": case["propuesta_version"],
            "result": None,
            "error": None,
        }
        return {
            "simulated": True,
            "job_id": job_id,
            "status": "queued",
            "job_url": f"/mock/jobs/{job_id}",
        }

    @app.get("/mock/fixtures")
    async def fixtures():
        return {"simulated": True, "fixtures": FIXTURES}

    @app.post("/mock/expedientes", status_code=201)
    async def create_case(payload: CaseInput, owner: Owner):
        if len(cases) >= 100:
            raise HTTPException(429, "Límite de expedientes de demo; reinicie la API")
        case_id = str(uuid4())
        cases[case_id] = {
            "id": case_id,
            "owner": owner,
            "name": payload.name,
            "documents": {},
            "bases_version": 0,
            "propuesta_version": 0,
            "confirmed_version": None,
            "bases_ready": None,
            "propuesta_ready": None,
        }
        return {"id": case_id, "simulated": True}

    @app.get("/mock/expedientes/{case_id}")
    async def get_case(case_id: str, owner: Owner):
        case = owned(case_id, owner)
        return {**case, "simulated": True}

    @app.post("/mock/expedientes/{case_id}/uploads", status_code=201)
    async def create_upload(case_id: str, payload: UploadInput, owner: Owner):
        case = owned(case_id, owner)
        if len(case["documents"]) >= 20:
            raise HTTPException(429, "Máximo 20 documentos por expediente de demo")
        previous = None
        if payload.replaces_document_id:
            previous = case["documents"].get(str(payload.replaces_document_id))
            if (
                previous is None
                or not previous["active"]
                or previous["kind"] != payload.kind
            ):
                raise HTTPException(
                    409,
                    "El documento a reemplazar debe estar activo y pertenecer al mismo grupo",
                )
        document_id = str(uuid4())
        case["documents"][document_id] = {
            **payload.model_dump(mode="json"),
            "id": document_id,
            "uploaded": False,
            "active": True,
        }
        if previous:
            previous["active"] = False
        case[payload.kind + "_version"] += 1
        case[payload.kind + "_ready"] = None
        if payload.kind == "bases":
            case["confirmed_version"] = None
        return {
            "document_id": document_id,
            "simulated": True,
            "version": case[payload.kind + "_version"],
            "upload_url": f"/mock/expedientes/{case_id}/uploads/{document_id}/content",
        }

    @app.put(
        "/mock/expedientes/{case_id}/uploads/{document_id}/content", status_code=204
    )
    async def content(case_id: str, document_id: str, request: Request, owner: Owner):
        doc = owned(case_id, owner)["documents"].get(document_id)
        if doc is None:
            raise HTTPException(404, "Documento no encontrado")
        if doc["uploaded"]:
            raise HTTPException(409, "Carga inmutable; cree un nuevo documento")
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_BYTES:
                raise HTTPException(413, "Máximo 5 MiB")
            data.extend(chunk)
        if len(data) != doc["size_bytes"] or not data.startswith(b"%PDF-"):
            raise HTTPException(422, "Tamaño o cabecera PDF incorrectos")
        digest = hashlib.sha256(data).hexdigest()
        if doc["checksum_sha256"] and digest != doc["checksum_sha256"].lower():
            raise HTTPException(422, "Checksum incorrecto")
        if doc["uploaded"]:
            raise HTTPException(409, "Carga ya completada")
        doc["uploaded"], doc["sha256"] = True, digest
        # Se descartan los bytes: este mock solo conserva metadatos y hash.
        return Response(status_code=204)

    @app.post("/mock/expedientes/{case_id}/process", status_code=202)
    async def process(case_id: str, payload: ProcessInput, owner: Owner):
        case = owned(case_id, owner)
        docs = [
            d
            for d in case["documents"].values()
            if d["kind"] == payload.kind and d["active"]
        ]
        if not docs or not all(d["uploaded"] for d in docs):
            raise HTTPException(
                409, "Complete la carga de todos los archivos del grupo"
            )
        return enqueue(
            case, payload.kind, extract(docs, payload.kind), payload.simulate_failure
        )

    @app.post("/mock/expedientes/{case_id}/requirements/confirm")
    async def confirm(case_id: str, payload: Confirmation, owner: Owner):
        case = owned(case_id, owner)
        if case["bases_ready"] is None or payload.version != case["bases_version"]:
            raise HTTPException(409, "Procese y revise la versión actual de las bases")
        case["confirmed_version"] = payload.version
        return {"simulated": True, "confirmed_version": payload.version}

    @app.post("/mock/expedientes/{case_id}/evaluations", status_code=202)
    async def evaluate(case_id: str, owner: Owner):
        case = owned(case_id, owner)
        if (
            case["bases_ready"] is None
            or case["propuesta_ready"] is None
            or case["confirmed_version"] != case["bases_version"]
        ):
            raise HTTPException(
                409, "Debe procesar ambos grupos y confirmar las bases actuales"
            )
        result = {
            "simulated": True,
            "bases_version": case["bases_version"],
            "propuesta_version": case["propuesta_version"],
            "evaluated_at": datetime.now(UTC).isoformat(),
            "checks": compare(
                case["bases_ready"]["requirements"],
                case["propuesta_ready"]["documents"],
            ),
            "warning": "Evidencias simuladas. No certifica admisibilidad ni autenticidad de firmas.",
        }
        return enqueue(case, "evaluation", result)

    @app.get("/mock/jobs/{job_id}")
    async def get_job(job_id: str, owner: Owner):
        job = jobs.get(job_id)
        if job is None or job["owner"] != owner:
            raise HTTPException(404, "Trabajo no encontrado")
        if job["status"] in ("queued", "processing"):
            job["polls"] += 1
            if job["polls"] == 1:
                job["status"] = "processing"
            elif job["fail"]:
                job["status"] = "failed"
                job["error"] = {
                    "code": "simulated_processing_error",
                    "message": "Fallo simulado. Puede volver a solicitar el procesamiento.",
                }
            else:
                job["status"], job["result"] = "completed", job["snapshot"]
                case = cases[job["case_id"]]
                kind = job["kind"]
                if (
                    kind in ("bases", "propuesta")
                    and job[kind + "_version"] == case[kind + "_version"]
                ):
                    case[kind + "_ready"] = deepcopy(job["result"])
        return {
            key: job[key]
            for key in (
                "id",
                "kind",
                "status",
                "result",
                "error",
                "bases_version",
                "propuesta_version",
            )
        } | {
            "simulated": True,
            "progress": 50 if job["status"] == "processing" else 100,
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8013)
