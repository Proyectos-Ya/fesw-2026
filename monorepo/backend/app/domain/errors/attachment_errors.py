"""Errores de la subida manual de anexos (plan 233, decisión 2).

Cada uno lleva un `code` estable, que es lo que el frontend usa para decidir qué
mostrar, y un mensaje en español ya listo para la persona. `extra` son los datos
que acompañan al código (por ejemplo el nombre esperado). El router los traduce
a una respuesta `{"detail", "code", ...extra}`; los mensajes de 403 nunca
contienen "revocado", porque el frontend trata esa palabra como cierre de sesión.
"""

from typing import ClassVar

from app.domain.entities.attachment_file import AttachmentFile


class AttachmentUploadError(Exception):
    code: ClassVar[str] = "attachment_upload_error"

    def __init__(self, message: str, **extra: object) -> None:
        super().__init__(message)
        self.message = message
        self.extra = extra


class AttachmentNotFound(AttachmentUploadError):
    code = "attachment_not_found"

    def __init__(self) -> None:
        super().__init__("El anexo no existe en esta licitación o Mercado Público lo retiró.")


class AttachmentTooLarge(AttachmentUploadError):
    code = "file_too_large"

    def __init__(self, max_size_bytes: int) -> None:
        super().__init__(
            f"El archivo supera el máximo de {max_size_bytes // (1024 * 1024)} MB.",
            max_size_bytes=max_size_bytes,
        )


class AttachmentExtensionMismatch(AttachmentUploadError):
    code = "attachment_extension_mismatch"

    def __init__(self, expected_ext: str, received_ext: str, expected_name: str) -> None:
        esperado = f".{expected_ext}" if expected_ext else "un archivo sin extensión"
        super().__init__(
            f"La extensión no coincide con el anexo «{expected_name}»: se esperaba {esperado}.",
            expected_ext=expected_ext,
            received_ext=received_ext,
            expected_name=expected_name,
        )


class AttachmentNameMismatch(AttachmentUploadError):
    code = "attachment_name_mismatch"

    def __init__(self, expected_name: str) -> None:
        super().__init__(
            f"El archivo no corresponde a este anexo. Se esperaba «{expected_name}».",
            expected_name=expected_name,
        )


class AttachmentAlreadyUploaded(AttachmentUploadError):
    code = "attachment_already_uploaded"

    def __init__(self) -> None:
        super().__init__(
            "Tu empresa ya subió otro archivo para este anexo. Bórralo antes de subir uno nuevo."
        )


class ConcurrentUploadConflict(AttachmentUploadError):
    code = "upload_in_progress"

    def __init__(self) -> None:
        super().__init__(
            "Este archivo ya se está subiendo. Espera un momento y vuelve a intentarlo."
        )


class UploadQuotaExceeded(AttachmentUploadError):
    code = "quota_exceeded"

    def __init__(self, *, used: int, limit: int) -> None:
        super().__init__(
            f"Tu empresa alcanzó el tope de {limit} subidas de anexos de este mes. "
            "Se renueva el día 1 (hora de Chile).",
            used=used,
            limit=limit,
        )


class AttachmentStorageUnavailable(AttachmentUploadError):
    code = "storage_unavailable"

    def __init__(self) -> None:
        super().__init__("La subida de anexos no está disponible en este momento.")


class UploadNotFound(AttachmentUploadError):
    code = "upload_not_found"

    def __init__(self) -> None:
        super().__init__("No encontramos esa subida.")


class UploadNotInProgress(AttachmentUploadError):
    code = "upload_not_in_progress"

    def __init__(self) -> None:
        super().__init__("Esta subida ya no está en curso. Vuelve a subir el archivo.")


class UploadedObjectMissing(AttachmentUploadError):
    code = "object_missing"

    def __init__(self) -> None:
        super().__init__("Todavía no recibimos el archivo. Vuelve a intentarlo.")


class UploadVerificationFailed(AttachmentUploadError):
    code = "upload_verification_failed"

    def __init__(self, file: AttachmentFile) -> None:
        super().__init__(
            "El archivo que llegó no coincide con el que elegiste (tamaño o huella "
            "distintos). Vuelve a subirlo."
        )
        self.file = file


class AttachmentFileNotFound(AttachmentUploadError):
    code = "file_not_found"

    def __init__(self) -> None:
        super().__init__("No encontramos ese archivo.")


class NotAttachmentFileOwner(AttachmentUploadError):
    code = "not_owner"

    def __init__(self) -> None:
        super().__init__("Solo la empresa que subió el archivo puede borrarlo.")


class AttachmentFileIsShared(AttachmentUploadError):
    code = "file_is_shared"

    def __init__(self) -> None:
        super().__init__("El archivo ya está compartido con otras empresas y no se puede borrar.")
