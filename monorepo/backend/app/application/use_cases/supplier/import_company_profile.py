from app.application.services.company_lookup_service import ICompanyLookupService
from app.application.services.company_profiling.profile_builder import (
    build_profile_draft,
)
from app.domain.entities.company_profile import CompanyProfileDraft
from app.domain.entities.supplier import is_valid_rut
from app.domain.errors.company_lookup_errors import (
    CompanyLookupNotConfigured,
    InvalidRutForLookup,
)


def normalize_rut(rut: str) -> str:
    """`76.086.428-5` → `76086428-5`, el formato que esperan las fuentes."""
    clean = rut.replace(".", "").replace(" ", "").upper()
    if "-" not in clean and len(clean) > 1:
        clean = f"{clean[:-1]}-{clean[-1]}"
    return clean


class ImportCompanyProfileUseCase:
    """Sugiere regiones, rubros y palabras clave a partir del RUT de la empresa (HdU 16).

    No guarda nada: devuelve un borrador que el usuario revisa en el wizard.
    """

    def __init__(self, lookup_service: ICompanyLookupService | None) -> None:
        self._lookup_service = lookup_service

    async def execute(self, rut: str) -> CompanyProfileDraft:
        if self._lookup_service is None:
            raise CompanyLookupNotConfigured()

        normalized = normalize_rut(rut)
        # Un RUT mal tipeado no merece una consulta a un servicio que cobra por ella.
        if not is_valid_rut(normalized):
            raise InvalidRutForLookup(rut)

        record = await self._lookup_service.lookup(normalized)
        return build_profile_draft(record)
