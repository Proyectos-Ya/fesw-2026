"""Promover a compartido la versión confirmada de un anexo oficial (plan 233, decisión 6).

La decisión de qué se comparte es una función pura (`decidir_confianza`); este caso
de uso la aplica con la fila del anexo bloqueada, copia el objeto ganador a
`shared/` verificando lo que quedó y avisa a la decisión 4 cuando una versión
entra o sale de lo compartido.
"""

import asyncio
import hashlib
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.application.repositories.attachment_trust_repository import (
    IAttachmentTrustRepository,
    TrustSnapshot,
)
from app.application.services.attachment_deleted_listener import (
    IAttachmentDeletedListener,
)
from app.application.services.attachment_storage import IAttachmentStorage
from app.application.services.attachment_stored_listener import (
    IAttachmentStoredListener,
)
from app.application.services.attachment_visibility_listener import (
    IAttachmentVisibilityListener,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.services.attachment_files import clave_compartida
from app.domain.services.attachment_trust import (
    decidir_confianza,
    es_canonico,
    fuentes_para_copiar,
)
from app.shared.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PromotionOutcome:
    shared: AttachmentFile | None = None  # la versión que ven todas tras evaluar
    visibility_changed: tuple[AttachmentFile, ...] = ()


@dataclass
class _Plan:
    actualizados: list[AttachmentFile] = field(default_factory=list)
    creados: list[AttachmentFile] = field(default_factory=list)
    visibilidad_cambiada: list[AttachmentFile] = field(default_factory=list)

    @property
    def vacio(self) -> bool:
        return not self.actualizados and not self.creados


def _sha256_hex(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _compartida(archivos: list[AttachmentFile], plan: _Plan) -> AttachmentFile | None:
    """La fila que ven todas las empresas después de aplicar el plan."""
    finales = (
        {a.id: a for a in archivos}
        | {a.id: a for a in plan.actualizados}
        | {a.id: a for a in plan.creados}
    )
    return next(
        (a for a in finales.values() if a.visibility == AttachmentVisibility.SHARED), None
    )


class PromoteAttachmentUseCase:
    """Reevalúa un anexo oficial con su fila bloqueada y aplica la decisión de confianza."""

    def __init__(
        self,
        *,
        trust: IAttachmentTrustRepository,
        storage: IAttachmentStorage | None,
        visibility_listener: IAttachmentVisibilityListener,
        clock: Callable[[], datetime] = utc_now_naive,
        new_id: Callable[[], UUID] = uuid4,
    ) -> None:
        self.trust = trust
        self.storage = storage
        self.visibility_listener = visibility_listener
        self.clock = clock
        self.new_id = new_id

    async def execute(self, tender_attachment_id: UUID) -> PromotionOutcome:
        if self.storage is None:
            return PromotionOutcome()  # sin almacenamiento no se puede copiar nada
        guardado = False
        plan = _Plan()
        foto: TrustSnapshot | None = None
        try:
            foto = await self.trust.lock_for_promotion(tender_attachment_id)
            if foto is None or foto.attachment.removed_at is not None:
                return PromotionOutcome()  # no existe, o Mercado Público lo retiró: no se publica
            plan = await self._planificar(foto, self.storage)
            if plan.vacio:
                return PromotionOutcome(shared=_compartida(foto.files, plan))
            await self.trust.save_promotion(updated=plan.actualizados, created=plan.creados)
            guardado = True
        finally:
            # Toda salida sin commit suelta el candado: la sesión no puede quedar con
            # una transacción abierta.
            if not guardado:
                await self.trust.release()
        # Ya con el commit hecho y fuera del candado: la decisión 4 reconstruye sus
        # resúmenes. Un fallo solo se registra, la promoción ya está guardada.
        for canonica in plan.visibilidad_cambiada:
            try:
                await self.visibility_listener.on_visibility_changed(canonica)
            except Exception:
                logger.exception("El listener de visibilidad falló (archivo %s).", canonica.id)
        return PromotionOutcome(
            shared=_compartida(foto.files, plan),
            visibility_changed=tuple(plan.visibilidad_cambiada),
        )

    async def _planificar(self, foto: TrustSnapshot, storage: IAttachmentStorage) -> _Plan:
        decision = decidir_confianza(foto.files, foto.people)
        plan = _Plan()
        for archivo in foto.files:
            if es_canonico(archivo):
                estado = decision.canonicos[archivo.id]
                if (archivo.visibility, archivo.trust) == (estado.visibility, estado.trust):
                    continue
                nuevo = archivo.model_copy(
                    update={"visibility": estado.visibility, "trust": estado.trust}
                )
                plan.actualizados.append(nuevo)
                if archivo.visibility != estado.visibility:
                    plan.visibilidad_cambiada.append(nuevo)
            elif archivo.trust != decision.aportes[archivo.id]:
                plan.actualizados.append(
                    archivo.model_copy(update={"trust": decision.aportes[archivo.id]})
                )
        if decision.crear_canonico is not None:
            canonica = await self._materializar(foto, decision.crear_canonico, storage)
            if canonica is None:
                # Ninguna copia coincide con su huella: no se publica ni se marca nada
                # como corroborado (corroborated implica que la canónica existe).
                return _Plan()
            plan.creados.append(canonica)
            plan.visibilidad_cambiada.append(canonica)
        return plan

    async def _materializar(
        self, foto: TrustSnapshot, sha256: str, storage: IAttachmentStorage
    ) -> AttachmentFile | None:
        """Copia la versión ganadora a `shared/` y crea la fila canónica, o `None`.

        Nunca borra ni repunta los objetos privados: la extracción privada (decisión
        4) y la deduplicación por objeto (decisión 2) los siguen usando.
        """
        anexo = foto.attachment
        destino = clave_compartida(anexo.tender_id, anexo.mp_document_id, sha256, anexo.ext)
        fuentes = fuentes_para_copiar(foto.files, sha256)
        for fuente in fuentes:
            await storage.copy(source_key=fuente.storage_key, destination_key=destino)
            # Se verifica el destino y no la fuente: a `shared/` nadie tiene una URL PUT,
            # así que lo que se hashea es lo que queda. R2 podría no haber validado el
            # checksum de la subida, y un aporte que declaró el sha correcto con otros
            # bytes envenenaría lo compartido.
            datos = await storage.get_bytes(destino)
            if (
                len(datos) == fuente.size_bytes
                and await asyncio.to_thread(_sha256_hex, datos) == sha256
            ):
                ahora = self.clock()
                return AttachmentFile(
                    id=self.new_id(),
                    tender_attachment_id=anexo.id,
                    tender_id=anexo.tender_id,
                    sha256=sha256,
                    size_bytes=fuente.size_bytes,
                    mime_declared=fuente.mime_declared,
                    storage_key=destino,
                    source=(
                        AttachmentFileSource.EXTENSION
                        if any(f.source == AttachmentFileSource.EXTENSION for f in fuentes)
                        else AttachmentFileSource.MANUAL
                    ),
                    uploader_user_id=None,
                    workspace_id=None,
                    visibility=AttachmentVisibility.SHARED,
                    trust=AttachmentTrust.CORROBORATED,
                    status=AttachmentFileStatus.STORED,
                    created_at=ahora,
                    completed_at=ahora,
                    purge_after=None,
                )
            logger.warning(
                "La copia del archivo %s no coincide con su huella; se prueba otra fuente.",
                fuente.id,
            )
            await storage.delete(destino)
        return None


PromoteOpener = Callable[[], AbstractAsyncContextManager[PromoteAttachmentUseCase]]


class AttachmentPromotionListener(IAttachmentStoredListener, IAttachmentDeletedListener):
    """Reevalúa el anexo cada vez que cambia la evidencia: se guarda o se borra un aporte.

    Cada evaluación pide un caso de uso nuevo a `abrir` (en producción, con su propia
    sesión de base): toma un candado y hace su propio commit, así que no puede heredar
    la transacción de la petición ni el estado que dejó otro listener.
    """

    def __init__(self, abrir: PromoteOpener) -> None:
        self.abrir = abrir

    async def on_stored(self, file: AttachmentFile) -> None:
        await self._reevaluar(file)

    async def on_deleted(self, file: AttachmentFile) -> None:
        await self._reevaluar(file)

    async def _reevaluar(self, file: AttachmentFile) -> None:
        if file.workspace_id is None:
            return  # una canónica no es evidencia nueva
        async with self.abrir() as promote:
            await promote.execute(file.tender_attachment_id)
