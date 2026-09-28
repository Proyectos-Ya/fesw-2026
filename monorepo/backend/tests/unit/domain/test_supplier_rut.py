"""
Pruebas unitarias del formato canónico del RUT en la entidad Supplier.

El RUT se guarda siempre como XX.XXX.XXX-X para que la búsqueda de duplicados
no dependa de cómo lo escribió el cliente.
"""

import pytest
from pydantic import ValidationError

from app.domain.entities.supplier import Supplier, format_rut


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("760864285", "76.086.428-5"),
        ("76086428-5", "76.086.428-5"),
        ("76.086.428-5", "76.086.428-5"),
        ("20347878k", "20.347.878-K"),
        ("7654321-6", "7.654.321-6"),
        (" 76.086.428-5 ", "76.086.428-5"),
    ],
)
def test_format_rut(raw: str, expected: str) -> None:
    assert format_rut(raw) == expected


@pytest.mark.parametrize("raw", ["76086428-5", "760864285", "76.086.428-5"])
def test_supplier_normalizes_rut(raw: str) -> None:
    supplier = Supplier(rut=raw, legal_name="Empresa SpA")

    assert supplier.rut == "76.086.428-5"


def test_supplier_uppercases_k_check_digit() -> None:
    supplier = Supplier(rut="20.347.878-k", legal_name="Empresa SpA")

    assert supplier.rut == "20.347.878-K"


def test_supplier_still_rejects_wrong_check_digit() -> None:
    with pytest.raises(ValidationError):
        Supplier(rut="76.086.428-0", legal_name="Empresa SpA")
