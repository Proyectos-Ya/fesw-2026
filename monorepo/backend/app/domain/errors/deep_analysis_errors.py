class InvalidPromptInstruction(Exception):
    """Excepción lanzada cuando la instrucción de refinamiento del usuario viola reglas de seguridad (Prompt Injection)."""

    def __init__(
        self,
        message: str = "Se detectó un intento de manipulación del prompt (Prompt Injection).",
    ):
        super().__init__(message)


class DeepAnalysisServiceError(Exception):
    """Excepción lanzada cuando ocurre un error al consumir el servicio de IA externo (Gemini)."""

    def __init__(self, message: str):
        super().__init__(message)
