"""Tests de extracción de texto de PDF con pypdf (plan 233, decisión 4)."""

from app.infrastructure.services.attachments.pdf_text import pdf_paginas
from tests.unit.application.attachment_processing_fakes import PDF_BYTES


def test_pdf_fixture_paginas_y_contenido():
    paginas = pdf_paginas(PDF_BYTES)
    assert len(paginas) == 9
    assert "suma alzada" in paginas[3].lower()


def test_pdf_max_paginas():
    paginas = pdf_paginas(PDF_BYTES, max_paginas=2)
    assert len(paginas) == 2


def test_pdf_invalido_devuelve_lista_vacia_sin_lanzar():
    paginas = pdf_paginas(b"%PDF-1.4 basura corrupta no legible")
    assert paginas == []
