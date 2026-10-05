class DocumentAnalysisAndQuotationError(Exception):
    """Excepción base para errores en el servicio unificado de análisis y cotización."""

    def __init__(self, message: str):
        super().__init__(message)


class DocumentAnalysisAndQuotationServiceError(DocumentAnalysisAndQuotationError):
    """Excepción lanzada cuando la llamada o procesamiento con Gemini falla."""
    pass
