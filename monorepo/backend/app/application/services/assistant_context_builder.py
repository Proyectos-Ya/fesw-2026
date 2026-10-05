"""Construcción de contexto textual optimizado para el asistente RAG (plan 233, decisión 5)."""

import hashlib
from typing import Sequence
from uuid import UUID

from app.domain.entities.attachment_extraction import FuenteDeExtraccion
from app.domain.entities.tender_chat import TenderChatDocument
from app.domain.entities.tender_digest import TenderDigestData

MAX_ATTACHMENT_TEXT_CHARS = 120_000


def deduplicar_documentos_chat(
    chat_docs: Sequence[TenderChatDocument],
    chat_bytes_by_id: dict[UUID, bytes],
    panel_sources: Sequence[FuenteDeExtraccion],
) -> list[TenderChatDocument]:
    """Descarta documentos del chat cuyo sha256 coincida con un anexo oficial del panel."""
    panel_hashes = {f.sha256.lower() for f in panel_sources}
    unicos: list[TenderChatDocument] = []
    for doc in chat_docs:
        b = chat_bytes_by_id.get(doc.id, b"")
        sha = hashlib.sha256(b).hexdigest().lower() if b else ""
        if sha not in panel_hashes:
            unicos.append(doc)
    return unicos


def construir_contexto_anexos(
    digest_data: TenderDigestData | None,
    sources: Sequence[FuenteDeExtraccion],
    legacy_docs: Sequence[tuple[TenderChatDocument, str]],  # (doc, texto_extraido)
) -> str:
    """Genera el bloque textual de antecedentes de anexos con citas para el prompt de Gemini."""
    lineas: list[str] = [
        "=== ANTECEDENTES Y BASES OFICIALES DE LA LICITACIÓN (PANEL DE DOCUMENTOS) ==="
    ]

    nombres_docs = [f.documento for f in sources]
    if nombres_docs:
        lineas.append(f"Documentos oficiales considerados: {', '.join(nombres_docs)}")

    if not digest_data and not legacy_docs:
        lineas.append("(No hay documentos o bases oficiales procesadas para esta licitación)")
        return "\n".join(lineas)

    if digest_data:
        # 1. Parámetros Clave
        lineas.append("\n--- PARÁMETROS PRINCIPALES Y FECHAS ---")
        if digest_data.campos.presupuesto and digest_data.campos.presupuesto.valor:
            p = digest_data.campos.presupuesto.valor
            citas_str = " ".join(
                f"[{c.documento}, Pág/Hoja: {c.pagina_u_hoja or 'N/A'}: \"{c.cita}\"]"
                for c in digest_data.campos.presupuesto.citas
            )
            lineas.append(f"- Presupuesto oficial estimado: {p.monto_texto} {citas_str}".strip())

        if digest_data.campos.fecha_publicacion and digest_data.campos.fecha_publicacion.valor:
            fp = digest_data.campos.fecha_publicacion.valor
            hora_str = f" {fp.hora}" if fp.hora else ""
            citas_str = " ".join(
                f"[{c.documento}: \"{c.cita}\"]"
                for c in digest_data.campos.fecha_publicacion.citas
            )
            lineas.append(f"- Fecha de publicación: {fp.fecha}{hora_str} {citas_str}".strip())

        if digest_data.campos.fecha_cierre_primer_llamado and digest_data.campos.fecha_cierre_primer_llamado.valor:
            fc = digest_data.campos.fecha_cierre_primer_llamado.valor
            hora_str = f" {fc.hora}" if fc.hora else ""
            citas_str = " ".join(
                f"[{c.documento}: \"{c.cita}\"]"
                for c in digest_data.campos.fecha_cierre_primer_llamado.citas
            )
            lineas.append(f"- Fecha de cierre (1.er llamado): {fc.fecha}{hora_str} {citas_str}".strip())

        if digest_data.campos.fecha_cierre_segundo_llamado and digest_data.campos.fecha_cierre_segundo_llamado.valor:
            fc2 = digest_data.campos.fecha_cierre_segundo_llamado.valor
            hora_str = f" {fc2.hora}" if fc2.hora else ""
            citas_str = " ".join(
                f"[{c.documento}: \"{c.cita}\"]"
                for c in digest_data.campos.fecha_cierre_segundo_llamado.citas
            )
            lineas.append(f"- Fecha de cierre (2.º llamado): {fc2.fecha}{hora_str} {citas_str}".strip())

        if digest_data.campos.visita_tecnica and digest_data.campos.visita_tecnica.valor:
            vt = digest_data.campos.visita_tecnica.valor
            ob_str = "Obligatoria" if vt.obligatoria else "Opcional / No obligatoria"
            lineas.append(f"- Visita a terreno: {ob_str}, Fecha: {vt.fecha or 'N/A'} {vt.hora or ''}, Lugar: {vt.lugar or 'N/A'}".strip())

        # 2. Discrepancias
        if digest_data.discrepancias:
            lineas.append("\n--- CONTRADICCIONES O DISCREPANCIAS DETECTADAS ---")
            for disc in digest_data.discrepancias:
                lineas.append(f"* [{disc.tema}] {disc.descripcion}")

        # 3. Requisitos
        if digest_data.requisitos:
            lineas.append("\n--- REQUISITOS HABILITANTES Y EXIGENCIAS ---")
            for req in digest_data.requisitos:
                ob = "[Obligatorio]" if req.obligatorio else "[Deseable]"
                citas = " ".join(f"[{c.documento}, Pág: {c.pagina_u_hoja or 'N/A'}]" for c in req.citas[:2])
                lineas.append(f"* {ob} ({req.tipo}): {req.descripcion} {citas}".strip())

        # 4. Ítems
        if digest_data.items:
            lineas.append("\n--- ÍTEMS SOLICITADOS ---")
            for it in digest_data.items[:25]:
                cant = f"{it.cantidad} {it.unidad or ''}".strip()
                cant_str = f" (Cantidad: {cant})" if cant else ""
                lineas.append(f"* {it.descripcion}{cant_str}")

        # 5. Entregables
        if digest_data.entregables:
            lineas.append("\n--- ENTREGABLES Y PLAZOS ---")
            for ent in digest_data.entregables[:15]:
                plazo_str = f" [Plazo: {ent.plazo}]" if ent.plazo else ""
                lineas.append(f"* {ent.descripcion}{plazo_str}")

        # 6. Puntos a tener en cuenta
        if digest_data.puntos_a_tener_en_cuenta:
            lineas.append("\n--- PUNTOS A TENER EN CUENTA ---")
            for pto in digest_data.puntos_a_tener_en_cuenta[:15]:
                lineas.append(f"* {pto.descripcion}")

        # 7. Resúmenes de documentos
        if digest_data.resumenes:
            lineas.append("\n--- RESÚMENES DE DOCUMENTOS ---")
            for r in digest_data.resumenes:
                lineas.append(f"* Documento '{r.documento}': {r.texto}")

    # Documentos legacy
    if legacy_docs:
        lineas.append("\n--- DOCUMENTOS ADJUNTOS HISTÓRICOS DEL CHAT ---")
        for doc, txt in legacy_docs:
            extracto = txt[:1000] if txt else "(Sin texto extraíble)"
            lineas.append(f"* Archivo '{doc.file_name}': {extracto}")

    resultado = "\n".join(lineas)
    if len(resultado) > MAX_ATTACHMENT_TEXT_CHARS:
        resultado = resultado[:MAX_ATTACHMENT_TEXT_CHARS] + "\n[... texto de anexos recortado por límite de contexto ...]"
    return resultado
