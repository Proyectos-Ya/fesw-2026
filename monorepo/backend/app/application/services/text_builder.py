from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender, TenderItem


class TextBuilder:
    """
    Construye representaciones textuales simétricas para licitaciones y proveedores.
    """

    def build_from_tender(self, tender: Tender, items: list[TenderItem], buyer_name: str) -> str:
        """
        Construye la representación de texto para una licitación (tender) siguiendo la estrategia requerida.
        """
        parts = [
            f"Title: {tender.name}",
            f"Description: {tender.description if tender.description else ''}"
        ]

        items_parts = ["Items Requested:"]
        for item in items:
            desc = f": {item.description}" if item.description else ""
            items_parts.append(f"- {item.name}{desc}")

        parts.append("\n".join(items_parts))
        parts.append(f"Buyer: {buyer_name} ({tender.buyer_unit})")

        return "\n".join(parts)


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
            sections.append(
                f"Certificaciones: {', '.join(supplier.certifications)}"
            )

        return ". ".join(sections) + "."
