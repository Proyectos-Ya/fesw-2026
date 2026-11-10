"""Pruebas de Supplier.match_threshold (HU-18).

Umbral de compatibilidad que puede fijarse a nivel de workspace. Si está
seteado, el scanner de alertas (`scan_supplier_for_alerts`) lo usa para
todos los miembros; si queda en None, cae al `threshold` de la
`NotificationPreference` individual.

El rango válido es (0, 1], igual que en NotificationPreference.threshold.
"""

import pytest
from pydantic import ValidationError

from app.domain.entities.supplier import Supplier


def _supplier(**overrides: object) -> Supplier:
    base: dict[str, object] = {
        "rut": "76.086.428-5",
        "legal_name": "Empresa SpA",
    }
    base.update(overrides)
    return Supplier(**base)  # type: ignore[arg-type]


def test_match_threshold_por_defecto_es_none() -> None:
    # None significa "no hay override de workspace; usar la preferencia
    # individual de cada miembro". Es el estado inicial para no cambiar
    # comportamiento al desplegar la HU-18.
    assert _supplier().match_threshold is None


def test_match_threshold_acepta_valores_dentro_del_rango_abierto_cerrado() -> None:
    assert _supplier(match_threshold=0.5).match_threshold == 0.5
    assert _supplier(match_threshold=1.0).match_threshold == 1.0


@pytest.mark.parametrize("valor", [0, -0.1, 1.5, 2.0])
def test_match_threshold_rechaza_valores_fuera_del_rango(valor: float) -> None:
    # Igual que en NotificationPreference.threshold: 0 avisaría de todo y
    # un valor > 1 no avisaría nunca; ambos dejan la función inservible.
    with pytest.raises(ValidationError):
        _supplier(match_threshold=valor)
