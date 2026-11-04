"""Qué versión de un anexo se comparte entre empresas (plan 233, decisión 6).

`decidir_confianza` es una función pura: acá se prueba como una tabla de verdad.
Lo que más importa es la privacidad: una subida suelta no puede cambiar de estado
por lo que haya subido otra empresa (sería un oráculo de existencia de los
privados ajenos), y lo ya compartido no se baja con cuentas títere.
"""

from datetime import datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.services.attachment_trust import (
    DecisionDeConfianza,
    EstadoCanonico,
    decidir_confianza,
    es_propio,
    fuentes_para_copiar,
    visibilidad_efectiva,
)

X = uuid4()
T = uuid4()
W1, W2, W3, W4, W5, W6 = (uuid4() for _ in range(6))
U1, U2, U3, U4, U5, U6, U7, U8, U9 = (uuid4() for _ in range(9))
S1 = sha256(b"hola").hexdigest()
S2 = sha256(b"chao").hexdigest()
AHORA = datetime(2026, 10, 3, 15, 0)

PERSONAS = {
    W1: frozenset({U1}),
    W2: frozenset({U2}),
    W3: frozenset({U3}),
    W4: frozenset({U4}),
    W5: frozenset({U5}),
    W6: frozenset({U6}),
}
AUTOR = {W1: U1, W2: U2, W3: U3, W4: U4, W5: U5, W6: U6}

MANUAL = AttachmentFileSource.MANUAL
EXTENSION = AttachmentFileSource.EXTENSION
PRIVATE = AttachmentVisibility.PRIVATE
SHARED = AttachmentVisibility.SHARED
PENDING = AttachmentTrust.PENDING
CORROBORATED = AttachmentTrust.CORROBORATED
CONFLICT = AttachmentTrust.CONFLICT
REJECTED = AttachmentTrust.REJECTED
STORED = AttachmentFileStatus.STORED


def aporte(
    ws: UUID,
    sha: str,
    *,
    fuente: AttachmentFileSource = MANUAL,
    autor: UUID | None = None,
    status: AttachmentFileStatus = STORED,
    completado: datetime = AHORA,
    trust: AttachmentTrust = PENDING,
) -> AttachmentFile:
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=X,
        tender_id=T,
        sha256=sha,
        size_bytes=4,
        storage_key=f"private/{ws}/{sha}.xlsx",
        source=fuente,
        uploader_user_id=autor or AUTOR[ws],
        workspace_id=ws,
        trust=trust,
        status=status,
        created_at=completado - timedelta(minutes=1),
        completed_at=completado,
    )


def canonico(
    sha: str,
    *,
    vis: AttachmentVisibility = SHARED,
    trust: AttachmentTrust = CORROBORATED,
    creado: datetime = AHORA,
) -> AttachmentFile:
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=X,
        tender_id=T,
        sha256=sha,
        size_bytes=4,
        storage_key=f"shared/{T}/1931002/{sha}.xlsx",
        source=MANUAL,
        uploader_user_id=None,
        workspace_id=None,
        visibility=vis,
        trust=trust,
        status=STORED,
        created_at=creado,
        completed_at=creado,
    )


def decidir(*filas: AttachmentFile, personas=PERSONAS) -> DecisionDeConfianza:
    return decidir_confianza(filas, personas)


# --- Subidas sueltas y corroboración entre empresas ---


def test_una_subida_sola_queda_pendiente():
    w1 = aporte(W1, S1)

    d = decidir(w1)

    assert d.ganador is None
    assert d.en_conflicto is False
    assert d.aportes == {w1.id: PENDING}
    assert d.crear_canonico is None


def test_dos_empresas_independientes_con_el_mismo_sha_se_comparten():
    w1, w2 = aporte(W1, S1), aporte(W2, S1)

    d = decidir(w1, w2)

    assert d.ganador == S1
    assert d.crear_canonico == S1
    assert d.en_conflicto is False
    assert d.aportes == {w1.id: CORROBORATED, w2.id: CORROBORATED}


def test_la_misma_empresa_no_se_corrobora():
    # Un archivo manual y uno migrado del chat de la misma empresa, con autores distintos.
    w1 = aporte(W1, S1, autor=U1)
    w1_chat = aporte(W1, S1, fuente=AttachmentFileSource.LEGACY_CHAT, autor=U8)

    d = decidir(w1, w1_chat)

    assert d.ganador is None
    assert d.aportes == {w1.id: PENDING, w1_chat.id: PENDING}
    assert d.crear_canonico is None


def test_empresas_que_comparten_una_persona_no_son_independientes():
    personas = {W1: frozenset({U1, U9}), W2: frozenset({U2, U9})}
    w1, w2 = aporte(W1, S1), aporte(W2, S1)

    d = decidir(w1, w2, personas=personas)

    assert d.ganador is None
    assert d.aportes == {w1.id: PENDING, w2.id: PENDING}


def test_una_persona_revocada_tambien_cuenta_como_persona_de_la_empresa():
    # `people` ya incluye las membresías en cualquier estado: la regla es solo de conjuntos.
    personas = {W1: frozenset({U1, U8}), W2: frozenset({U2, U8})}

    d = decidir(aporte(W1, S1), aporte(W2, S1), personas=personas)

    assert d.ganador is None


def test_el_mismo_autor_en_dos_empresas_no_se_corrobora():
    w1, w2 = aporte(W1, S1, autor=U7), aporte(W2, S1, autor=U7)

    d = decidir(w1, w2, personas={})

    assert d.ganador is None
    assert d.aportes == {w1.id: PENDING, w2.id: PENDING}


# --- La extensión ---


def test_la_extension_corrobora_una_subida_manual():
    w1, w5 = aporte(W1, S1), aporte(W5, S1, fuente=EXTENSION)

    d = decidir(w1, w5)

    assert d.ganador == S1
    assert d.crear_canonico == S1
    assert d.aportes == {w1.id: CORROBORATED, w5.id: CORROBORATED}


def test_la_extension_corrobora_aunque_las_empresas_compartan_personas():
    # La captura de la extensión es otro canal: no depende de quién tenga acceso a qué.
    personas = {W1: frozenset({U1, U9}), W5: frozenset({U5, U9})}

    d = decidir(aporte(W1, S1), aporte(W5, S1, fuente=EXTENSION), personas=personas)

    assert d.ganador == S1


def test_la_extension_no_corrobora_a_la_misma_persona():
    w1 = aporte(W1, S1, autor=U1)
    w5 = aporte(W5, S1, fuente=EXTENSION, autor=U1)

    d = decidir(w1, w5)

    assert d.ganador is None
    assert d.aportes == {w1.id: PENDING, w5.id: PENDING}


def test_una_captura_sola_de_la_extension_no_se_comparte():
    w5 = aporte(W5, S1, fuente=EXTENSION)

    d = decidir(w5)

    assert d.ganador is None
    assert d.en_conflicto is False
    assert d.aportes == {w5.id: PENDING}
    assert d.crear_canonico is None


def test_solo_cuentan_archivos_guardados():
    w1 = aporte(W1, S1)
    subiendo = aporte(W2, S1, status=AttachmentFileStatus.UPLOADING)

    d = decidir(w1, subiendo)

    assert d.ganador is None
    assert d.aportes == {w1.id: PENDING, subiendo.id: PENDING}


def test_un_archivo_no_soportado_si_cuenta_porque_tiene_archivo():
    w1 = aporte(W1, S1)
    ilegible = aporte(W2, S1, status=AttachmentFileStatus.UNSUPPORTED)

    d = decidir(w1, ilegible)

    assert d.ganador == S1
    assert d.aportes == {w1.id: CORROBORATED, ilegible.id: CORROBORATED}


# --- Versiones distintas ---


def test_dos_subidas_sueltas_distintas_no_se_ven():
    # Si W1 "viera" que W2 subió otra cosa, subir cualquier archivo serviría para
    # averiguar si otra empresa trabaja esa licitación.
    w1, w2 = aporte(W1, S1), aporte(W2, S2)

    d = decidir(w1, w2)

    assert d.en_conflicto is False
    assert d.ganador is None
    assert d.aportes == {w1.id: PENDING, w2.id: PENDING}


def test_una_subida_suelta_distinta_no_bloquea_lo_corroborado():
    w1, w2, w3 = aporte(W1, S1), aporte(W2, S1), aporte(W3, S2)

    d = decidir(w1, w2, w3)

    assert d.ganador == S1
    assert d.en_conflicto is False
    assert d.aportes == {w1.id: CORROBORATED, w2.id: CORROBORATED, w3.id: REJECTED}


def test_dos_versiones_respaldadas_quedan_en_conflicto():
    filas = [aporte(W1, S1), aporte(W2, S1), aporte(W3, S2), aporte(W4, S2)]

    d = decidir(*filas)

    assert d.en_conflicto is True
    assert d.ganador is None
    assert d.crear_canonico is None
    assert set(d.aportes.values()) == {CONFLICT}
    assert len(d.aportes) == 4


def test_la_extension_resuelve_el_conflicto():
    w1, w2, w3, w4 = aporte(W1, S1), aporte(W2, S1), aporte(W3, S2), aporte(W4, S2)
    w5 = aporte(W5, S1, fuente=EXTENSION)

    d = decidir(w1, w2, w3, w4, w5)

    assert d.ganador == S1
    assert d.en_conflicto is False
    assert d.aportes == {
        w1.id: CORROBORATED,
        w2.id: CORROBORATED,
        w5.id: CORROBORATED,
        w3.id: REJECTED,
        w4.id: REJECTED,
    }


def test_la_extension_resuelve_dos_sueltas():
    w1, w2 = aporte(W1, S1), aporte(W2, S2)
    w5 = aporte(W5, S1, fuente=EXTENSION)

    d = decidir(w1, w2, w5)

    assert d.ganador == S1
    assert d.aportes == {w1.id: CORROBORATED, w5.id: CORROBORATED, w2.id: REJECTED}


def test_la_extension_contradice_lo_corroborado():
    w1, w2 = aporte(W1, S1), aporte(W2, S1)
    w5 = aporte(W5, S2, fuente=EXTENSION)

    d = decidir(w1, w2, w5)

    assert d.en_conflicto is True
    assert d.ganador is None
    assert set(d.aportes.values()) == {CONFLICT}


def test_la_extension_se_contradice():
    w5 = aporte(W5, S1, fuente=EXTENSION)
    w6 = aporte(W6, S2, fuente=EXTENSION)
    w1 = aporte(W1, S1)

    d = decidir(w5, w6, w1)

    assert d.en_conflicto is True
    assert d.ganador is None
    assert d.aportes == {w5.id: CONFLICT, w6.id: CONFLICT, w1.id: CONFLICT}


# --- Lo ya compartido es pegajoso ---


def test_lo_compartido_se_mantiene_sin_aportes():
    c = canonico(S1)

    d = decidir(c)

    assert d.ganador == S1
    assert d.en_conflicto is False
    assert d.canonicos[c.id] == EstadoCanonico(SHARED, CORROBORATED)
    assert d.crear_canonico is None


def test_dos_empresas_no_descomparten():
    c = canonico(S1)
    w3, w4 = aporte(W3, S2), aporte(W4, S2)

    d = decidir(c, w3, w4)

    assert d.ganador == S1
    assert d.aportes == {w3.id: REJECTED, w4.id: REJECTED}
    assert d.canonicos[c.id] == EstadoCanonico(SHARED, CORROBORATED)
    assert d.crear_canonico is None


def test_la_extension_suspende_lo_compartido():
    c = canonico(S1)
    w5 = aporte(W5, S2, fuente=EXTENSION)

    d = decidir(c, w5)

    assert d.en_conflicto is True
    assert d.ganador is None
    assert d.canonicos[c.id] == EstadoCanonico(PRIVATE, CONFLICT)
    assert d.aportes == {w5.id: CONFLICT}


def test_la_extension_confirma_una_version_nueva():
    c = canonico(S1)
    w5 = aporte(W5, S2, fuente=EXTENSION)
    w3 = aporte(W3, S2)

    d = decidir(c, w5, w3)

    assert d.ganador == S2
    assert d.crear_canonico == S2
    assert d.aportes == {w5.id: CORROBORATED, w3.id: CORROBORATED}
    assert d.canonicos[c.id] == EstadoCanonico(PRIVATE, REJECTED)


def test_un_suspendido_vuelve():
    c = canonico(S1, vis=PRIVATE, trust=CONFLICT)
    w5 = aporte(W5, S1, fuente=EXTENSION)

    d = decidir(c, w5)

    assert d.ganador == S1
    assert d.canonicos[c.id] == EstadoCanonico(SHARED, CORROBORATED)
    assert d.crear_canonico is None
    assert d.aportes == {w5.id: CORROBORATED}


def test_un_rechazado_que_vuelve_a_ganar_reusa_su_fila():
    viejo = canonico(S1, vis=PRIVATE, trust=REJECTED)
    vigente = canonico(S2)
    w5 = aporte(W5, S1, fuente=EXTENSION)
    w1 = aporte(W1, S1)

    d = decidir(viejo, vigente, w5, w1)

    assert d.ganador == S1
    assert d.crear_canonico is None
    assert d.canonicos[viejo.id] == EstadoCanonico(SHARED, CORROBORATED)
    assert d.canonicos[vigente.id] == EstadoCanonico(PRIVATE, REJECTED)


def test_una_canonica_suspendida_sin_ayuda_sigue_suspendida():
    # Suspendida por la extensión, que desde entonces desapareció: no se resuelve sola.
    c = canonico(S1, vis=PRIVATE, trust=CONFLICT)
    w5 = aporte(W5, S2, fuente=EXTENSION)

    d = decidir(c, w5)

    assert d.en_conflicto is True
    assert d.canonicos[c.id] == EstadoCanonico(PRIVATE, CONFLICT)


def test_es_idempotente_con_el_resultado_ya_aplicado():
    # Aplicar la decisión y volver a decidir no cambia nada: no hay estados intermedios.
    w1, w2 = aporte(W1, S1), aporte(W2, S1)
    primera = decidir(w1, w2)
    aplicados = [
        w1.model_copy(update={"trust": primera.aportes[w1.id]}),
        w2.model_copy(update={"trust": primera.aportes[w2.id]}),
        canonico(S1),
    ]

    segunda = decidir(*aplicados)

    assert segunda.ganador == S1
    assert segunda.crear_canonico is None
    assert segunda.aportes == primera.aportes


# --- Visibilidad efectiva y pertenencia ---


def test_visibilidad_efectiva():
    assert visibilidad_efectiva(aporte(W1, S1, trust=CORROBORATED)) == SHARED
    for trust in (PENDING, CONFLICT, REJECTED):
        assert visibilidad_efectiva(aporte(W1, S1, trust=trust)) == PRIVATE
    # Sin archivo no hay nada que compartir, aunque la confianza diga lo contrario.
    sin_archivo = aporte(W1, S1, trust=CORROBORATED, status=AttachmentFileStatus.REJECTED)
    assert visibilidad_efectiva(sin_archivo) == PRIVATE
    assert visibilidad_efectiva(canonico(S1)) == SHARED
    assert visibilidad_efectiva(canonico(S1, vis=PRIVATE, trust=CONFLICT)) == PRIVATE


def test_es_propio():
    canonica = canonico(S1)
    de_w1 = aporte(W1, S1)

    # Nunca `workspace_id == workspace_id` a secas: None == None.
    assert es_propio(canonica, None) is False
    assert es_propio(de_w1, W1) is True
    assert es_propio(de_w1, W2) is False
    assert es_propio(de_w1, None) is False


def test_fuentes_para_copiar():
    antigua = aporte(W1, S1, completado=AHORA - timedelta(hours=2))
    reciente = aporte(W2, S1, completado=AHORA - timedelta(hours=1))
    de_la_extension = aporte(W5, S1, fuente=EXTENSION, completado=AHORA)
    otro_sha = aporte(W3, S2)
    sin_archivo = aporte(W4, S1, status=AttachmentFileStatus.UPLOADING)
    c = canonico(S1)

    orden = fuentes_para_copiar(
        [reciente, c, otro_sha, sin_archivo, antigua, de_la_extension], S1
    )

    assert [f.id for f in orden] == [de_la_extension.id, antigua.id, reciente.id]


# --- La entidad espeja los CHECK de la base ---


def test_la_entidad_rechaza_compartir_una_fila_de_empresa():
    datos = aporte(W1, S1).model_dump()

    with pytest.raises(ValidationError):
        AttachmentFile.model_validate({**datos, "visibility": SHARED, "trust": CORROBORATED})


def test_la_entidad_rechaza_compartir_lo_no_corroborado():
    datos = canonico(S1).model_dump()

    with pytest.raises(ValidationError):
        AttachmentFile.model_validate({**datos, "trust": PENDING})


def test_la_entidad_rechaza_una_canonica_con_autor():
    datos = canonico(S1).model_dump()

    with pytest.raises(ValidationError):
        AttachmentFile.model_validate({**datos, "uploader_user_id": U1})


def test_la_entidad_acepta_una_canonica_valida_y_un_aporte_privado():
    assert canonico(S1).workspace_id is None
    assert aporte(W1, S1).visibility == PRIVATE
