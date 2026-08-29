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
