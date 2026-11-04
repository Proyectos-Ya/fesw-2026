"""Caso de uso: Gestión del emparejamiento (Pairing) web-extensión."""

import time
from uuid import UUID, uuid4

from app.application.repositories.extension_repository import (
    IExtensionInstallationRepository,
)
from app.application.schemas.extension_schema import (
    ExtensionPairingConfirmRequest,
    ExtensionPairingConfirmResponse,
    ExtensionPairingStartResponse,
)
from app.application.use_cases.extension.get_extension_capabilities import (
    GetExtensionCapabilitiesUseCase,
)
from app.domain.entities.extension_installation import ExtensionInstallation
from app.domain.errors.extension_errors import (
    InvalidPairingTicketError,
    PairingTicketExpiredError,
)
from app.shared.datetime_utils import utc_now_naive

# Registro en memoria de tickets efímeros: ticket -> (user_id, workspace_id, expires_at_timestamp)
_PAIRING_TICKETS: dict[str, tuple[UUID, UUID | None, float]] = {}


class PairExtensionUseCase:
    """Orquesta el flujo de emparejamiento seguro entre la app web y la extensión."""

    def __init__(
        self,
        installation_repo: IExtensionInstallationRepository,
        capabilities_use_case: GetExtensionCapabilitiesUseCase | None = None,
    ) -> None:
        self.installation_repo = installation_repo
        self.capabilities_use_case = capabilities_use_case or GetExtensionCapabilitiesUseCase()

    def start_pairing(
        self, user_id: UUID, workspace_id: UUID | None, expires_in_seconds: int = 300
    ) -> ExtensionPairingStartResponse:
        ticket = f"TKT-{uuid4().hex[:12].upper()}"
        expires_at = time.time() + expires_in_seconds
        _PAIRING_TICKETS[ticket] = (user_id, workspace_id, expires_at)
        return ExtensionPairingStartResponse(
            pairing_ticket=ticket,
            expires_in_seconds=expires_in_seconds,
        )

    async def confirm_pairing(
        self, request: ExtensionPairingConfirmRequest
    ) -> ExtensionPairingConfirmResponse:
        entry = _PAIRING_TICKETS.pop(request.pairing_ticket, None)
        if not entry:
            raise InvalidPairingTicketError()

        user_id, workspace_id, expires_at = entry
        if time.time() > expires_at:
            raise PairingTicketExpiredError()

        now = utc_now_naive()
        existing = await self.installation_repo.get_by_id(request.installation_id)
        if existing:
            installation = ExtensionInstallation(
                id=existing.id,
                user_id=user_id,
                workspace_id=workspace_id,
                browser=request.browser,
                browser_version=request.browser_version,
                extension_version=request.extension_version,
                is_active=True,
                last_heartbeat_at=now,
                created_at=existing.created_at,
                updated_at=now,
            )
            status = "updated"
        else:
            installation = ExtensionInstallation(
                id=request.installation_id,
                user_id=user_id,
                workspace_id=workspace_id,
                browser=request.browser,
                browser_version=request.browser_version,
                extension_version=request.extension_version,
                is_active=True,
                last_heartbeat_at=now,
                created_at=now,
                updated_at=now,
            )
            status = "paired"

        saved = await self.installation_repo.save(installation)
        capabilities = self.capabilities_use_case.execute()

        return ExtensionPairingConfirmResponse(
            installation_id=saved.id,
            status=status,
            workspace_id=saved.workspace_id,
            capabilities=capabilities,
        )
