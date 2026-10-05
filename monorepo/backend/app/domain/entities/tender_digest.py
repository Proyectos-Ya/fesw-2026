"""Modelos de datos para el resumen consolidado de anexos (plan 233, decisión 4)."""

from datetime import date
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.attachment_file import AttachmentVisibility
from app.shared.datetime_utils import UtcDateTime

DIGEST_ALGORITHM_VERSION = "resumen-v1"

CampoDelResumen = Literal[
    "presupuesto",
    "fecha_publicacion",
    "fecha_cierre_primer_llamado",
    "fecha_cierre_segundo_llamado",
    "visita_tecnica",
]
CampoDeLaApi = Literal[
    "available_amount_clp",
    "published_at",
    "first_call_closing_at",
    "second_call_closing_at",
    "closing_at",
]



class CitaDeFuente(BaseModel):
    documento: str
    pagina_u_hoja: str | None = None
    cita: str
    verificada: bool
    anexo_id: UUID
    archivo_id: UUID


class ValorDeFecha(BaseModel):
    fecha: date
    hora: str | None = None


class ValorDePresupuesto(BaseModel):
    monto_clp: float | None = None
    incluye_iva: bool | None = None
    monto_texto: str


class ValorDeVisita(BaseModel):
    obligatoria: bool | None = None
    fecha: date | None = None
    hora: str | None = None
    lugar: str | None = None


class Alternativa[T](BaseModel):
    valor: T
    citas: list[CitaDeFuente]


class CampoConsolidado[T](BaseModel):
    valor: T | None
    en_conflicto: bool = False
    alternativas: list[Alternativa[T]] = Field(default_factory=list)  # solo con conflicto
    citas: list[CitaDeFuente]


class CamposConsolidados(BaseModel):
    presupuesto: CampoConsolidado[ValorDePresupuesto] | None = None
    fecha_publicacion: CampoConsolidado[ValorDeFecha] | None = None
    fecha_cierre_primer_llamado: CampoConsolidado[ValorDeFecha] | None = None
    fecha_cierre_segundo_llamado: CampoConsolidado[ValorDeFecha] | None = None
    visita_tecnica: CampoConsolidado[ValorDeVisita] | None = None


class RequisitoConsolidado(BaseModel):
    descripcion: str
    tipo: str
    obligatorio: bool | None = None
    citas: list[CitaDeFuente]


class ItemConsolidado(BaseModel):
    descripcion: str
    cantidad: float | None = None
    unidad: str | None = None
    citas: list[CitaDeFuente]


class EntregableConsolidado(BaseModel):
    descripcion: str
    plazo: str | None = None
    citas: list[CitaDeFuente]


class PuntoConsolidado(BaseModel):
    descripcion: str
    citas: list[CitaDeFuente]


class ResumenDeAnexo(BaseModel):
    anexo_id: UUID
    documento: str
    texto: str
    citas: list[CitaDeFuente]


class OtraCitaConsolidada(BaseModel):
    tema: str
    citas: list[CitaDeFuente]


class TipoDeDiscrepancia(StrEnum):
    ANEXO_VS_ANEXO = "anexo_vs_anexo"
    ANEXO_VS_API = "anexo_vs_api"


class Discrepancia(BaseModel):
    tipo: TipoDeDiscrepancia
    campo: CampoDelResumen
    tema: str
    descripcion: str
    campo_api: CampoDeLaApi | None = None
    valor_api: str | None = None
    valores_anexos: list[str]
    fuentes: list[CitaDeFuente]


class FuenteDelResumen(BaseModel):
    anexo_id: UUID
    archivo_id: UUID
    documento: str
    visibilidad: AttachmentVisibility
    citas_total: int
    citas_verificadas: int
    texto_disponible: bool
    modelo: str
    prompt_version: str
    procesado_en: UtcDateTime


class TenderDigestData(BaseModel):
    campos: CamposConsolidados
    requisitos: list[RequisitoConsolidado]
    items: list[ItemConsolidado]
    entregables: list[EntregableConsolidado]
    puntos_a_tener_en_cuenta: list[PuntoConsolidado]
    resumenes: list[ResumenDeAnexo]
    otras_citas: list[OtraCitaConsolidada]
    discrepancias: list[Discrepancia]
    fuentes: list[FuenteDelResumen]

    @classmethod
    def vacio(cls) -> "TenderDigestData":
        return cls(
            campos=CamposConsolidados(),
            requisitos=[],
            items=[],
            entregables=[],
            puntos_a_tener_en_cuenta=[],
            resumenes=[],
            otras_citas=[],
            discrepancias=[],
            fuentes=[],
        )


class TenderDigest(BaseModel):
    id: UUID
    tender_id: UUID
    workspace_id: UUID | None = None  # None = compartido
    version: int
    extraction_set_hash: str
    is_current: bool
    source_count: int
    data: TenderDigestData
    api_snapshot: dict[str, str | float | int | None]
    created_at: UtcDateTime
