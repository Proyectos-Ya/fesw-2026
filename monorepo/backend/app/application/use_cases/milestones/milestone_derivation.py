"""Derivación determinista de hitos a partir de extracciones de anexos (plan 233, decisión 5)."""

from typing import Sequence
from uuid import UUID

from app.domain.entities.attachment_extraction import FuenteDeExtraccion
from app.domain.entities.tender_digest import TenderDigestData
from app.domain.entities.tender_milestone import MilestoneKind, MilestoneSource, TenderMilestone
from app.domain.services.milestone_date_normalizer import normalize_milestone_date


def derivar_hitos_desde_digest(
    digest_data: TenderDigestData,
    fuentes: Sequence[FuenteDeExtraccion],
    user_id: UUID,
    tender_id: UUID,
) -> list[TenderMilestone]:
    """Extrae hitos de manera inmediata y determinista desde los datos estructurados del digest."""
    hitos: list[TenderMilestone] = []
    fuente_por_doc = {
        f.documento: getattr(f, "archivo_id", getattr(f, "attachment_file_id", None))
        for f in fuentes
    }

    # 1. Publicación
    if digest_data.campos.fecha_publicacion and digest_data.campos.fecha_publicacion.valor:
        fp = digest_data.campos.fecha_publicacion.valor
        norm = normalize_milestone_date(str(fp.fecha), fp.hora)
        citas = digest_data.campos.fecha_publicacion.citas
        cita_doc = citas[0].documento if citas else None
        hitos.append(
            TenderMilestone(
                user_id=user_id,
                tender_id=tender_id,
                kind=MilestoneKind.PUBLICACION,
                title="Fecha de publicación en bases",
                description="Publicación estipulada en los documentos oficiales.",
                source=MilestoneSource.IA_DOCUMENTO,
                source_file_id=fuente_por_doc.get(cita_doc) if cita_doc else None,
                source_excerpt=citas[0].cita if citas else None,
                due_at=norm.due_at,
                has_time=norm.has_time,
            )
        )

    # 2. Cierre Primer Llamado
    if digest_data.campos.fecha_cierre_primer_llamado and digest_data.campos.fecha_cierre_primer_llamado.valor:
        fc1 = digest_data.campos.fecha_cierre_primer_llamado.valor
        norm = normalize_milestone_date(str(fc1.fecha), fc1.hora)
        citas = digest_data.campos.fecha_cierre_primer_llamado.citas
        cita_doc = citas[0].documento if citas else None
        hitos.append(
            TenderMilestone(
                user_id=user_id,
                tender_id=tender_id,
                kind=MilestoneKind.CIERRE_POSTULACION,
                title="Cierre de ofertas (1.er llamado)",
                description="Plazo límite para presentar ofertas estipulado en bases.",
                source=MilestoneSource.IA_DOCUMENTO,
                source_file_id=fuente_por_doc.get(cita_doc) if cita_doc else None,
                source_excerpt=citas[0].cita if citas else None,
                due_at=norm.due_at,
                has_time=norm.has_time,
            )
        )

    # 3. Cierre Segundo Llamado
    if digest_data.campos.fecha_cierre_segundo_llamado and digest_data.campos.fecha_cierre_segundo_llamado.valor:
        fc2 = digest_data.campos.fecha_cierre_segundo_llamado.valor
        norm = normalize_milestone_date(str(fc2.fecha), fc2.hora)
        citas = digest_data.campos.fecha_cierre_segundo_llamado.citas
        cita_doc = citas[0].documento if citas else None
        hitos.append(
            TenderMilestone(
                user_id=user_id,
                tender_id=tender_id,
                kind=MilestoneKind.CIERRE_SEGUNDO_LLAMADO,
                title="Cierre de ofertas (2.º llamado)",
                description="Plazo límite para presentar ofertas en segundo llamado según bases.",
                source=MilestoneSource.IA_DOCUMENTO,
                source_file_id=fuente_por_doc.get(cita_doc) if cita_doc else None,
                source_excerpt=citas[0].cita if citas else None,
                due_at=norm.due_at,
                has_time=norm.has_time,
            )
        )

    # 4. Visita Técnica
    if digest_data.campos.visita_tecnica and digest_data.campos.visita_tecnica.valor:
        vt = digest_data.campos.visita_tecnica.valor
        if vt.fecha:
            norm = normalize_milestone_date(str(vt.fecha), vt.hora)
            citas = digest_data.campos.visita_tecnica.citas
            cita_doc = citas[0].documento if citas else None
            desc = f"Visita a terreno {'obligatoria' if vt.obligatoria else 'opcional'}."
            if vt.lugar:
                desc += f" Lugar: {vt.lugar}."
            hitos.append(
                TenderMilestone(
                    user_id=user_id,
                    tender_id=tender_id,
                    kind=MilestoneKind.VISITA_TECNICA,
                    title="Visita técnica a terreno",
                    description=desc,
                    source=MilestoneSource.IA_DOCUMENTO,
                    source_file_id=fuente_por_doc.get(cita_doc) if cita_doc else None,
                    source_excerpt=citas[0].cita if citas else None,
                    due_at=norm.due_at,
                    has_time=norm.has_time,
                )
            )

    return hitos
