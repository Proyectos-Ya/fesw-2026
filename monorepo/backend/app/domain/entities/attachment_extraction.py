"""Modelos de datos para la extracción de anexos con Gemini (plan 233, decisión 4)."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities.attachment_file import AttachmentTrust, AttachmentVisibility

EXTRACTION_PROMPT_VERSION = "anexos-v1"


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


_HORA = r"^([01]\d|2[0-3]):[0-5]\d$"


class Cita(_Modelo):
    documento: str = Field(min_length=1, max_length=255)
    pagina_u_hoja: str | None = Field(default=None, max_length=60)
    cita: str = Field(min_length=1, max_length=600)
    verificada: bool | None = None  # la calcula Chiripa; lo que mande el modelo se descarta


class _Citado(_Modelo):
    citas: list[Cita] = Field(min_length=1, max_length=5)


class FechaExtraida(_Citado):
    fecha: date
    hora: str | None = Field(default=None, pattern=_HORA)


class Presupuesto(_Citado):
    monto_clp: float | None = Field(default=None, ge=0, lt=1e13)
    incluye_iva: bool | None = None
    monto_texto: str = Field(min_length=1, max_length=200)


class Requisito(_Citado):
    descripcion: str = Field(min_length=1, max_length=600)
    tipo: Literal["administrativo", "tecnico", "economico", "legal", "otro"] = "otro"
    obligatorio: bool | None = None


class ItemExtraido(_Citado):
    descripcion: str = Field(min_length=1, max_length=600)
    cantidad: float | None = Field(default=None, ge=0)
    unidad: str | None = Field(default=None, max_length=60)


class VisitaTecnica(_Citado):
    obligatoria: bool | None = None
    fecha: date | None = None
    hora: str | None = Field(default=None, pattern=_HORA)
    lugar: str | None = Field(default=None, max_length=300)


class Entregable(_Citado):
    descripcion: str = Field(min_length=1, max_length=600)
    plazo: str | None = Field(default=None, max_length=200)


class PuntoATenerEnCuenta(_Citado):
    descripcion: str = Field(min_length=1, max_length=600)


class ResumenGeneral(_Citado):
    texto: str = Field(min_length=1, max_length=2000)


class OtraCita(_Citado):
    tema: str = Field(min_length=1, max_length=120)


class AttachmentExtractionData(_Modelo):
    presupuesto: Presupuesto | None = None
    fecha_publicacion: FechaExtraida | None = None
    fecha_cierre_primer_llamado: FechaExtraida | None = None
    fecha_cierre_segundo_llamado: FechaExtraida | None = None
    requisitos: list[Requisito] = Field(default_factory=list, max_length=40)
    items: list[ItemExtraido] = Field(default_factory=list, max_length=100)
    visita_tecnica: VisitaTecnica | None = None
    entregables: list[Entregable] = Field(default_factory=list, max_length=30)
    puntos_a_tener_en_cuenta: list[PuntoATenerEnCuenta] = Field(
        default_factory=list, max_length=15
    )
    resumen_general: ResumenGeneral
    otras_citas: list[OtraCita] = Field(default_factory=list, max_length=10)

    def todas_las_citas(self) -> Iterator[Cita]:
        """Recorre todas las citas en un orden determinista."""
        if self.presupuesto:
            yield from self.presupuesto.citas
        if self.fecha_publicacion:
            yield from self.fecha_publicacion.citas
        if self.fecha_cierre_primer_llamado:
            yield from self.fecha_cierre_primer_llamado.citas
        if self.fecha_cierre_segundo_llamado:
            yield from self.fecha_cierre_segundo_llamado.citas
        for req in self.requisitos:
            yield from req.citas
        for item in self.items:
            yield from item.citas
        if self.visita_tecnica:
            yield from self.visita_tecnica.citas
        for ent in self.entregables:
            yield from ent.citas
        for pto in self.puntos_a_tener_en_cuenta:
            yield from pto.citas
        yield from self.resumen_general.citas
        for otra in self.otras_citas:
            yield from otra.citas

    def con_documento(self, nombre: str) -> "AttachmentExtractionData":
        """Devuelve una copia profunda pisando el campo documento de todas las citas."""
        copia = self.model_copy(deep=True)
        for cita in copia.todas_las_citas():
            cita.documento = nombre
        return copia


class ExtractionInputMode(StrEnum):
    INLINE = "inline"
    FILES_API = "files_api"
    TEXT = "text"
    REUSED = "reused"


class AttachmentExtraction(BaseModel):
    id: UUID
    attachment_file_id: UUID
    tender_attachment_id: UUID
    tender_id: UUID
    sha256: str
    prompt_version: str
    model: str
    input_mode: ExtractionInputMode
    data: AttachmentExtractionData
    citas_total: int
    citas_verificadas: int
    texto_disponible: bool
    usage_metadata: dict[str, Any] | None = None
    reused_from_id: UUID | None = None
    created_at: datetime


@dataclass(frozen=True)
class FuenteDeExtraccion:
    """Una extracción con lo que el resumen necesita de su archivo y su anexo."""

    extraction_id: UUID
    attachment_file_id: UUID
    tender_attachment_id: UUID
    mp_document_id: int
    documento: str  # nombre oficial del anexo
    sha256: str
    visibility: AttachmentVisibility
    trust: AttachmentTrust
    workspace_id: UUID | None
    data: AttachmentExtractionData
    citas_total: int
    citas_verificadas: int
    texto_disponible: bool
    model: str
    prompt_version: str
    created_at: datetime
