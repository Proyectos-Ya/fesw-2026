"""Puertos para generar los archivos de exportación (HdU 19).

Son síncronos y puros —reciben el snapshot y devuelven bytes— para que el caso
de uso no dependa de ReportLab ni de openpyxl, y para poder correrlos en un hilo
aparte sin sesión de base de datos.
"""

from collections.abc import Sequence
from typing import Protocol

from app.application.use_cases.exports.export_snapshot import (
    ExportSection,
    ExportSnapshot,
)


class IPdfRenderer(Protocol):
    def render(self, snapshot: ExportSnapshot) -> bytes:
        """El PDF lleva siempre análisis, justificación y cotización (criterio 3)."""
        ...


class IExcelRenderer(Protocol):
    def render(self, snapshot: ExportSnapshot, sections: Sequence[ExportSection]) -> bytes:
        """Una hoja por sección marcada (criterios 4 y 5)."""
        ...
