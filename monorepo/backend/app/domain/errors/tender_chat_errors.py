class TenderChatError(Exception):
    """Base exception for tender chat errors."""

    pass


class TenderChatQueryTooLongError(TenderChatError):
    def __init__(
        self, message: str = "La consulta supera el límite de 1000 caracteres."
    ):
        super().__init__(message)


class TenderAssistantUnavailableError(TenderChatError):
    def __init__(
        self,
        message: str = "El asistente virtual se encuentra temporalmente fuera de servicio.",
    ):
        super().__init__(message)


class UnsupportedDocumentTypeError(TenderChatError):
    def __init__(
        self,
        message: str = "Tipo de archivo no permitido. Solo se aceptan PDF, XLSX y PNG.",
    ):
        super().__init__(message)


class DocumentNotFoundError(TenderChatError):
    def __init__(
        self,
        message: str = "El documento solicitado no existe o no pertenece a este chat.",
    ):
        super().__init__(message)


class MaxDocumentsExceededError(TenderChatError):
    def __init__(
        self,
        message: str = "Se ha alcanzado el límite máximo de documentos adjuntos por chat.",
    ):
        super().__init__(message)


class InvalidPromptInstruction(TenderChatError):
    """Excepción lanzada cuando la consulta del usuario intenta manipular el prompt del sistema (Prompt Injection)."""

    def __init__(
        self,
        message: str = "Se detectó un intento de manipulación del prompt (Prompt Injection).",
    ):
        super().__init__(message)


class OutOfScopeQueryError(TenderChatError):
    """Excepción lanzada cuando la consulta está completamente fuera del alcance del asistente de licitaciones."""


class ChatSessionNotFoundError(TenderChatError):
    """Excepción lanzada cuando la sesión de chat no existe o no pertenece al usuario."""
    def __init__(self, message: str = "La sesión de chat solicitada no existe."):
        super().__init__(message)


class ChatHistoryLoadError(TenderChatError):
    """Excepción lanzada cuando ocurre un error al recuperar el historial desde la base de datos."""
    def __init__(
        self,
        message: str = "No se pudo cargar el historial de la conversación. Por favor reintente más tarde o inicie un nuevo chat.",
    ):
        super().__init__(message)


    def __init__(
        self,
        message: str = "La consulta está fuera del ámbito de análisis de esta licitación.",
    ):
        super().__init__(message)
