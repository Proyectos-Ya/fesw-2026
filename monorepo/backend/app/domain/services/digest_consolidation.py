"""Consolidación determinista del resumen de licitación y detección de discrepancias (plan 233, decisión 4)."""

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID

from app.domain.entities.attachment_extraction import (
    Cita,
    FuenteDeExtraccion,
    Requisito,
)
from app.domain.entities.attachment_file import AttachmentVisibility
from app.domain.entities.tender import Tender
from app.domain.entities.tender_digest import (
    DIGEST_ALGORITHM_VERSION,
    Alternativa,
    CampoConsolidado,
    CampoDeLaApi,
    CampoDelResumen,
    CamposConsolidados,
    CitaDeFuente,
    Discrepancia,
    EntregableConsolidado,
    FuenteDelResumen,
    ItemConsolidado,
    OtraCitaConsolidada,
    PuntoConsolidado,
    RequisitoConsolidado,
    ResumenDeAnexo,
    TenderDigestData,
    TipoDeDiscrepancia,
    ValorDeFecha,
    ValorDePresupuesto,
    ValorDeVisita,
)
from app.domain.errors.attachment_processing_errors import FuenteNoVisible
from app.domain.services.citation_verification import normalizar_para_citas
from app.shared.datetime_utils import CHILE_TZ, serialize_utc

TEMAS: dict[CampoDelResumen, str] = {
    "presupuesto": "Presupuesto",
    "fecha_publicacion": "Fecha de publicación",
    "fecha_cierre_primer_llamado": "Cierre del primer llamado",
    "fecha_cierre_segundo_llamado": "Cierre del segundo llamado",
    "visita_tecnica": "Visita técnica",
}


def deduplicar_fuentes(
    fuentes: Sequence[FuenteDeExtraccion],
) -> list[FuenteDeExtraccion]:
    """Quita duplicados por (tender_attachment_id, sha256), prefiriendo SHARED, y ordena."""
    por_contenido: dict[tuple[UUID, str], FuenteDeExtraccion] = {}
    for f in fuentes:
        clave = (f.tender_attachment_id, f.sha256)
        existente = por_contenido.get(clave)
        if existente is None:
            por_contenido[clave] = f
        elif (
            f.visibility == AttachmentVisibility.SHARED
            and existente.visibility != AttachmentVisibility.SHARED
        ):
            por_contenido[clave] = f

    return sorted(
        por_contenido.values(),
        key=lambda f: (
            normalizar_para_citas(f.documento),
            f.mp_document_id,
            str(f.attachment_file_id),
        ),
    )


def huella_del_conjunto(fuentes: Sequence[FuenteDeExtraccion]) -> str:
    """Calcula el hash SHA-256 del conjunto ordenado de extracciones."""
    lineas = [DIGEST_ALGORITHM_VERSION]
    elementos = [
        f"{f.tender_attachment_id}:{f.attachment_file_id}:{f.sha256}:{f.prompt_version}:{f.visibility.value}"
        for f in fuentes
    ]
    lineas.extend(sorted(elementos))
    return hashlib.sha256("\n".join(lineas).encode("utf-8")).hexdigest()


def foto_de_la_api(tender: Tender) -> dict[str, str | float | int | None]:
    """Foto de los campos clave de la licitación en la API, serializados a UTC."""
    return {
        "available_amount_clp": (
            float(tender.available_amount_clp)
            if tender.available_amount_clp is not None
            else None
        ),
        "published_at": (
            serialize_utc(tender.published_at) if tender.published_at else None
        ),
        "closing_at": (
            serialize_utc(tender.closing_at) if tender.closing_at else None
        ),
        "first_call_closing_at": (
            serialize_utc(tender.first_call_closing_at)
            if tender.first_call_closing_at
            else None
        ),
        "second_call_closing_at": (
            serialize_utc(tender.second_call_closing_at)
            if tender.second_call_closing_at
            else None
        ),
        "call_number": tender.call_number,
    }


def alcance_para(
    fuentes: Sequence[FuenteDeExtraccion], workspace_id: UUID | None
) -> UUID | None:
    """Devuelve workspace_id si hay fuentes privadas de esa empresa; si no, None (compartido)."""
    if workspace_id is None:
        return None
    for f in fuentes:
        if (
            f.visibility == AttachmentVisibility.PRIVATE
            and f.workspace_id == workspace_id
        ):
            return workspace_id
    return None


def exigir_privacidad(
    fuentes: Sequence[FuenteDeExtraccion], alcance: UUID | None
) -> None:
    """Defensa en profundidad: lanza FuenteNoVisible si se incluye una fuente ajena."""
    for f in fuentes:
        if f.visibility == AttachmentVisibility.PRIVATE:
            if alcance is None or f.workspace_id != alcance:
                raise FuenteNoVisible(f.extraction_id)


def _a_cita_fuente(cita: Cita, f: FuenteDeExtraccion) -> CitaDeFuente:
    return CitaDeFuente(
        documento=f.documento,
        pagina_u_hoja=cita.pagina_u_hoja,
        cita=cita.cita,
        verificada=bool(cita.verificada),
        anexo_id=f.tender_attachment_id,
        archivo_id=f.attachment_file_id,
    )


def _formatear_docs(documentos: Sequence[str]) -> str:
    nombres = [f"«{d}»" for d in dict.fromkeys(documentos)]
    if not nombres:
        return ""
    if len(nombres) == 1:
        return nombres[0]
    if len(nombres) == 2:
        return f"{nombres[0]} y {nombres[1]}"
    return f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def _formatear_monto(m: float) -> str:
    return f"${round(m):,}".replace(",", ".")


def _formatear_fecha(vf: ValorDeFecha) -> str:
    s = vf.fecha.strftime("%d-%m-%Y")
    return f"{s} {vf.hora}" if vf.hora else s


def _api_para(
    campo: str, t: Tender
) -> tuple[CampoDeLaApi, datetime | float] | None:
    if campo == "presupuesto":
        return (
            ("available_amount_clp", t.available_amount_clp)
            if t.available_amount_clp is not None
            else None
        )
    if campo == "fecha_publicacion":
        return ("published_at", t.published_at) if t.published_at else None
    if campo == "fecha_cierre_primer_llamado":
        if t.first_call_closing_at is not None:
            return ("first_call_closing_at", t.first_call_closing_at)
        return (
            ("closing_at", t.closing_at)
            if (t.closing_at and t.call_number in (None, 1))
            else None
        )
    if campo == "fecha_cierre_segundo_llamado":
        if t.second_call_closing_at is not None:
            return ("second_call_closing_at", t.second_call_closing_at)
        return (
            ("closing_at", t.closing_at)
            if (t.closing_at and t.call_number == 2)
            else None
        )
    return None


def _fecha_difiere(
    valor: ValorDeFecha, api_utc: datetime, *, con_hora: bool
) -> bool:
    local = api_utc.replace(tzinfo=UTC).astimezone(CHILE_TZ)
    if valor.fecha != local.date():
        return True
    return (
        con_hora
        and valor.hora is not None
        and valor.hora != local.strftime("%H:%M")
    )


def _formatear_api_fecha(api_utc: datetime, *, con_hora: bool) -> str:
    local = api_utc.replace(tzinfo=UTC).astimezone(CHILE_TZ)
    if con_hora:
        return local.strftime("%d-%m-%Y %H:%M")
    return local.strftime("%d-%m-%Y")


def _unir_citas(
    existentes: list[CitaDeFuente], nuevas: Sequence[CitaDeFuente]
) -> list[CitaDeFuente]:
    vistos = {
        (c.archivo_id, normalizar_para_citas(c.cita)) for c in existentes
    }
    resultado = list(existentes)
    for c in nuevas:
        k = (c.archivo_id, normalizar_para_citas(c.cita))
        if k not in vistos:
            vistos.add(k)
            resultado.append(c)
    return resultado


def consolidar(
    fuentes: Sequence[FuenteDeExtraccion], tender: Tender
) -> TenderDigestData:
    """Consolida las extracciones de una licitación en un resumen determinista."""
    if not fuentes:
        return TenderDigestData.vacio()

    fuentes = deduplicar_fuentes(fuentes)

    fuentes_resumen = [
        FuenteDelResumen(
            anexo_id=f.tender_attachment_id,
            archivo_id=f.attachment_file_id,
            documento=f.documento,
            visibilidad=f.visibility,
            citas_total=f.citas_total,
            citas_verificadas=f.citas_verificadas,
            texto_disponible=f.texto_disponible,
            modelo=f.model,
            prompt_version=f.prompt_version,
            procesado_en=f.created_at,
        )
        for f in fuentes
    ]

    resumenes = [
        ResumenDeAnexo(
            anexo_id=f.tender_attachment_id,
            documento=f.documento,
            texto=f.data.resumen_general.texto,
            citas=[_a_cita_fuente(c, f) for c in f.data.resumen_general.citas],
        )
        for f in fuentes
    ]

    # --- Consolidación de campos escalares ---
    # Presupuesto
    grupos_presupuesto: list[dict[str, Any]] = []
    for f in fuentes:
        p = f.data.presupuesto
        if p is None:
            continue
        citas_fuente = [_a_cita_fuente(c, f) for c in p.citas]
        clave = (
            ("monto_clp", round(p.monto_clp))
            if p.monto_clp is not None
            else ("monto_texto", normalizar_para_citas(p.monto_texto))
        )
        encontrado = False
        for g in grupos_presupuesto:
            if g["clave"] == clave:
                g["citas"] = _unir_citas(g["citas"], citas_fuente)
                encontrado = True
                break
        if not encontrado:
            grupos_presupuesto.append(
                {
                    "clave": clave,
                    "valor": ValorDePresupuesto(
                        monto_clp=p.monto_clp,
                        incluye_iva=p.incluye_iva,
                        monto_texto=p.monto_texto,
                    ),
                    "citas": citas_fuente,
                }
            )

    campo_presupuesto: CampoConsolidado[ValorDePresupuesto] | None = None
    if grupos_presupuesto:
        if len(grupos_presupuesto) == 1:
            g = grupos_presupuesto[0]
            campo_presupuesto = CampoConsolidado[ValorDePresupuesto](
                valor=g["valor"],
                en_conflicto=False,
                alternativas=[],
                citas=g["citas"],
            )
        else:
            todas_citas = []
            for g in grupos_presupuesto:
                todas_citas = _unir_citas(todas_citas, g["citas"])
            campo_presupuesto = CampoConsolidado[ValorDePresupuesto](
                valor=None,
                en_conflicto=True,
                alternativas=[
                    Alternativa(valor=g["valor"], citas=g["citas"])
                    for g in grupos_presupuesto
                ],
                citas=todas_citas,
            )

    # Fechas
    def _consolidar_fechas(
        campo_nombre: str,
    ) -> CampoConsolidado[ValorDeFecha] | None:
        elementos: list[tuple[ValorDeFecha, list[CitaDeFuente]]] = []
        for f in fuentes:
            fe = getattr(f.data, campo_nombre)
            if fe is None:
                continue
            elementos.append(
                (
                    ValorDeFecha(fecha=fe.fecha, hora=fe.hora),
                    [_a_cita_fuente(c, f) for c in fe.citas],
                )
            )
        if not elementos:
            return None

        # Agrupar por fecha primero
        por_fecha: dict[
            Any, list[tuple[ValorDeFecha, list[CitaDeFuente]]]
        ] = {}
        for vf, cits in elementos:
            por_fecha.setdefault(vf.fecha, []).append((vf, cits))

        grupos_fecha: list[dict[str, Any]] = []
        for fecha_val, sublista in sorted(por_fecha.items(), key=lambda x: x[0]):
            con_hora = [
                (vf, cits) for vf, cits in sublista if vf.hora is not None
            ]
            sin_hora = [(vf, cits) for vf, cits in sublista if vf.hora is None]
            horas_unicas = {vf.hora for vf, _ in con_hora}
            if len(horas_unicas) == 0:
                # Solo fechas sin hora
                citas_f: list[CitaDeFuente] = []
                for _, cs in sin_hora:
                    citas_f = _unir_citas(citas_f, cs)
                grupos_fecha.append(
                    {
                        "valor": ValorDeFecha(fecha=fecha_val, hora=None),
                        "citas": citas_f,
                    }
                )
            elif len(horas_unicas) == 1:
                # Una sola hora: la hora nula se funde
                hora_real = next(iter(horas_unicas))
                citas_f = []
                for _, cs in con_hora:
                    citas_f = _unir_citas(citas_f, cs)
                for _, cs in sin_hora:
                    citas_f = _unir_citas(citas_f, cs)
                grupos_fecha.append(
                    {
                        "valor": ValorDeFecha(fecha=fecha_val, hora=hora_real),
                        "citas": citas_f,
                    }
                )
            else:
                # Múltiples horas distintas: grupos distintos
                por_hora: dict[
                    str, list[tuple[ValorDeFecha, list[CitaDeFuente]]]
                ] = {}
                for vf, cs in con_hora:
                    por_hora.setdefault(vf.hora, []).append((vf, cs))  # type: ignore[arg-type]
                for h_val, h_sub in por_hora.items():
                    citas_f = []
                    for _, cs in h_sub:
                        citas_f = _unir_citas(citas_f, cs)
                    grupos_fecha.append(
                        {
                            "valor": ValorDeFecha(
                                fecha=fecha_val, hora=h_val
                            ),
                            "citas": citas_f,
                        }
                    )
                if sin_hora:
                    # Las sin hora van aparte
                    citas_f = []
                    for _, cs in sin_hora:
                        citas_f = _unir_citas(citas_f, cs)
                    grupos_fecha.append(
                        {
                            "valor": ValorDeFecha(fecha=fecha_val, hora=None),
                            "citas": citas_f,
                        }
                    )

        if len(grupos_fecha) == 1:
            g = grupos_fecha[0]
            return CampoConsolidado[ValorDeFecha](
                valor=g["valor"],
                en_conflicto=False,
                alternativas=[],
                citas=g["citas"],
            )
        todas_citas = []
        for g in grupos_fecha:
            todas_citas = _unir_citas(todas_citas, g["citas"])
        return CampoConsolidado[ValorDeFecha](
            valor=None,
            en_conflicto=True,
            alternativas=[
                Alternativa(valor=g["valor"], citas=g["citas"])
                for g in grupos_fecha
            ],
            citas=todas_citas,
        )

    campo_publicacion = _consolidar_fechas("fecha_publicacion")
    campo_cierre_1 = _consolidar_fechas("fecha_cierre_primer_llamado")
    campo_cierre_2 = _consolidar_fechas("fecha_cierre_segundo_llamado")

    # Visita técnica
    grupos_visita: list[dict[str, Any]] = []
    for f in fuentes:
        vt = f.data.visita_tecnica
        if vt is None:
            continue
        citas_fuente = [_a_cita_fuente(c, f) for c in vt.citas]
        clave_visita = (vt.obligatoria, vt.fecha, vt.hora)
        encontrado = False
        for g in grupos_visita:
            if g["clave"] == clave_visita:
                g["citas"] = _unir_citas(g["citas"], citas_fuente)
                encontrado = True
                break
        if not encontrado:
            grupos_visita.append(
                {
                    "clave": clave_visita,
                    "valor": ValorDeVisita(
                        obligatoria=vt.obligatoria,
                        fecha=vt.fecha,
                        hora=vt.hora,
                        lugar=vt.lugar,
                    ),
                    "citas": citas_fuente,
                }
            )

    campo_visita: CampoConsolidado[ValorDeVisita] | None = None
    if grupos_visita:
        if len(grupos_visita) == 1:
            g = grupos_visita[0]
            campo_visita = CampoConsolidado[ValorDeVisita](
                valor=g["valor"],
                en_conflicto=False,
                alternativas=[],
                citas=g["citas"],
            )
        else:
            todas_citas = []
            for g in grupos_visita:
                todas_citas = _unir_citas(todas_citas, g["citas"])
            campo_visita = CampoConsolidado[ValorDeVisita](
                valor=None,
                en_conflicto=True,
                alternativas=[
                    Alternativa(valor=g["valor"], citas=g["citas"])
                    for g in grupos_visita
                ],
                citas=todas_citas,
            )

    campos = CamposConsolidados(
        presupuesto=campo_presupuesto,
        fecha_publicacion=campo_publicacion,
        fecha_cierre_primer_llamado=campo_cierre_1,
        fecha_cierre_segundo_llamado=campo_cierre_2,
        visita_tecnica=campo_visita,
    )

    # --- Fusión de listas ---
    def _mismo_texto(a: str, b: str) -> bool:
        na, nb = normalizar_para_citas(a), normalizar_para_citas(b)
        if na == nb:
            return True
        tokens_a, tokens_b = na.split(), nb.split()
        if not tokens_a or not tokens_b:
            return False
        return (
            SequenceMatcher(
                None, tokens_a, tokens_b, autojunk=False
            ).ratio()
            >= 0.9
        )

    # Requisitos
    grupos_req: list[dict[str, Any]] = []
    for f in fuentes:
        for r in f.data.requisitos:
            citas_r = [_a_cita_fuente(c, f) for c in r.citas]
            encontrado = False
            for g in grupos_req:
                if _mismo_texto(g["descripcion"], r.descripcion):
                    g["citas"] = _unir_citas(g["citas"], citas_r)
                    if len(r.descripcion) > len(g["descripcion"]):
                        g["descripcion"] = r.descripcion
                    if r.obligatorio is True:
                        g["obligatorio"] = True
                    encontrado = True
                    break
            if not encontrado:
                grupos_req.append(
                    {
                        "descripcion": r.descripcion,
                        "tipo": r.tipo,
                        "obligatorio": r.obligatorio,
                        "citas": citas_r,
                    }
                )
    requisitos = [RequisitoConsolidado(**g) for g in grupos_req]

    # Items
    grupos_items: list[dict[str, Any]] = []
    for f in fuentes:
        for item in f.data.items:
            citas_it = [_a_cita_fuente(c, f) for c in item.citas]
            u_norm = (
                normalizar_para_citas(item.unidad) if item.unidad else None
            )
            encontrado = False
            for g in grupos_items:
                g_u_norm = (
                    normalizar_para_citas(g["unidad"]) if g["unidad"] else None
                )
                if (
                    g["cantidad"] == item.cantidad
                    and g_u_norm == u_norm
                    and _mismo_texto(g["descripcion"], item.descripcion)
                ):
                    g["citas"] = _unir_citas(g["citas"], citas_it)
                    if len(item.descripcion) > len(g["descripcion"]):
                        g["descripcion"] = item.descripcion
                    encontrado = True
                    break
            if not encontrado:
                grupos_items.append(
                    {
                        "descripcion": item.descripcion,
                        "cantidad": item.cantidad,
                        "unidad": item.unidad,
                        "citas": citas_it,
                    }
                )
    items = [ItemConsolidado(**g) for g in grupos_items]

    # Entregables
    grupos_entregables: list[dict[str, Any]] = []
    for f in fuentes:
        for ent in f.data.entregables:
            citas_ent = [_a_cita_fuente(c, f) for c in ent.citas]
            encontrado = False
            for g in grupos_entregables:
                if _mismo_texto(g["descripcion"], ent.descripcion):
                    g["citas"] = _unir_citas(g["citas"], citas_ent)
                    if len(ent.descripcion) > len(g["descripcion"]):
                        g["descripcion"] = ent.descripcion
                        if ent.plazo:
                            g["plazo"] = ent.plazo
                    encontrado = True
                    break
            if not encontrado:
                grupos_entregables.append(
                    {
                        "descripcion": ent.descripcion,
                        "plazo": ent.plazo,
                        "citas": citas_ent,
                    }
                )
    entregables = [EntregableConsolidado(**g) for g in grupos_entregables]

    # Puntos a tener en cuenta
    grupos_puntos: list[dict[str, Any]] = []
    for f in fuentes:
        for pto in f.data.puntos_a_tener_en_cuenta:
            citas_pto = [_a_cita_fuente(c, f) for c in pto.citas]
            encontrado = False
            for g in grupos_puntos:
                if _mismo_texto(g["descripcion"], pto.descripcion):
                    g["citas"] = _unir_citas(g["citas"], citas_pto)
                    if len(pto.descripcion) > len(g["descripcion"]):
                        g["descripcion"] = pto.descripcion
                    encontrado = True
                    break
            if not encontrado:
                grupos_puntos.append(
                    {"descripcion": pto.descripcion, "citas": citas_pto}
                )
    puntos = [PuntoConsolidado(**g) for g in grupos_puntos]

    # Otras citas
    grupos_otras: list[dict[str, Any]] = []
    for f in fuentes:
        for otra in f.data.otras_citas:
            citas_o = [_a_cita_fuente(c, f) for c in otra.citas]
            encontrado = False
            for g in grupos_otras:
                if _mismo_texto(g["tema"], otra.tema):
                    g["citas"] = _unir_citas(g["citas"], citas_o)
                    encontrado = True
                    break
            if not encontrado:
                grupos_otras.append({"tema": otra.tema, "citas": citas_o})
    otras_citas = [OtraCitaConsolidada(**g) for g in grupos_otras]

    # --- Detección de discrepancias ---
    discrepancias: list[Discrepancia] = []

    # 1. Presupuesto
    if campo_presupuesto:
        api_info = _api_para("presupuesto", tender)
        tema = TEMAS["presupuesto"]
        tema_minusc = tema.lower()
        if campo_presupuesto.en_conflicto:
            partes = []
            valores_anexos = []
            for alt in campo_presupuesto.alternativas:
                val_str = (
                    _formatear_monto(alt.valor.monto_clp)
                    if alt.valor.monto_clp is not None
                    else alt.valor.monto_texto
                )
                valores_anexos.append(val_str)
                docs = _formatear_docs([c.documento for c in alt.citas])
                verbo = "dice" if " y " not in docs and "," not in docs else "dicen"
                partes.append(f"{docs} {verbo} {val_str}")
            partes_str = "; ".join(partes)
            desc = f"Los anexos no coinciden en {tema_minusc}: {partes_str}."
            val_api_str = None
            if api_info and isinstance(api_info[1], (int, float)):
                val_api_str = _formatear_monto(api_info[1])
                desc += f" Mercado Público informa {val_api_str}."
            discrepancias.append(
                Discrepancia(
                    tipo=TipoDeDiscrepancia.ANEXO_VS_ANEXO,
                    campo="presupuesto",
                    tema=tema,
                    descripcion=desc,
                    campo_api=api_info[0] if api_info else None,
                    valor_api=val_api_str,
                    valores_anexos=valores_anexos,
                    fuentes=campo_presupuesto.citas,
                )
            )
        elif campo_presupuesto.valor and campo_presupuesto.valor.monto_clp is not None and api_info:
            api_monto = float(api_info[1])
            if abs(campo_presupuesto.valor.monto_clp - api_monto) >= 1:
                val_api_str = _formatear_monto(api_monto)
                val_anexo_str = _formatear_monto(campo_presupuesto.valor.monto_clp)
                docs = _formatear_docs([c.documento for c in campo_presupuesto.citas])
                verbo = "dice" if " y " not in docs and "," not in docs else "dicen"
                desc = f"Mercado Público informa {val_api_str} como {tema_minusc}, pero {docs} {verbo} {val_anexo_str}."
                discrepancias.append(
                    Discrepancia(
                        tipo=TipoDeDiscrepancia.ANEXO_VS_API,
                        campo="presupuesto",
                        tema=tema,
                        descripcion=desc,
                        campo_api=api_info[0],
                        valor_api=val_api_str,
                        valores_anexos=[val_anexo_str],
                        fuentes=campo_presupuesto.citas,
                    )
                )

    # 2. Fechas
    for campo_nom, con_hora in (
        ("fecha_publicacion", False),
        ("fecha_cierre_primer_llamado", True),
        ("fecha_cierre_segundo_llamado", True),
    ):
        cf: CampoConsolidado[ValorDeFecha] | None = getattr(campos, campo_nom)
        if not cf:
            continue
        api_info = _api_para(campo_nom, tender)
        tema = TEMAS[campo_nom]  # type: ignore[index]
        tema_minusc = tema.lower()

        if cf.en_conflicto:
            partes = []
            valores_anexos = []
            for alt in cf.alternativas:
                val_str = _formatear_fecha(alt.valor)
                valores_anexos.append(val_str)
                docs = _formatear_docs([c.documento for c in alt.citas])
                verbo = "dice" if " y " not in docs and "," not in docs else "dicen"
                partes.append(f"{docs} {verbo} {val_str}")
            partes_str = "; ".join(partes)
            desc = f"Los anexos no coinciden en {tema_minusc}: {partes_str}."
            val_api_str = None
            if api_info and isinstance(api_info[1], datetime):
                val_api_str = _formatear_api_fecha(api_info[1], con_hora=con_hora)
                desc += f" Mercado Público informa {val_api_str}."
            discrepancias.append(
                Discrepancia(
                    tipo=TipoDeDiscrepancia.ANEXO_VS_ANEXO,
                    campo=campo_nom,  # type: ignore[arg-type]
                    tema=tema,
                    descripcion=desc,
                    campo_api=api_info[0] if api_info else None,
                    valor_api=val_api_str,
                    valores_anexos=valores_anexos,
                    fuentes=cf.citas,
                )
            )
        elif cf.valor and api_info and isinstance(api_info[1], datetime):
            api_dt = api_info[1]
            if _fecha_difiere(cf.valor, api_dt, con_hora=con_hora):
                val_api_str = _formatear_api_fecha(api_dt, con_hora=con_hora)
                val_anexo_str = _formatear_fecha(cf.valor)
                docs = _formatear_docs([c.documento for c in cf.citas])
                verbo = "dice" if " y " not in docs and "," not in docs else "dicen"
                desc = f"Mercado Público informa {val_api_str} como {tema_minusc}, pero {docs} {verbo} {val_anexo_str}."
                discrepancias.append(
                    Discrepancia(
                        tipo=TipoDeDiscrepancia.ANEXO_VS_API,
                        campo=campo_nom,  # type: ignore[arg-type]
                        tema=tema,
                        descripcion=desc,
                        campo_api=api_info[0],
                        valor_api=val_api_str,
                        valores_anexos=[val_anexo_str],
                        fuentes=cf.citas,
                    )
                )

    return TenderDigestData(
        campos=campos,
        requisitos=requisitos,
        items=items,
        entregables=entregables,
        puntos_a_tener_en_cuenta=puntos,
        resumenes=resumenes,
        otras_citas=otras_citas,
        discrepancias=discrepancias,
        fuentes=fuentes_resumen,
    )
