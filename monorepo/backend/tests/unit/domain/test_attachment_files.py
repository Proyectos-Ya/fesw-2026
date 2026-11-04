"""Reglas puras de los archivos de anexos (plan 233, decisión 2).

Lo que más importa acá es la privacidad (`elegir_archivo_visible` jamás devuelve
el archivo privado de otra empresa), la validación contra el nombre oficial y el
mes del cupo, que tiene que ser el de Chile y no el del servidor.
"""

from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.domain.entities.attachment_file import (
    PLAZO_DE_SUBIDA_INCOMPLETA,
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.entities.tender_attachment import AttachmentStatus, OfficialAttachment
from app.domain.errors.attachment_errors import (
    AttachmentExtensionMismatch,
    AttachmentNameMismatch,
)
from app.domain.services.attachment_files import (
    clave_compartida,
    clave_privada,
    elegir_archivo_visible,
    estado_del_anexo,
    mes_de_cuota,
    tiene_archivo,
    tipo_de_contenido,
    validar_archivo_para_anexo,
)

WS = UUID("11111111-1111-1111-1111-111111111111")
OTRA = UUID("22222222-2222-2222-2222-222222222222")
T = UUID("33333333-3333-3333-3333-333333333333")
SHA = "b221d9dbb083a7f33428d7c2a3c3198ae925614d70210e28716ccaa7cd4ddb79"
AHORA = datetime(2026, 10, 3, 15, 0)


def _anexo(name: str, normalizado: str, ext: str) -> OfficialAttachment:
    return OfficialAttachment(
        id=uuid4(),
        tender_id=T,
        mp_document_id=1931002,
        name=name,
        name_normalized=normalizado,
        ext=ext,
        first_seen_at=AHORA,
        last_seen_at=AHORA,
    )


def _archivo(
    *,
    ws: UUID = WS,
    estado: AttachmentFileStatus = AttachmentFileStatus.STORED,
    visibilidad: AttachmentVisibility = AttachmentVisibility.PRIVATE,
    creado: datetime = AHORA,
) -> AttachmentFile:
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=uuid4(),
        tender_id=T,
        sha256=SHA,
        size_bytes=4,
        storage_key=f"private/{ws}/{SHA}.pdf",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=uuid4(),
        workspace_id=ws,
        visibility=visibilidad,
        status=estado,
        created_at=creado,
    )


def _canonico(
    *,
    estado: AttachmentFileStatus = AttachmentFileStatus.STORED,
    visibilidad: AttachmentVisibility = AttachmentVisibility.SHARED,
    confianza: AttachmentTrust = AttachmentTrust.CORROBORATED,
    creado: datetime = AHORA,
) -> AttachmentFile:
    """La versión compartida de un anexo: sin empresa ni autor (decisión 6)."""
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=uuid4(),
        tender_id=T,
        sha256=SHA,
        size_bytes=4,
        storage_key=f"shared/{T}/1931002/{SHA}.pdf",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=None,
        workspace_id=None,
        visibility=visibilidad,
        trust=confianza,
        status=estado,
        created_at=creado,
    )


# --- Claves de objeto ---


def test_clave_privada_con_extension() -> None:
    assert clave_privada(WS, SHA, "pdf") == f"private/{WS}/{SHA}.pdf"


def test_clave_privada_sin_extension() -> None:
    assert clave_privada(WS, SHA, "") == f"private/{WS}/{SHA}"


def test_clave_compartida() -> None:
    assert clave_compartida(T, 1931002, SHA, "pdf") == f"shared/{T}/1931002/{SHA}.pdf"


# --- Cupo ---


@pytest.mark.parametrize(
    ("instante", "esperado"),
    [
        # Septiembre en Chile todavía: UTC-3 en verano, así que 02:59 UTC es 23:59.
        (datetime(2026, 10, 1, 2, 59), date(2026, 9, 1)),
        (datetime(2026, 10, 1, 3, 0), date(2026, 10, 1)),
        # Invierno: UTC-4.
        (datetime(2026, 7, 1, 3, 59), date(2026, 6, 1)),
        (datetime(2026, 7, 1, 4, 0), date(2026, 7, 1)),
        (datetime(2027, 1, 1, 2, 59), date(2026, 12, 1)),
    ],
)
def test_mes_de_cuota_usa_hora_de_chile(instante: datetime, esperado: date) -> None:
    assert mes_de_cuota(instante) == esperado


# --- Tipo de contenido ---


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("application/pdf", "application/pdf"),
        ("APPLICATION/PDF", "application/pdf"),
        ("", "application/octet-stream"),
        # Inyección de cabeceras: el valor viaja firmado, no puede traer saltos de línea.
        ("text/html\r\nX-Evil: 1", "application/octet-stream"),
        (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    ],
)
def test_tipo_de_contenido(entrada: str, esperado: str) -> None:
    assert tipo_de_contenido(entrada) == esperado


# --- Validación contra el anexo oficial ---

XLSX = _anexo(
    "Anexo 3 Composición personalidad juridica.xlsx",
    "anexo 3 composicion personalidad juridica.xlsx",
    "xlsx",
)


def test_valida_un_archivo_descargado_del_navegador() -> None:
    validar_archivo_para_anexo(XLSX, "anexo 3 composicion personalidad juridica (1).XLSX")


def test_extension_distinta_se_acepta() -> None:
    validar_archivo_para_anexo(XLSX, "Anexo 3 Composición personalidad juridica.pdf")


def test_nombre_distinto_se_acepta() -> None:
    validar_archivo_para_anexo(XLSX, "Otro.xlsx")


def test_anexo_sin_extension() -> None:
    bases = _anexo("Bases", "bases", "")

    validar_archivo_para_anexo(bases, "bases (1)")
    validar_archivo_para_anexo(bases, "bases.pdf")


# --- Qué archivo ve cada empresa ---


def test_elegir_archivo_visible_prefiere_el_propio_antes_que_el_compartido() -> None:
    propio = _archivo()
    compartido = _canonico()

    assert elegir_archivo_visible([compartido, propio], WS) is propio


def test_elegir_archivo_visible_prefiere_el_compartido_antes_que_el_propio_subiendo() -> None:
    subiendo = _archivo(estado=AttachmentFileStatus.UPLOADING)
    compartido = _canonico()

    assert elegir_archivo_visible([subiendo, compartido], WS) is compartido


def test_elegir_archivo_visible_prefiere_subiendo_antes_que_rechazado() -> None:
    subiendo = _archivo(estado=AttachmentFileStatus.UPLOADING)
    rechazado = _archivo(estado=AttachmentFileStatus.REJECTED)

    assert elegir_archivo_visible([rechazado, subiendo], WS) is subiendo


def test_elegir_archivo_visible_entre_iguales_gana_el_mas_reciente() -> None:
    viejo = _archivo(creado=AHORA - timedelta(days=2))
    nuevo = _archivo(creado=AHORA)

    assert elegir_archivo_visible([nuevo, viejo], WS) is nuevo
    assert elegir_archivo_visible([viejo, nuevo], WS) is nuevo


def test_elegir_archivo_visible_nunca_elige_un_purgado() -> None:
    assert elegir_archivo_visible([_archivo(estado=AttachmentFileStatus.PURGED)], WS) is None


def test_elegir_archivo_visible_no_devuelve_el_privado_de_otra_empresa() -> None:
    ajeno = _archivo(ws=OTRA, visibilidad=AttachmentVisibility.PRIVATE)

    assert elegir_archivo_visible([ajeno], WS) is None
    assert elegir_archivo_visible([ajeno], None) is None


@pytest.mark.parametrize(
    "estado", [AttachmentFileStatus.UPLOADING, AttachmentFileStatus.REJECTED]
)
def test_elegir_archivo_visible_ignora_lo_compartido_que_no_esta_guardado(
    estado: AttachmentFileStatus,
) -> None:
    sin_guardar = _canonico(estado=estado)

    assert elegir_archivo_visible([sin_guardar], WS) is None


@pytest.mark.parametrize(
    "estado", [AttachmentFileStatus.UPLOADING, AttachmentFileStatus.REJECTED]
)
def test_elegir_archivo_visible_ignora_lo_que_otra_empresa_sube_o_le_rechazan(
    estado: AttachmentFileStatus,
) -> None:
    ajeno = _archivo(ws=OTRA, estado=estado)

    assert elegir_archivo_visible([ajeno], WS) is None


def test_elegir_archivo_visible_no_devuelve_una_canonica_oculta() -> None:
    # Suspendida por un conflicto o reemplazada: sin empresa, pero privada. Con
    # `workspace_id is None` a ambos lados, `None == None` la haría "propia".
    oculta = _canonico(
        visibilidad=AttachmentVisibility.PRIVATE, confianza=AttachmentTrust.CONFLICT
    )

    assert elegir_archivo_visible([oculta], WS) is None
    assert elegir_archivo_visible([oculta], None) is None


def test_elegir_archivo_visible_sin_empresa_solo_elige_compartidos() -> None:
    propio = _archivo()
    compartido = _canonico()

    assert elegir_archivo_visible([propio, compartido], None) is compartido
    assert elegir_archivo_visible([propio], None) is None


def test_elegir_archivo_visible_sin_candidatos() -> None:
    assert elegir_archivo_visible([], WS) is None


# --- Estado del anexo ---


@pytest.mark.parametrize(
    ("archivo_estado", "esperado"),
    [
        (None, AttachmentStatus.MISSING),
        (AttachmentFileStatus.PURGED, AttachmentStatus.MISSING),
        (AttachmentFileStatus.UPLOADING, AttachmentStatus.UPLOADING),
        (AttachmentFileStatus.STORED, AttachmentStatus.STORED),
        (AttachmentFileStatus.UNSUPPORTED, AttachmentStatus.UNSUPPORTED),
        (AttachmentFileStatus.REJECTED, AttachmentStatus.REJECTED),
    ],
)
def test_estado_del_anexo(
    archivo_estado: AttachmentFileStatus | None, esperado: AttachmentStatus
) -> None:
    archivo = None if archivo_estado is None else _archivo(estado=archivo_estado)

    assert estado_del_anexo(archivo) == esperado


def test_tiene_archivo_solo_con_stored_o_unsupported() -> None:
    con_archivo = {AttachmentFileStatus.STORED, AttachmentFileStatus.UNSUPPORTED}
    for estado in AttachmentFileStatus:
        assert tiene_archivo(_archivo(estado=estado)) is (estado in con_archivo)


# --- Transiciones ---


def test_transiciones() -> None:
    base = _archivo(estado=AttachmentFileStatus.REJECTED)
    usuario = uuid4()

    subiendo = base.como_subiendo(
        size_bytes=9, mime_declared="application/pdf", uploader_user_id=usuario, ahora=AHORA
    )
    assert subiendo.status == AttachmentFileStatus.UPLOADING
    assert subiendo.completed_at is None
    assert subiendo.purge_after == AHORA + PLAZO_DE_SUBIDA_INCOMPLETA
    assert subiendo.size_bytes == 9
    assert subiendo.mime_declared == "application/pdf"
    assert subiendo.uploader_user_id == usuario

    guardado = subiendo.como_guardado(ahora=AHORA)
    assert guardado.status == AttachmentFileStatus.STORED
    assert guardado.completed_at == AHORA
    assert guardado.purge_after is None

    rechazado = subiendo.como_rechazado(ahora=AHORA)
    assert rechazado.status == AttachmentFileStatus.REJECTED
    assert rechazado.completed_at == AHORA
    assert rechazado.purge_after == AHORA
    # El original no se muta.
    assert base.status == AttachmentFileStatus.REJECTED


def test_el_plazo_de_subida_incompleta_es_un_dia() -> None:
    assert PLAZO_DE_SUBIDA_INCOMPLETA == timedelta(hours=24)


def test_visible_para() -> None:
    privado = _archivo()
    compartido = _canonico()
    oculto = _canonico(
        visibilidad=AttachmentVisibility.PRIVATE, confianza=AttachmentTrust.REJECTED
    )

    assert privado.visible_para(WS) is True
    assert privado.visible_para(OTRA) is False
    assert privado.visible_para(None) is False
    assert compartido.visible_para(OTRA) is True
    assert compartido.visible_para(None) is True
    # Una canónica oculta no es de nadie: ni siquiera de quien no tiene empresa.
    assert oculto.visible_para(WS) is False
    assert oculto.visible_para(None) is False
