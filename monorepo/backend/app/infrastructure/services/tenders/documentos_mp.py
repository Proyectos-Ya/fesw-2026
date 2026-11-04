"""Lee la lista oficial de anexos que Mercado Público publica por licitación.

Forma verificada en el listado real del 2026-09-28
(`tests/fixtures/mp_listado_cambios.json`):

    documentos: [{"id": 1931002, "nombre": "Anexo 3 ....xlsx"}, ...]

Que el **detalle** (`/v2/compra-agil/{codigo}`) también la traiga no está
confirmado (plan 233, fase 0). Por eso la ausencia se distingue de la lista vacía.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO


def _id_documento(valor: object) -> int | None:
    if isinstance(valor, bool):  # bool es int en Python; un True no es un id
        return None
    if isinstance(valor, int):
        return valor if valor > 0 else None
    if isinstance(valor, str) and valor.strip().isdigit():
        numero = int(valor.strip())
        return numero if numero > 0 else None
    return None


def documentos_desde_payload(
    payload: Mapping[str, Any],
) -> list[DocumentoOficialDTO] | None:
    """La lista oficial del ítem, `[]` si no tiene anexos, `None` si no se puede leer.

    **Ante la duda, `None`.** Con una lista a medias, el anexo ilegible quedaría
    marcado como retirado aunque siga publicado: es preferible no tocar la lista
    guardada hasta la próxima lectura limpia.

    **Duplicados.** Con un id repetido se conserva el primero. Dos filas con la
    misma clave en un `INSERT ... ON CONFLICT DO UPDATE` hacen fallar la
    sentencia entera.
    """
    crudos = payload.get("documentos")
    if not isinstance(crudos, list):
        return None
    documentos: list[DocumentoOficialDTO] = []
    vistos: set[int] = set()
    for crudo in crudos:
        if not isinstance(crudo, dict):
            return None
        doc_id = _id_documento(crudo.get("id"))
        nombre = crudo.get("nombre")
        if doc_id is None or not isinstance(nombre, str) or not nombre.strip():
            return None
        if doc_id in vistos:
            continue
        vistos.add(doc_id)
        documentos.append(DocumentoOficialDTO(mp_document_id=doc_id, nombre=nombre))
    return documentos


def documentos_por_codigo(
    items: Iterable[Mapping[str, Any]],
) -> dict[str, list[DocumentoOficialDTO]]:
    """La lista oficial de cada ítem del listado que la trae legible."""
    por_codigo: dict[str, list[DocumentoOficialDTO]] = {}
    for item in items:
        code = item.get("codigo")
        lista = documentos_desde_payload(item)
        if code and lista is not None:
            por_codigo[str(code)] = lista
    return por_codigo
