import io
import struct
import zipfile
from typing import Optional

from app.application.services.document_validator_service import (
    IDocumentValidatorService,
    DocumentValidationResult,
)


class DocumentValidatorService(IDocumentValidatorService):
    """Implementación técnica del validador de integridad estructural para documentos adjuntos (PDF, XLSX, PNG)."""

    ALLOWED_TYPES = {"pdf", "xlsx", "png"}

    def _resolve_file_type(self, file_name: str, declared_type: Optional[str] = None) -> str:
        if declared_type and declared_type.strip():
            return declared_type.strip().lower()
        if "." in file_name:
            return file_name.rsplit(".", 1)[-1].strip().lower()
        return ""

    def _validate_pdf(self, file_bytes: bytes, file_name: str) -> DocumentValidationResult:
        if len(file_bytes) < 32:
            return DocumentValidationResult(
                is_valid=False,
                file_type="pdf",
                error_message=f"El archivo PDF '{file_name}' es demasiado pequeño o está truncado.",
            )

        # Verificar cabecera %PDF- en los primeros 1024 bytes
        header_sample = file_bytes[:1024]
        if b"%PDF-" not in header_sample:
            return DocumentValidationResult(
                is_valid=False,
                file_type="pdf",
                error_message=f"El archivo '{file_name}' no posee una cabecera PDF válida o está dañado.",
            )

        # Verificar que no sea un archivo severamente truncado
        # Los archivos PDF deben tener marcadores de estructura como trailer, xref o %%EOF al final
        tail_sample = file_bytes[-1024:] if len(file_bytes) > 1024 else file_bytes
        if not (b"%%EOF" in tail_sample or b"xref" in tail_sample or b"startxref" in tail_sample or b"trailer" in file_bytes or b"obj" in file_bytes):
            return DocumentValidationResult(
                is_valid=False,
                file_type="pdf",
                error_message=f"El archivo PDF '{file_name}' está dañado o incompleto (falta terminador %%EOF).",
            )

        return DocumentValidationResult(is_valid=True, file_type="pdf")

    def _validate_xlsx(self, file_bytes: bytes, file_name: str) -> DocumentValidationResult:
        if len(file_bytes) < 30 or not file_bytes.startswith(b"PK"):
            return DocumentValidationResult(
                is_valid=False,
                file_type="xlsx",
                error_message=f"El archivo '{file_name}' no posee una estructura ZIP válida para documentos Excel.",
            )

        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
                # Comprobar integridad básica del contenedor ZIP
                bad_file = zf.testzip()
                if bad_file is not None:
                    return DocumentValidationResult(
                        is_valid=False,
                        file_type="xlsx",
                        error_message=f"El archivo Excel '{file_name}' contiene componentes corruptos: {bad_file}.",
                    )
                # Verificar presencia de descriptor de contenido
                namelist = zf.namelist()
                if not any("[Content_Types].xml" in name or "xl/" in name for name in namelist):
                    return DocumentValidationResult(
                        is_valid=False,
                        file_type="xlsx",
                        error_message=f"El archivo '{file_name}' no es un libro Excel OpenXML válido.",
                    )
        except Exception as e:
            return DocumentValidationResult(
                is_valid=False,
                file_type="xlsx",
                error_message=f"El archivo Excel '{file_name}' está dañado o corrupto: {e}",
            )

        return DocumentValidationResult(is_valid=True, file_type="xlsx")

    def _validate_png(self, file_bytes: bytes, file_name: str) -> DocumentValidationResult:
        # Magic bytes PNG: 89 50 4E 47 0D 0A 1A 0A
        png_magic = b"\x89PNG\r\n\x1a\n"
        if not file_bytes.startswith(png_magic) or len(file_bytes) < 33:
            return DocumentValidationResult(
                is_valid=False,
                file_type="png",
                error_message=f"El archivo '{file_name}' no posee una cabecera PNG válida o está incompleto.",
            )

        try:
            # Estructura del chunk IHDR inmediatamente después de la cabecera
            # Offset 8..12: Longitud IHDR (debe ser 13)
            # Offset 12..16: Chunk Type "IHDR"
            ihdr_len, ihdr_type = struct.unpack(">I4s", file_bytes[8:16])
            if ihdr_type != b"IHDR" or ihdr_len != 13:
                return DocumentValidationResult(
                    is_valid=False,
                    file_type="png",
                    error_message=f"La imagen PNG '{file_name}' tiene un bloque de cabecera IHDR inválido.",
                )

            # Verificar que contenga al menos un chunk IEND al final o cerca del final
            if b"IEND" not in file_bytes[-100:]:
                return DocumentValidationResult(
                    is_valid=False,
                    file_type="png",
                    error_message=f"La imagen PNG '{file_name}' está truncada o incompleta (falta bloque IEND).",
                )
        except Exception as e:
            return DocumentValidationResult(
                is_valid=False,
                file_type="png",
                error_message=f"La imagen PNG '{file_name}' está dañada: {e}",
            )

        return DocumentValidationResult(is_valid=True, file_type="png")

    def validate_integrity(
        self,
        file_bytes: bytes,
        file_name: str,
        declared_type: Optional[str] = None,
    ) -> DocumentValidationResult:
        if not file_bytes or len(file_bytes) == 0:
            return DocumentValidationResult(
                is_valid=False,
                file_type=declared_type or "",
                error_message=f"El archivo '{file_name}' está vacío.",
            )

        file_type = self._resolve_file_type(file_name=file_name, declared_type=declared_type)

        if file_type not in self.ALLOWED_TYPES:
            return DocumentValidationResult(
                is_valid=False,
                file_type=file_type,
                error_message=f"Tipo de archivo no soportado: '{file_type}'. Solo se permiten PDF, XLSX y PNG.",
            )

        if file_type == "pdf":
            return self._validate_pdf(file_bytes=file_bytes, file_name=file_name)
        elif file_type == "xlsx":
            return self._validate_xlsx(file_bytes=file_bytes, file_name=file_name)
        elif file_type == "png":
            return self._validate_png(file_bytes=file_bytes, file_name=file_name)

        return DocumentValidationResult(
            is_valid=False,
            file_type=file_type,
            error_message="Formato desconocido.",
        )
