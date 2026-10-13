"""Errores del procesamiento de anexos y extracción con Gemini (plan 233, decisión 4)."""


class AttachmentProcessingError(Exception):
    """Error base de procesamiento de anexos."""


class AttachmentExtractionUnavailable(AttachmentProcessingError):
    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int | None = None,
        rate_limited: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after_seconds = retry_after_seconds
        self.rate_limited = rate_limited


class InvalidExtractionResponse(AttachmentProcessingError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AttachmentExtractionRejected(AttachmentProcessingError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ExtractionAlreadyExists(AttachmentProcessingError):
    pass


class FuenteNoVisible(AttachmentProcessingError):
    def __init__(self, extraction_id: object) -> None:
        super().__init__(
            f"La fuente de extracción {extraction_id} no es visible en este alcance"
        )
        self.extraction_id = extraction_id
