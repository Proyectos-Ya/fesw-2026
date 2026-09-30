from collections.abc import Sequence
from typing import Protocol

from app.domain.entities.supplier import Supplier


class _TenderLike(Protocol):
    name: str
    description: str | None


class _ItemLike(Protocol):
    name: str
    description: str | None


class TextBuilder:
    """
    Construye representaciones textuales simétricas para licitaciones y proveedores.
    """

    def build_from_tender(self, tender: _TenderLike, items: Sequence[_ItemLike]) -> str:
        """
        Construye el texto semántico de una licitación para embedding.
        Solo incluye qué trabajo se necesita (nombre, descripción, items).
        No incluye datos del comprador para mantener simetría con el perfil del proveedor.
        """
        parts = [tender.name]
        if tender.description:
            parts.append(tender.description)
        if items:
            item_texts = [
                item.name + (f": {item.description}" if item.description else "")
                for item in items
            ]
            parts.append("Items: " + ". ".join(item_texts))
        return ". ".join(parts)

    def build_from_supplier(self, supplier: Supplier) -> str:
        sections: list[str] = []

        if supplier.sectors:
            sections.append(", ".join(supplier.sectors))
        else:
            sections.append(supplier.legal_name)

        if supplier.description:
            sections.append(supplier.description)

        if supplier.keywords:
            sections.append(f"Capacidades: {', '.join(supplier.keywords)}")

        if supplier.certifications:
            sections.append(f"Certificaciones: {', '.join(supplier.certifications)}")

        return ". ".join(sections) + "."

    def build_item_texts(self, items: Sequence[_ItemLike]) -> list[str]:
        """Construye textos de partidas en formato normalizado.

        Retorna lista de strings: 'nombre: descripción[:200]' o solo 'nombre'.
        Omite partidas con nombre vacío y deduplica conservando el orden.
        """
        seen = set()
        result = []

        for item in items:
            if not item.name:
                continue

            if item.description:
                desc_stripped = item.description.strip()
                desc_truncated = desc_stripped[:200]
                text = f"{item.name}: {desc_truncated}"
            else:
                text = item.name

            if text not in seen:
                seen.add(text)
                result.append(text)

        return result

    def build_keyword_texts(self, supplier: Supplier) -> list[str]:
        """Textos a embeber para representar lo que ofrece el proveedor, uno por keyword.

        Los comparten el puntaje (`CompatibilityScorer`, que los cruza contra las
        partidas de cada candidata) y la búsqueda por partidas del ranking (que
        los cruza contra todo el corpus): si cada uno armara su lista, el canal
        que trae candidatas y el que las puntúa podrían dejar de mirar lo mismo.

        Un proveedor sin keywords se representa con su descripción y, si tampoco
        la tiene, con su razón social: mejor un calce grueso que dejar el calce
        en cero y hundirlo en el ranking por no haber llenado un campo.
        """
        texts = [k.strip() for k in supplier.keywords or [] if k and k.strip()]
        if not texts:
            texts = [(supplier.description or "").strip() or supplier.legal_name]
        return texts

    def build_reranker_query(self, supplier: Supplier) -> str:
        """Construye el query para el reranker en formato calibrado.

        Formato exacto: 'Rubro: <sectores o legal_name>. Productos: <keywords o descripción>.'
        """
        # Rubro: sectores o legal_name
        if supplier.sectors:
            rubro_part = ", ".join(supplier.sectors)
        else:
            rubro_part = supplier.legal_name

        # Productos: keywords o descripción o legal_name
        if supplier.keywords:
            productos_part = ", ".join(supplier.keywords)
        elif supplier.description:
            productos_part = supplier.description
        else:
            productos_part = supplier.legal_name

        return f"Rubro: {rubro_part}. Productos: {productos_part}."
