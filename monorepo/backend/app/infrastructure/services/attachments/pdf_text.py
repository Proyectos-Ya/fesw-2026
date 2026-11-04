"""Extracción de texto por página en PDF usando pypdf (plan 233, decisión 4)."""

from io import BytesIO

from pypdf import PasswordType, PdfReader


def pdf_paginas(datos: bytes, *, max_paginas: int = 300) -> list[str]:
    """Texto por página. `[]` si pypdf no lo abre: Gemini igual puede leer el PDF, y las
    citas quedan sin verificar. El tope de páginas limita la CPU (pypdf es Python puro)."""
    try:
        lector = PdfReader(BytesIO(datos))
        if lector.is_encrypted and lector.decrypt("") == PasswordType.NOT_DECRYPTED:
            return []
        paginas: list[str] = []
        for i, pagina in enumerate(lector.pages):
            if i >= max_paginas:
                break
            try:
                paginas.append(pagina.extract_text() or "")
            except Exception:  # una página rota no tumba el resto
                paginas.append("")
        return paginas
    except Exception:
        return []
