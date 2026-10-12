"""Enlace web temporal para compartir una licitación sin cuenta (HdU 19)."""

import hashlib
import secrets
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime

# Criterio 1: la URL generada vale 7 días.
SHARE_LINK_TTL = timedelta(days=7)


class ShareLinkStatus(StrEnum):
    ACTIVO = "activo"
    CADUCADO = "caducado"
    REVOCADO = "revocado"


def hash_share_token(token: str) -> str:
    """Huella del token con la que se busca el enlace.

    En la base solo queda esto: quien la lea no puede reconstruir la URL. Un
    SHA-256 sin sal alcanza porque el token es aleatorio de 256 bits; no hay
    diccionario contra el que probar.
    """
    return hashlib.sha256(token.encode()).hexdigest()


class TenderShareLink(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    token_hash: str
    tender_id: UUID
    # El enlace se abre sin sesión, así que la empresa de la que se muestran el
    # puntaje y el análisis tiene que quedar fijada al crearlo.
    supplier_id: UUID
    created_by: UUID
    created_at: UtcDateTime
    expires_at: UtcDateTime
    revoked_at: UtcDateTime | None = None

    @classmethod
    def emitir(
        cls, tender_id: UUID, supplier_id: UUID, created_by: UUID, now: datetime
    ) -> tuple["TenderShareLink", str]:
        """Crea el enlace y devuelve también el token, que no se vuelve a ver."""
        token = secrets.token_urlsafe(32)
        enlace = cls(
            token_hash=hash_share_token(token),
            tender_id=tender_id,
            supplier_id=supplier_id,
            created_by=created_by,
            created_at=now,
            expires_at=now + SHARE_LINK_TTL,
        )
        return enlace, token

    def estado(self, now: datetime) -> ShareLinkStatus:
        # Revocado gana a caducado: es el motivo más preciso para quien lo abre.
        if self.revoked_at is not None:
            return ShareLinkStatus.REVOCADO
        if now >= self.expires_at:
            return ShareLinkStatus.CADUCADO
        return ShareLinkStatus.ACTIVO

    def revocar(self, now: datetime) -> "TenderShareLink":
        if self.revoked_at is not None:
            return self
        return self.model_copy(update={"revoked_at": now})
