"""Nombre de un anexo, comparable entre Mercado Público y una descarga del navegador.

Lo importante: el navegador agrega " (1)" al repetir una descarga ("Bases (1).pdf"
en Chrome y Edge, "Bases(1).pdf" en Firefox), pero los paréntesis que son parte
del nombre oficial ("anexos (1,1-A, 2).docx", un nombre real del fixture) se
conservan. Y NFC/NFD, mayúsculas y tildes no pueden separar dos nombres iguales.
"""

import unicodedata

import pytest

from app.domain.services.attachment_names import extension_de, normalizar_nombre_anexo


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Especificaciones Técnicas.pdf", "especificaciones tecnicas.pdf"),
        ("ESPECIFICACIONES TECNICAS.PDF", "especificaciones tecnicas.pdf"),
        ("  Anexo   1 \t.docx ", "anexo 1.docx"),
        ("Bases (1).pdf", "bases.pdf"),
        ("Bases(2).pdf", "bases.pdf"),
        ("Bases (1) (2).pdf", "bases.pdf"),
        ("anexos (1,1-A, 2).docx", "anexos (1,1-a, 2).docx"),
        ("Año 2026 Ñuñoa.xlsx", "ano 2026 nunoa.xlsx"),
        ("Bases", "bases"),
        ("Bases (1)", "bases"),
    ],
)
def test_normalizar_nombre_anexo(entrada: str, esperado: str) -> None:
    assert normalizar_nombre_anexo(entrada) == esperado


def test_nfc_y_nfd_dan_lo_mismo() -> None:
    nfc = unicodedata.normalize("NFC", "Técnicas.pdf")
    nfd = unicodedata.normalize("NFD", "Técnicas.pdf")

    assert nfc != nfd
    assert normalizar_nombre_anexo(nfc) == normalizar_nombre_anexo(nfd)


def test_la_descarga_del_navegador_calza_con_el_nombre_oficial() -> None:
    oficial = "Anexo 3 Composición personalidad juridica.xlsx"
    descargado = "anexo 3 composicion personalidad juridica (1).XLSX"

    assert normalizar_nombre_anexo(oficial) == normalizar_nombre_anexo(descargado)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Bases.PDF", "pdf"),
        ("anexos (1,1-A, 2).docx", "docx"),
        ("archivo.tar.gz", "gz"),
        ("foto.JPEG", "jpeg"),
        ("Planilla.xlsx ", "xlsx"),
        ("Bases", ""),
        (".pdf", ""),
        ("Versión 1.2", ""),
        ("Informe v1.2 final", ""),
    ],
)
def test_extension_de(entrada: str, esperado: str) -> None:
    assert extension_de(entrada) == esperado
