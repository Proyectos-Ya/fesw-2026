"""Fuentes externas de datos de empresas por RUT: SRE y Web Empresario.

Portado de `spikes/spike-1/poc/perfilar_rut.py` (red) y
`spikes/spike-1/poc/perfilamiento/fuentes.py` (parseo). Las dos APIs entregan lo
mismo con esquemas y autenticación distintos; cada subclase resuelve lo suyo y
devuelve el mismo `CompanyRecord`:

| | Web Empresario | SRE |
|---|---|---|
| Petición | `GET /v1/{rut}` | `POST /api/company_info` |
| Credencial | cabecera `X-Api-Key` | `token` dentro del cuerpo JSON |
| Actividades | código (entero) + glosa | solo códigos (texto) |
| Domicilio | `domicilios[].REGION` | no entrega |
| Vigencia | `FECHA_TG_VIG` vacío = vigente | no entrega |

Lo común —timeout, códigos HTTP, JSON inválido— vive en la base. Sin reintentos: el
usuario está esperando frente al botón, y un error rápido le deja seguir llenando
el wizard a mano.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.application.services.company_lookup_service import ICompanyLookupService
from app.domain.entities.company_profile import CompanyRecord, EconomicActivity
from app.domain.errors.company_lookup_errors import (
    CompanyLookupUnavailable,
    CompanyNotFoundInSource,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 15.0

# Respuestas que significan "no hay datos para ese RUT" y no un problema de la
# fuente. El resto de los 4xx (credencial, cuota) se trata como no disponible.
_NOT_FOUND_STATUS = {400, 404, 422}


class HttpCompanyLookupService(ICompanyLookupService, ABC):
    source: str

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @abstractmethod
    async def _request(self, client: httpx.AsyncClient, rut: str) -> httpx.Response: ...

    @abstractmethod
    def _parse(self, payload: Any, rut: str) -> CompanyRecord: ...

    async def lookup(self, rut: str) -> CompanyRecord:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await self._request(client, rut)
        except httpx.TransportError as exc:
            logger.warning("%s no respondió: %s", self.source, exc)
            raise CompanyLookupUnavailable(f"{self.source}: {exc}") from exc

        if response.status_code in _NOT_FOUND_STATUS:
            raise CompanyNotFoundInSource(rut)
        if response.status_code >= 400:
            logger.error("%s respondió %s", self.source, response.status_code)
            raise CompanyLookupUnavailable(f"{self.source}: HTTP {response.status_code}")

        # Con reemplazo: Web Empresario ya entrega campos mal codificados, y
        # reventar por un acento perdería la respuesta completa.
        try:
            payload = json.loads(response.content.decode("utf-8", errors="replace"))
        except ValueError as exc:
            logger.error("%s no respondió JSON válido", self.source)
            raise CompanyLookupUnavailable(f"{self.source}: JSON inválido") from exc

        return self._parse(payload, rut)


def repair_mojibake(text: str) -> str:
    """Repara texto UTF-8 que el origen decodificó como Latin-1 (`VALPARAÃ\\x8dSO`)."""
    if not any(mark in text for mark in ("Ã", "Â", "â€")):
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _parse_code(raw: Any) -> int | None:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


class WebEmpresarioLookupService(HttpCompanyLookupService):
    source = "web-empresario"

    async def _request(self, client: httpx.AsyncClient, rut: str) -> httpx.Response:
        return await client.get(
            f"{self._base_url}/v1/{rut}",
            headers={"Accept": "application/json", "X-Api-Key": self._api_key},
        )

    def _parse(self, payload: Any, rut: str) -> CompanyRecord:
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(payload, dict) or not payload.get("success") or not isinstance(data, dict):
            raise CompanyNotFoundInSource(rut)

        body = str(data.get("RUT", "")).strip()
        dv = str(data.get("DV", "")).strip().upper()

        activities: list[EconomicActivity] = []
        for raw in data.get("actividades") or []:
            code = _parse_code(raw.get("CODIGO_ACTIVIDAD")) if isinstance(raw, dict) else None
            if code is None:
                logger.info("Código de actividad ilegible en %s: %r", self.source, raw)
                continue
            activities.append(
                EconomicActivity(code=code, description=_text(raw, "DESC_ACTIVIDAD"))
            )

        # Los domicilios vienen repetidos con distinta fecha de vigencia; interesa
        # la región, no la dirección.
        regions: list[str] = []
        for raw in data.get("domicilios") or []:
            region = _text(raw, "REGION") if isinstance(raw, dict) else ""
            if region and region not in regions:
                regions.append(region)

        return CompanyRecord(
            source=self.source,
            rut=f"{body}-{dv}" if body and dv else rut,
            legal_name=_text(data, "RAZON_SOCIAL"),
            activities=activities,
            raw_regions=regions,
            # Vacío = sin término de giro registrado = vigente.
            is_active=not _text(data, "FECHA_TG_VIG") if "FECHA_TG_VIG" in data else None,
        )


def _text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    return repair_mojibake(str(value)).strip() if value else ""


class SreLookupService(HttpCompanyLookupService):
    source = "sre"

    async def _request(self, client: httpx.AsyncClient, rut: str) -> httpx.Response:
        return await client.post(
            f"{self._base_url}/api/company_info",
            headers={"Accept": "application/json"},
            json={"token": self._api_key, "rut": rut, "version": "2.0"},
        )

    def _parse(self, payload: Any, rut: str) -> CompanyRecord:
        if not isinstance(payload, dict) or not payload.get("razon_social"):
            logger.warning(
                "SRE no trajo razón social para %s (claves: %s)",
                rut,
                sorted(payload) if isinstance(payload, dict) else type(payload).__name__,
            )
            raise CompanyNotFoundInSource(rut)

        # La API expone su propia cuota en cada respuesta.
        if "consultas_restantes" in payload:
            logger.info("SRE: quedan %s consultas", payload["consultas_restantes"])

        activities: list[EconomicActivity] = []
        for raw in payload.get("actecos") or []:
            code = _parse_code(raw)
            if code is None:
                logger.info("Código de actividad ilegible en SRE: %r", raw)
                continue
            activities.append(EconomicActivity(code=code))

        return CompanyRecord(
            source=self.source,
            rut=str(payload.get("rut") or rut).strip(),
            legal_name=str(payload["razon_social"]).strip(),
            activities=activities,
        )
