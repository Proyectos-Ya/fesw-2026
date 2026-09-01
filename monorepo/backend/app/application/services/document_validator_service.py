from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel


class DocumentValidationResult(BaseModel):
    """Resultado de la validación estructural y de integridad de un documento."""
    is_valid: bool
    file_type: str
    error_message: Optional[str] = None


class IDocumentValidatorService(ABC):
    """Contrato del servicio para validar la integridad técnica de archivos antes de su procesamiento."""

    @abstractmethod
    def validate_integrity(
        self,
        file_bytes: bytes,
        file_name: str,
        declared_type: Optional[str] = None,
    ) -> DocumentValidationResult:
        """Valida que los bytes correspondan a un archivo no corrupto y legible del tipo especificado (PDF, XLSX, PNG)."""
        pass
