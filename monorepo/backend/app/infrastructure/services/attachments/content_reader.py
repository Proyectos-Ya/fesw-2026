"""Lector de documentos de anexos basado en la biblioteca estándar, pypdf y openpyxl (plan 233, decisión 4)."""

import asyncio
import logging

from app.application.services.attachment_content_reader import (
    IAttachmentContentReader,
    SeccionDeTexto,
    TextoDelDocumento,
)
from app.domain.entities.attachment_processing import (
    MOTIVOS_DE_RECHAZO,
)
from app.domain.services.attachment_file_signatures import (
    LARGO_DE_CABECERA,
    ArchivoInspeccionado,
    FormatoLegible,
    Veredicto,
    clasificar_por_firma,
)
from app.infrastructure.services.attachments.ooxml import (
    LimitesZip,
    docx_a_texto,
    inspeccionar_ooxml,
)
from app.infrastructure.services.attachments.pdf_text import pdf_paginas
from app.infrastructure.services.document_text import formatear_hojas, xlsx_hojas

logger = logging.getLogger(__name__)


class StdlibAttachmentContentReader(IAttachmentContentReader):
    def __init__(
        self,
        *,
        limites: LimitesZip = LimitesZip(),
        max_paginas: int = 300,
        max_caracteres: int = 300_000,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.limites = limites
        self.max_paginas = max_paginas
        self.max_caracteres = max_caracteres
        self.timeout_seconds = timeout_seconds

    def _inspeccionar(self, data: bytes, ext: str) -> ArchivoInspeccionado:
        inspeccion = clasificar_por_firma(data[:LARGO_DE_CABECERA], ext)
        if inspeccion.veredicto != Veredicto.OK:
            return inspeccion
        if inspeccion.formato in (FormatoLegible.DOCX, FormatoLegible.XLSX):
            motivo = inspeccionar_ooxml(data, inspeccion.formato, self.limites)
            if motivo is not None:
                if motivo in MOTIVOS_DE_RECHAZO:
                    return ArchivoInspeccionado(Veredicto.RECHAZADO, motivo=motivo)
                return ArchivoInspeccionado(Veredicto.NO_SOPORTADO, motivo=motivo)
            return ArchivoInspeccionado(
                Veredicto.OK, formato=inspeccion.formato, mime="text/plain"
            )
        return inspeccion

    async def inspect(self, data: bytes, ext: str) -> ArchivoInspeccionado:
        return await asyncio.to_thread(self._inspeccionar, data, ext)

    def _truncar_para_modelo(self, texto: str) -> str:
        if len(texto) > self.max_caracteres:
            return texto[: self.max_caracteres] + "\n[… documento truncado …]"
        return texto

    def _leer(
        self, data: bytes, formato: FormatoLegible, *, nombre: str
    ) -> TextoDelDocumento:
        if formato == FormatoLegible.PDF:
            paginas = pdf_paginas(data, max_paginas=self.max_paginas)
            secciones = tuple(
                SeccionDeTexto(etiqueta=str(i + 1), texto=p)
                for i, p in enumerate(paginas)
            )
            return TextoDelDocumento(
                secciones=secciones, para_modelo=None, paginas=len(paginas)
            )

        if formato == FormatoLegible.IMAGEN:
            return TextoDelDocumento(secciones=(), para_modelo=None)

        if formato == FormatoLegible.DOCX:
            texto = docx_a_texto(data, self.limites)
            secciones = (
                (SeccionDeTexto(etiqueta="documento", texto=texto),)
                if texto
                else ()
            )
            return TextoDelDocumento(
                secciones=secciones,
                para_modelo=self._truncar_para_modelo(texto) if texto else None,
            )

        if formato == FormatoLegible.XLSX:
            hojas = xlsx_hojas(data, read_only=True)
            secciones = tuple(
                SeccionDeTexto(etiqueta=hoja, texto="\n".join(filas))
                for hoja, filas in hojas
            )
            para_modelo = formatear_hojas(nombre, hojas)
            return TextoDelDocumento(
                secciones=secciones,
                para_modelo=self._truncar_para_modelo(para_modelo),
            )

        return TextoDelDocumento(secciones=())

    async def read_text(
        self, data: bytes, formato: FormatoLegible, *, nombre: str
    ) -> TextoDelDocumento:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._leer, data, formato, nombre=nombre),
                timeout=self.timeout_seconds,
            )
        except TimeoutError:
            logger.warning(
                "Timeout (%s s) al leer texto del anexo %s",
                self.timeout_seconds,
                nombre,
            )
            return TextoDelDocumento(secciones=())
