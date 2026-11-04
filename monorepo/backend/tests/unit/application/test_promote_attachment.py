"""Promover a compartido la versión confirmada de un anexo (plan 233, decisión 6).

La decisión de qué se comparte está probada como tabla de verdad en
`tests/unit/domain/test_attachment_trust.py`. Acá se prueba lo que la rodea: que
la copia a `shared/` se verifique, que nunca quede una transacción abierta, que
una canónica sin empresa se vea igual para todas y que la promoción se dispare al
guardar y al borrar un archivo.
"""

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.services.attachment_storage import AttachmentStorageError
from app.application.use_cases.tender_attachments.delete_attachment_file import (
    DeleteAttachmentFileUseCase,
)
from app.application.use_cases.tender_attachments.get_tender_attachments import (
    GetTenderAttachmentsUseCase,
    TenderAttachmentsResult,
    WorkspaceAccess,
)
from app.application.use_cases.tender_attachments.promote_attachment import (
    AttachmentPromotionListener,
    PromoteAttachmentUseCase,
    PromotionOutcome,
)
from app.application.use_cases.tender_attachments.request_attachment_upload import (
    RequestAttachmentUploadUseCase,
    UploadDeduplicated,
    UploadRequest,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.entities.tender_attachment import AttachmentStatus
from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from app.domain.services.attachment_trust import visibilidad_efectiva
from tests.unit.application.attachment_fakes import InMemoryTenderAttachmentRepository
from tests.unit.application.attachment_file_fakes import (
    FakeAttachmentStorage,
    InMemoryAttachmentFileRepository,
    InMemoryAttachmentTrustRepository,
    RecordingStoredListener,
    RecordingVisibilityListener,
)

T = uuid4()
W1, W2, W3, W4, W5 = (uuid4() for _ in range(5))
U1, U2, U3, U4, U5, U9 = (uuid4() for _ in range(6))
AUTOR = {W1: U1, W2: U2, W3: U3, W4: U4, W5: U5}
AHORA = datetime(2026, 10, 3, 15, 0)
SINCRONIZADO = datetime(2026, 9, 28, 16, 0)
NOMBRE = "Anexo 3 Composición personalidad juridica.xlsx"
HOLA = b"hola"
CHAO = b"chao"
S1 = hashlib.sha256(HOLA).hexdigest()
S2 = hashlib.sha256(CHAO).hexdigest()

PRIVATE = AttachmentVisibility.PRIVATE
SHARED = AttachmentVisibility.SHARED
PENDING = AttachmentTrust.PENDING
CORROBORATED = AttachmentTrust.CORROBORATED
CONFLICT = AttachmentTrust.CONFLICT
REJECTED = AttachmentTrust.REJECTED
EXTENSION = AttachmentFileSource.EXTENSION


class Mundo:
    """La licitación T con un anexo oficial xlsx, y los dobles que lo rodean."""

    def __init__(self, *, personas: dict[UUID, frozenset[UUID]] | None = None) -> None:
        self.anexos = InMemoryTenderAttachmentRepository({"5052-431-COT26": T})
        self.files = InMemoryAttachmentFileRepository()
        self.storage = FakeAttachmentStorage()
        self.vis = RecordingVisibilityListener()
        self.trust = InMemoryAttachmentTrustRepository(
            files=self.files, attachments=self.anexos, personas=personas
        )
        self.aperturas = 0

    async def sincronizar(self) -> None:
        await self.anexos.sync_official_lists(
            {T: [DocumentoOficialDTO(mp_document_id=1931002, nombre=NOMBRE)]},
            visto_en=SINCRONIZADO,
        )

    @property
    def x(self) -> UUID:
        return self.anexos.filas[(T, 1931002)].id

    @property
    def clave_compartida(self) -> str:
        return f"shared/{T}/1931002/{S1}.xlsx"

    def caso(self, *, con_almacenamiento: bool = True) -> PromoteAttachmentUseCase:
        return PromoteAttachmentUseCase(
            trust=self.trust,
            storage=self.storage if con_almacenamiento else None,
            visibility_listener=self.vis,
            clock=lambda: AHORA,
        )

    def listener(self) -> AttachmentPromotionListener:
        @asynccontextmanager
        async def abrir() -> AsyncIterator[PromoteAttachmentUseCase]:
            self.aperturas += 1
            yield self.caso()

        return AttachmentPromotionListener(abrir)

    def aportar(
        self,
        ws: UUID,
        *,
        contenido: bytes = HOLA,
        sha: str | None = None,
        fuente: AttachmentFileSource = AttachmentFileSource.MANUAL,
        autor: UUID | None = None,
        completado: datetime = AHORA,
    ) -> AttachmentFile:
        """Un archivo guardado de la empresa; `sha` distinto del contenido simula bytes adulterados."""
        sha = sha or hashlib.sha256(contenido).hexdigest()
        clave = f"private/{ws}/{sha}.xlsx"
        fila = AttachmentFile(
            id=uuid4(),
            tender_attachment_id=self.x,
            tender_id=T,
            sha256=sha,
            size_bytes=len(contenido),
            mime_declared="application/octet-stream",
            storage_key=clave,
            source=fuente,
            uploader_user_id=autor or AUTOR[ws],
            workspace_id=ws,
            status=AttachmentFileStatus.STORED,
            created_at=completado - timedelta(minutes=1),
            completed_at=completado,
        )
        self.files.filas[fila.id] = fila
        self.storage.subir(clave, contenido)
        return fila

    def fila(self, archivo: AttachmentFile) -> AttachmentFile:
        return self.files.filas[archivo.id]

    def canonicas(self) -> list[AttachmentFile]:
        return [f for f in self.files.filas.values() if f.workspace_id is None]

    def canonica(self, sha: str) -> AttachmentFile:
        [c] = [c for c in self.canonicas() if c.sha256 == sha]
        return c

    async def ver(self, ws: UUID | None) -> TenderAttachmentsResult:
        acceso = WorkspaceAccess(ws, True) if ws is not None else None
        return await GetTenderAttachmentsUseCase(
            self.anexos,
            self.files,
            uploads_per_month=100,
            storage_available=True,
            clock=lambda: AHORA,
        ).execute(T, access=acceso)

    async def conflicto_de_cuatro(self) -> list[AttachmentFile]:
        """W1 y W2 con S1, W3 y W4 con S2: dos versiones respaldadas, ninguna gana."""
        filas = [
            self.aportar(W1),
            self.aportar(W2),
            self.aportar(W3, contenido=CHAO),
            self.aportar(W4, contenido=CHAO),
        ]
        await self.caso().execute(self.x)
        return filas


@pytest.fixture
async def mundo():
    m = Mundo()
    await m.sincronizar()
    yield m
    # Invariante de la promoción: toda transacción abierta se cierra, con commit o
    # con rollback. Una sesión que queda abierta retiene el candado del anexo.
    assert m.trust.abiertas == m.trust.liberadas + m.trust.guardadas


# --- Lo que se comparte y lo que no ---


async def test_subida_manual_sola_queda_privada_y_pendiente(mundo: Mundo) -> None:
    w1 = mundo.aportar(W1)

    await mundo.caso().execute(mundo.x)

    assert mundo.fila(w1).visibility == PRIVATE
    assert mundo.fila(w1).trust == PENDING
    assert mundo.canonicas() == []
    assert mundo.storage.copias == []
    assert mundo.vis.recibidos == []
    assert (mundo.trust.liberadas, mundo.trust.guardadas) == (1, 0)


async def test_otra_empresa_con_el_mismo_sha_se_comparte_con_copia_a_shared(
    mundo: Mundo,
) -> None:
    w1 = mundo.aportar(W1, completado=AHORA - timedelta(hours=1))
    w2 = mundo.aportar(W2)

    resultado = await mundo.caso().execute(mundo.x)

    canonica = mundo.canonica(S1)
    assert canonica.workspace_id is None
    assert canonica.uploader_user_id is None
    assert canonica.visibility == SHARED
    assert canonica.trust == CORROBORATED
    assert canonica.status == AttachmentFileStatus.STORED
    assert canonica.storage_key == mundo.clave_compartida
    assert canonica.size_bytes == 4
    assert canonica.created_at == canonica.completed_at == AHORA
    assert canonica.source == AttachmentFileSource.MANUAL
    assert canonica.tender_attachment_id == mundo.x
    # Se copia de la más antigua; los privados no se tocan.
    assert mundo.storage.copias == [(f"private/{W1}/{S1}.xlsx", mundo.clave_compartida)]
    assert mundo.storage.objetos[mundo.clave_compartida] == HOLA
    assert mundo.storage.borradas == []
    assert mundo.storage.objetos[f"private/{W1}/{S1}.xlsx"] == HOLA
    for aporte in (w1, w2):
        assert mundo.fila(aporte).trust == CORROBORATED
        assert mundo.fila(aporte).visibility == PRIVATE
    assert mundo.vis.recibidos == [canonica]
    assert resultado.shared is not None and resultado.shared.id == canonica.id
    assert resultado.visibility_changed == (canonica,)


async def test_volver_a_subir_el_mismo_archivo_no_se_corrobora(mundo: Mundo) -> None:
    w1 = mundo.aportar(W1)
    await mundo.caso().execute(mundo.x)
    del mundo.files.filas[w1.id]

    otra = mundo.aportar(W1)
    await mundo.caso().execute(mundo.x)

    assert mundo.fila(otra).trust == PENDING
    assert mundo.storage.copias == []
    assert mundo.canonicas() == []


async def test_dos_empresas_con_una_persona_en_comun_no_se_corroboran() -> None:
    m = Mundo(personas={W1: frozenset({U1, U9}), W2: frozenset({U2, U9})})
    await m.sincronizar()
    w1, w2 = m.aportar(W1), m.aportar(W2)

    await m.caso().execute(m.x)

    assert m.fila(w1).trust == PENDING
    assert m.fila(w2).trust == PENDING
    assert m.storage.copias == []
    assert m.trust.abiertas == m.trust.liberadas + m.trust.guardadas


async def test_dos_subidas_sueltas_distintas_no_se_ven_entre_si(mundo: Mundo) -> None:
    w1 = mundo.aportar(W1)
    w2 = mundo.aportar(W2, contenido=CHAO)

    await mundo.caso().execute(mundo.x)

    # Si W1 pasara a `conflict` por lo que subió W2, subir cualquier archivo
    # revelaría que otra empresa trabaja esa licitación.
    assert mundo.fila(w1).trust == PENDING
    assert mundo.fila(w2).trust == PENDING
    assert mundo.storage.copias == []


async def test_versiones_respaldadas_distintas_quedan_en_conflicto_y_no_se_comparte_nada(
    mundo: Mundo,
) -> None:
    filas = await mundo.conflicto_de_cuatro()

    assert {mundo.fila(f).trust for f in filas} == {CONFLICT}
    assert mundo.canonicas() == []
    assert mundo.storage.copias == []
    vista = await mundo.ver(W5)
    assert vista.official[0].status == AttachmentStatus.MISSING
    assert vista.official[0].file is None


async def test_la_extension_que_contradice_lo_compartido_lo_suspende(mundo: Mundo) -> None:
    w1, w2 = mundo.aportar(W1), mundo.aportar(W2)
    await mundo.caso().execute(mundo.x)
    w5 = mundo.aportar(W5, contenido=CHAO, fuente=EXTENSION)

    await mundo.caso().execute(mundo.x)

    suspendida = mundo.canonica(S1)
    assert (suspendida.visibility, suspendida.trust) == (PRIVATE, CONFLICT)
    for aporte in (w1, w2, w5):
        assert mundo.fila(aporte).trust == CONFLICT
    assert mundo.vis.recibidos[-1].visibility == PRIVATE
    assert (await mundo.ver(W3)).official[0].status == AttachmentStatus.MISSING
    assert await mundo.files.find_shared_stored(tender_attachment_id=mundo.x, sha256=S1) is None


async def test_la_extension_resuelve_el_conflicto(mundo: Mundo) -> None:
    w1, w2, w3, w4 = await mundo.conflicto_de_cuatro()
    w5 = mundo.aportar(W5, fuente=EXTENSION)

    await mundo.caso().execute(mundo.x)

    canonica = mundo.canonica(S1)
    assert canonica.visibility == SHARED
    # La extensión va primero entre las fuentes de la copia.
    assert mundo.storage.copias[-1][0] == f"private/{W5}/{S1}.xlsx"
    for ganador in (w1, w2, w5):
        assert mundo.fila(ganador).trust == CORROBORATED
    for perdedor in (w3, w4):
        assert mundo.fila(perdedor).trust == REJECTED
        assert mundo.fila(perdedor).visibility == PRIVATE
        assert perdedor.storage_key in mundo.storage.objetos


async def test_la_extension_resuelve_dos_sueltas(mundo: Mundo) -> None:
    w1 = mundo.aportar(W1)
    w2 = mundo.aportar(W2, contenido=CHAO)
    mundo.aportar(W5, contenido=CHAO, fuente=EXTENSION)

    await mundo.caso().execute(mundo.x)

    assert mundo.canonica(S2).visibility == SHARED
    assert mundo.fila(w2).trust == CORROBORATED
    assert mundo.fila(w1).trust == REJECTED


# --- La copia se verifica ---


async def test_verifica_la_copia_y_prueba_otra_fuente(mundo: Mundo) -> None:
    # W1 (la más antigua) declara el sha correcto pero subió otros bytes.
    mundo.aportar(W1, contenido=b"xxxx", sha=S1, completado=AHORA - timedelta(hours=1))
    mundo.aportar(W2)

    await mundo.caso().execute(mundo.x)

    assert mundo.storage.copias == [
        (f"private/{W1}/{S1}.xlsx", mundo.clave_compartida),
        (f"private/{W2}/{S1}.xlsx", mundo.clave_compartida),
    ]
    assert mundo.storage.borradas == [mundo.clave_compartida]
    assert mundo.storage.objetos[mundo.clave_compartida] == HOLA
    assert mundo.canonica(S1).visibility == SHARED


async def test_si_ninguna_copia_coincide_no_publica_nada(mundo: Mundo) -> None:
    w1 = mundo.aportar(W1, contenido=b"xxxx", sha=S1)
    w2 = mundo.aportar(W2, contenido=b"yyyy", sha=S1)

    await mundo.caso().execute(mundo.x)

    assert mundo.canonicas() == []
    assert mundo.fila(w1).trust == PENDING
    assert mundo.fila(w2).trust == PENDING
    assert mundo.clave_compartida not in mundo.storage.objetos
    assert (mundo.trust.guardadas, mundo.trust.liberadas) == (0, 1)
    assert mundo.vis.recibidos == []


async def test_un_error_del_almacenamiento_no_deja_nada_a_medias(mundo: Mundo) -> None:
    w1, w2 = mundo.aportar(W1), mundo.aportar(W2)
    mundo.storage.falla_con = AttachmentStorageError()

    with pytest.raises(AttachmentStorageError):
        await mundo.caso().execute(mundo.x)

    assert mundo.trust.liberadas == 1
    assert mundo.fila(w1).trust == PENDING
    assert mundo.fila(w2).trust == PENDING
    assert mundo.canonicas() == []


async def test_sin_almacenamiento_no_evalua(mundo: Mundo) -> None:
    mundo.aportar(W1)
    mundo.aportar(W2)

    resultado = await mundo.caso(con_almacenamiento=False).execute(mundo.x)

    assert resultado == PromotionOutcome()
    assert mundo.trust.abiertas == 0


async def test_un_anexo_inexistente_suelta_el_candado(mundo: Mundo) -> None:
    resultado = await mundo.caso().execute(uuid4())

    assert resultado == PromotionOutcome()
    assert mundo.trust.liberadas == 1


async def test_anexo_retirado_no_se_publica(mundo: Mundo) -> None:
    mundo.aportar(W1)
    mundo.aportar(W2)
    # Mercado Público ya no lista el documento: la fila queda con `removed_at`.
    await mundo.anexos.sync_official_lists({T: []}, visto_en=SINCRONIZADO + timedelta(hours=1))

    resultado = await mundo.caso().execute(mundo.x)

    assert resultado == PromotionOutcome()
    assert mundo.canonicas() == []
    assert mundo.trust.liberadas == 1


async def test_es_idempotente(mundo: Mundo) -> None:
    mundo.aportar(W1)
    mundo.aportar(W2)

    primera = await mundo.caso().execute(mundo.x)
    segunda = await mundo.caso().execute(mundo.x)

    assert len(mundo.canonicas()) == 1
    assert len(mundo.storage.copias) == 1
    assert (mundo.trust.guardadas, mundo.trust.liberadas) == (1, 1)
    assert len(mundo.vis.recibidos) == 1
    assert segunda.shared is not None and segunda.shared.id == primera.shared.id  # type: ignore[union-attr]
    assert segunda.visibility_changed == ()


async def test_un_listener_de_visibilidad_que_falla_no_deshace_la_promocion(
    mundo: Mundo,
) -> None:
    mundo.vis.falla_con = RuntimeError("boom")
    mundo.aportar(W1)
    mundo.aportar(W2)

    resultado = await mundo.caso().execute(mundo.x)

    assert mundo.canonica(S1).visibility == SHARED
    assert resultado.shared is not None
    assert mundo.trust.guardadas == 1


# --- Lo compartido no depende de nadie ---


async def test_quitar_los_aportes_no_descomparte(mundo: Mundo) -> None:
    w1, w2 = mundo.aportar(W1), mundo.aportar(W2)
    await mundo.caso().execute(mundo.x)
    # Lo que haría el CASCADE al borrar las dos empresas.
    del mundo.files.filas[w1.id]
    del mundo.files.filas[w2.id]

    await mundo.caso().execute(mundo.x)

    assert mundo.canonica(S1).visibility == SHARED
    visto = (await mundo.ver(W3)).official[0]
    assert visto.status == AttachmentStatus.STORED
    assert visto.file is not None
    assert visto.file.is_mine is False
    assert visibilidad_efectiva(visto.file.file) == SHARED


async def test_lo_compartido_aparece_para_todas_las_empresas(mundo: Mundo) -> None:
    mundo.aportar(W1)
    mundo.aportar(W2)
    await mundo.caso().execute(mundo.x)

    de_w3 = (await mundo.ver(W3)).official[0]
    assert de_w3.status == AttachmentStatus.STORED
    assert de_w3.file is not None
    assert de_w3.file.is_mine is False
    assert de_w3.file.file.visibility == SHARED

    de_w1 = (await mundo.ver(W1)).official[0]
    assert de_w1.file is not None
    assert de_w1.file.is_mine is True
    assert visibilidad_efectiva(de_w1.file.file) == SHARED

    # Regresión: sin empresa, `None == None` no puede volver "propia" a la canónica.
    anonimo = (await mundo.ver(None)).official[0]
    assert anonimo.file is not None
    assert anonimo.file.is_mine is False


async def test_upload_url_deduplica_contra_lo_compartido(mundo: Mundo) -> None:
    mundo.aportar(W1)
    mundo.aportar(W2)
    await mundo.caso().execute(mundo.x)
    pedir = RequestAttachmentUploadUseCase(
        attachments=mundo.anexos,
        files=mundo.files,
        storage=mundo.storage,
        listener=RecordingStoredListener(),
        uploads_per_month=2,
        clock=lambda: AHORA,
    )

    resultado = await pedir.execute(
        UploadRequest(
            tender_id=T,
            attachment_id=mundo.x,
            workspace_id=W3,
            user_id=U3,
            file_name=NOMBRE,
            size_bytes=4,
            mime="application/octet-stream",
            sha256=S1,
        )
    )

    assert isinstance(resultado, UploadDeduplicated)
    assert resultado.file.id == mundo.canonica(S1).id
    assert mundo.storage.firmadas == []
    assert not any(ws == W3 for ws, _ in mundo.files.cupo)


# --- El listener ---


async def test_el_listener_reevalua_al_guardar(mundo: Mundo) -> None:
    mundo.aportar(W1)
    w2 = mundo.aportar(W2)
    listener = mundo.listener()

    await listener.on_stored(w2)

    canonica = mundo.canonica(S1)
    assert mundo.aperturas == 1
    # Una canónica no es evidencia nueva: no abre ni evalúa nada.
    await listener.on_stored(canonica)
    assert mundo.aperturas == 1


async def test_borrar_una_captura_que_contradecia_destraba_lo_compartido(mundo: Mundo) -> None:
    mundo.aportar(W1)
    mundo.aportar(W2)
    await mundo.caso().execute(mundo.x)
    w5 = mundo.aportar(W5, contenido=CHAO, fuente=EXTENSION)
    await mundo.caso().execute(mundo.x)
    assert mundo.canonica(S1).visibility == PRIVATE
    borrar = DeleteAttachmentFileUseCase(
        files=mundo.files, storage=mundo.storage, listener=mundo.listener()
    )

    await borrar.execute(tender_id=T, file_id=w5.id, workspace_id=W5)

    canonica = mundo.canonica(S1)
    assert (canonica.visibility, canonica.trust) == (SHARED, CORROBORATED)
    assert w5.id not in mundo.files.filas
    assert mundo.vis.recibidos[-1].visibility == SHARED
