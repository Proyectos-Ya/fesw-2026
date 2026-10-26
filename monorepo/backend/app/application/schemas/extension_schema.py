"""Esquemas Pydantic para los contratos de la extensión de navegador (Plan 233, Decisión 7)."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ExtensionCapabilitiesResponse(BaseModel):
    """Capacidades operativas y parámetros de configuración para la extensión."""

    enabled: bool
    min_version: str = "0.1.0"
    latest_version: str = "0.1.0"
    mp_adapter_enabled: bool = True
    fetch_jobs_enabled: bool = True
    postulation_enabled: bool = False
    max_daily_fetches: int = 50
    polling_interval_seconds: int = 300
    supported_mp_hosts: list[str] = Field(
        default_factory=lambda: [
            "buscador.mercadopublico.cl",
            "adjunto.mercadopublico.cl",
        ]
    )
    message: str | None = None


class ExtensionPairingStartRequest(BaseModel):
    """Solicitud de inicio de vinculación web-extensión iniciada por la web."""

    browser: Literal["chrome", "firefox", "edge", "safari", "other"]
    extension_version: str


class ExtensionPairingStartResponse(BaseModel):
    """Ticket efímero generado para que la extensión confirme la vinculación."""

    pairing_ticket: str
    expires_in_seconds: int = 300


class ExtensionPairingConfirmRequest(BaseModel):
    """Confirmación enviada por la extensión con el ticket efímero recibido por el bridge."""

    pairing_ticket: str
    installation_id: UUID
    browser: Literal["chrome", "firefox", "edge", "safari", "other"]
    browser_version: str | None = None
    extension_version: str


class ExtensionPairingConfirmResponse(BaseModel):
    """Resultado de la confirmación de emparejamiento."""

    installation_id: UUID
    status: Literal["paired", "updated"]
    workspace_id: UUID | None
    capabilities: ExtensionCapabilitiesResponse


class ExtensionHeartbeatRequest(BaseModel):
    """Latido periódico enviado por la extensión para mantener su estado activo."""

    installation_id: UUID
    extension_version: str


class ExtensionHeartbeatResponse(BaseModel):
    """Respuesta al latido con capacidades actualizadas."""

    acknowledged: bool
    capabilities: ExtensionCapabilitiesResponse


class DocumentCheckItem(BaseModel):
    """Documento detectado por la extensión en la SPA de Mercado Público."""

    mp_document_id: str
    name: str


class ExtensionAttachmentCheckRequest(BaseModel):
    """Consulta de estado de una lista de documentos de una licitación."""

    tender_code: str
    documents: list[DocumentCheckItem]


class DocumentCheckStatus(BaseModel):
    """Estado de indexación de un documento de la licitación."""

    mp_document_id: str
    name: str
    attachment_id: UUID | None = None
    status: Literal["missing", "uploading", "stored", "rejected", "unsupported"] = "missing"
    exists: bool = False


class ExtensionAttachmentCheckResponse(BaseModel):
    """Respuesta con el estado consolidado de los documentos consultados."""

    tender_id: UUID | None = None
    tender_code: str
    documents: list[DocumentCheckStatus] = Field(default_factory=list)


class ExtensionJobLeaseRequest(BaseModel):
    """Solicitud de arrendamiento de una tarea de la cola distribuida."""

    installation_id: UUID


class ExtensionJobLeaseResponse(BaseModel):
    """Tarea asignada a la instalación con expiración de arrendamiento."""

    job_id: UUID
    tender_id: UUID
    tender_code: str
    lease_expires_at: datetime


class ExtensionJobResultRequest(BaseModel):
    """Reporte del resultado de ejecución de una tarea por parte de la extensión."""

    installation_id: UUID
    status: Literal["completed", "failed", "skipped"]
    error_code: str | None = None
    error_detail: str | None = None
    result_summary: dict[str, Any] | None = None


class ExtensionJobResultResponse(BaseModel):
    """Confirmación del backend de que el resultado fue registrado."""

    job_id: UUID
    status: str
    acknowledged: bool = True
