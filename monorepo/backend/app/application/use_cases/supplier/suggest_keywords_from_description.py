from app.application.services.company_profiling.keyword_extractor import (
    suggest_keywords,
)


class SuggestKeywordsFromDescriptionUseCase:
    """Sugiere palabras clave a partir de la descripción que el usuario escribió.

    Extracción léxica, sin IA ni servicios externos: no guarda nada y no usa la
    cuota de ningún proveedor. El usuario decide cuáles agrega al perfil.
    """

    def execute(self, description: str, existing_keywords: list[str]) -> list[str]:
        return suggest_keywords(description, existing_keywords)
