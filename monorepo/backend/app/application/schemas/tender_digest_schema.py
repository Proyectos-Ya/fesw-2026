"""Esquemas de respuesta para el resumen de licitación (plan 233, decisión 4)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.application.use_cases.attachment_processing.get_tender_digest import (
    TenderDigestView,
)
from app.domain.entities.tender_digest import (
    CamposConsolidados,
    Discrepancia,
    EntregableConsolidado,
    FuenteDelResumen,
    ItemConsolidado,
    OtraCitaConsolidada,
    PuntoConsolidado,
    RequisitoConsolidado,
    ResumenDeAnexo,
    TenderDigestData,
)
from app.shared.datetime_utils import UtcDateTime


class TenderDigestResponse(BaseModel):
    tender_id: UUID
    status: Literal["ready", "empty"]
    scope: Literal["shared", "workspace"]
    version: int | None = None
    generated_at: UtcDateTime | None = None
    pending_sources: int = 0
    ai_generated: Literal[True] = True
    data: TenderDigestData | None = None
    campos: CamposConsolidados
    requisitos: list[RequisitoConsolidado] = Field(default_factory=list)
    items: list[ItemConsolidado] = Field(default_factory=list)
    entregables: list[EntregableConsolidado] = Field(default_factory=list)
    puntos_a_tener_en_cuenta: list[PuntoConsolidado] = Field(default_factory=list)
    resumenes: list[ResumenDeAnexo] = Field(default_factory=list)
    otras_citas: list[OtraCitaConsolidada] = Field(default_factory=list)
    discrepancias: list[Discrepancia] = Field(default_factory=list)
    fuentes: list[FuenteDelResumen] = Field(default_factory=list)

    @classmethod
    def desde_vista(cls, vista: TenderDigestView) -> "TenderDigestResponse":
        if vista.digest is None or vista.digest.source_count == 0:
            vacio = TenderDigestData.vacio()
            return cls(
                tender_id=vista.tender_id,
                status="empty",
                scope=vista.scope,
                version=None,
                generated_at=None,
                pending_sources=vista.pending_sources,
                ai_generated=True,
                data=vacio,
                campos=vacio.campos,
                requisitos=vacio.requisitos,
                items=vacio.items,
                entregables=vacio.entregables,
                puntos_a_tener_en_cuenta=vacio.puntos_a_tener_en_cuenta,
                resumenes=vacio.resumenes,
                otras_citas=vacio.otras_citas,
                discrepancias=vacio.discrepancias,
                fuentes=vacio.fuentes,
            )
        data = vista.digest.data
        return cls(
            tender_id=vista.tender_id,
            status="ready",
            scope=vista.scope,
            version=vista.digest.version,
            generated_at=vista.digest.created_at,
            pending_sources=vista.pending_sources,
            ai_generated=True,
            data=data,
            campos=data.campos,
            requisitos=data.requisitos,
            items=data.items,
            entregables=data.entregables,
            puntos_a_tener_en_cuenta=data.puntos_a_tener_en_cuenta,
            resumenes=data.resumenes,
            otras_citas=data.otras_citas,
            discrepancias=data.discrepancias,
            fuentes=data.fuentes,
        )
