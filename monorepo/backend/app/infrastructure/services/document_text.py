"""Funciones utilitarias para aplanar hojas de cálculo XLSX a texto plano."""

from io import BytesIO


def formatear_hojas(file_name: str, hojas: list[tuple[str, list[str]]]) -> str:
    """Formatea la lista de hojas y sus filas a texto tabular."""
    output = [f"=== DOCUMENTO EXCEL: {file_name} ==="]
    for sheet_name, filas in hojas:
        output.append(f"\n--- Hoja: {sheet_name} ---")
        for fila in filas:
            output.append(fila)
    return "\n".join(output)


def xlsx_hojas(
    file_bytes: bytes, *, read_only: bool = True
) -> list[tuple[str, list[str]]]:
    """Lee las hojas de un archivo Excel. Salta hojas sin iter_rows (como gráficos)."""
    import openpyxl  # type: ignore

    wb = openpyxl.load_workbook(
        BytesIO(file_bytes), data_only=True, read_only=read_only
    )
    try:
        hojas = []
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            if not hasattr(ws, "iter_rows"):
                continue
            filas = []
            for row in ws.iter_rows(values_only=True):
                row_values = [
                    str(val) if val is not None else "" for val in row
                ]
                if any(row_values):
                    filas.append(" | ".join(row_values))
            hojas.append((sheet, filas))
        return hojas
    finally:
        wb.close()


def xlsx_to_text(file_bytes: bytes, file_name: str) -> str:
    """Aplana las hojas de un XLSX a texto tabular para enviarlo a un modelo de lenguaje."""
    try:
        return formatear_hojas(
            file_name, xlsx_hojas(file_bytes, read_only=False)
        )
    except Exception:
        return (
            f"[Documento Excel adjunto: {file_name} (no se pudo parsear el"
            " contenido tabular)]"
        )
