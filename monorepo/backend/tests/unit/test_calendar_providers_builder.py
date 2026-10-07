"""Qué calendarios se ofrecen según las credenciales configuradas (HU-16, criterio 2)."""

import pytest

from app.bootstrap import builders
from app.domain.entities.calendar import CalendarProvider
from app.infrastructure.services.calendar.google_calendar_client import (
    GoogleCalendarClient,
)
from app.infrastructure.services.calendar.outlook_calendar_client import (
    OutlookCalendarClient,
)


@pytest.fixture
def credenciales(monkeypatch):
    def poner(**valores: object) -> None:
        for campo in (
            "google_calendar_client_id",
            "google_calendar_client_secret",
            "microsoft_calendar_client_id",
            "microsoft_calendar_client_secret",
        ):
            monkeypatch.setattr(builders.settings, campo, valores.get(campo))
        monkeypatch.setattr(builders.settings, "microsoft_calendar_tenant", "common")

    return poner


def test_sin_credenciales_no_hay_calendarios(credenciales):
    credenciales()

    assert builders.build_calendar_providers() == {}


def test_con_credenciales_de_microsoft_ofrece_outlook(credenciales):
    credenciales(microsoft_calendar_client_id="id", microsoft_calendar_client_secret="secreto")

    proveedores = builders.build_calendar_providers()

    assert list(proveedores) == [CalendarProvider.OUTLOOK]
    assert isinstance(proveedores[CalendarProvider.OUTLOOK], OutlookCalendarClient)
    assert proveedores[CalendarProvider.OUTLOOK].redirect_uri.endswith("/calendario/callback/outlook")


def test_con_ambas_ofrece_google_y_outlook(credenciales):
    credenciales(
        google_calendar_client_id="id.apps.googleusercontent.com",
        google_calendar_client_secret="secreto",
        microsoft_calendar_client_id="id",
        microsoft_calendar_client_secret="secreto",
    )

    proveedores = builders.build_calendar_providers()

    assert set(proveedores) == {CalendarProvider.GOOGLE, CalendarProvider.OUTLOOK}
    assert isinstance(proveedores[CalendarProvider.GOOGLE], GoogleCalendarClient)
