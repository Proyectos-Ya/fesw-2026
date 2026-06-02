from app.domain.entities.licitacion import Licitacion
from app.domain.entities.proveedor import Proveedor


class TextBuilder:
    """
    Construye representaciones textuales simétricas para licitaciones y proveedores.

    Formato compartido (4 secciones con datos completos, 1 con datos mínimos):
      {concepto_principal}. {descripcion_libre}.
      {Etiqueta_A}: {lista_A}. {Etiqueta_B}: {lista_B}.

    La simetría estructural es un requisito no negociable: si los dos documentos
    se representan con estructuras distintas, la similitud coseno entre sus
    vectores pierde significado aunque el modelo de embeddings sea el mismo.
    """

    def build_from_licitacion(self, licitacion: Licitacion) -> str:
        sections: list[str] = []

        sections.append(licitacion.nombre)

        if licitacion.descripcion:
            sections.append(licitacion.descripcion)

        if licitacion.categorias:
            sections.append(f"Categorías: {', '.join(licitacion.categorias)}")

        if licitacion.items:
            items_text = ", ".join(
                f"{item.nombre}: {item.descripcion}"
                if item.descripcion
                else item.nombre
                for item in licitacion.items
            )
            sections.append(f"Items: {items_text}")

        return ". ".join(sections) + "."

    def build_from_proveedor(self, proveedor: Proveedor) -> str:
        sections: list[str] = []

        if proveedor.rubros:
            sections.append(", ".join(proveedor.rubros))
        else:
            sections.append(proveedor.razon_social)

        if proveedor.descripcion_libre:
            sections.append(proveedor.descripcion_libre)

        if proveedor.palabras_clave:
            sections.append(f"Capacidades: {', '.join(proveedor.palabras_clave)}")

        if proveedor.certificaciones:
            sections.append(
                f"Certificaciones: {', '.join(proveedor.certificaciones)}"
            )

        return ". ".join(sections) + "."
