class TenderChatError(Exception):
    """Base exception for tender chat errors."""
    pass


class TenderChatQueryTooLongError(TenderChatError):
    def __init__(self, message: str = "La consulta supera el límite de 1000 caracteres."):
        super().__init__(message)


class TenderAssistantUnavailableError(TenderChatError):
    def __init__(self, message: str = "El asistente virtual se encuentra temporalmente fuera de servicio."):
        super().__init__(message)


class UnsupportedDocumentTypeError(TenderChatError):
    def __init__(self, message: str = "Tipo de archivo no permitido. Solo se aceptan PDF, XLSX y PNG."):
        super().__init__(message)


class DocumentNotFoundError(TenderChatError):
    def __init__(self, message: str = "El documento solicitado no existe o no pertenece a este chat."):
        super().__init__(message)


class MaxDocumentsExceededError(TenderChatError):
    def __init__(self, message: str = "Se ha alcanzado el límite máximo de documentos adjuntos por chat."):
        super().__init__(message)
