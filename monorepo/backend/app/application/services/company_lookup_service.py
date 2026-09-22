from abc import ABC, abstractmethod

from app.domain.entities.company_profile import CompanyRecord


class ICompanyLookupService(ABC):
    """Fuente externa de datos de empresas por RUT (SRE, Web Empresario).

    Toda implementación devuelve el mismo `CompanyRecord`, sin importar el esquema
    de la API que consulte. Errores esperables: `CompanyNotFoundInSource` y
    `CompanyLookupUnavailable`.
    """

    @abstractmethod
    async def lookup(self, rut: str) -> CompanyRecord:
        """Consulta la empresa. `rut` llega normalizado: `76086428-5`."""
