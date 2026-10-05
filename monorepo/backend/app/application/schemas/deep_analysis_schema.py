from app.domain.entities.deep_analysis import DeepAnalysis


class DeepAnalysisResponse(DeepAnalysis):
    """El análisis más si dejó de estar al día.

    La ficha lo consulta sin generar, así que necesita distinguir 'vigente' de
    'escrito con datos anteriores' para ofrecer el botón de actualizar.
    """

    is_outdated: bool = False
