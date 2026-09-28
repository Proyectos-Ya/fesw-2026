from app.application.repositories.supplier_repository import ISupplierRepository
from app.domain.entities.supplier import format_rut, is_valid_rut


class CheckRutExistsUseCase:
    """Informa si ya existe una empresa registrada con el RUT consultado.

    Permite al formulario de creación detectar el RUT duplicado de forma
    temprana; la garantía definitiva sigue siendo la verificación de
    CreateSupplierUseCase al momento de crear.
    """

    def __init__(self, repo: ISupplierRepository):
        self.repo = repo

    async def execute(self, rut: str) -> bool:
        # Un RUT inválido no puede estar registrado; el válido se busca en el
        # mismo formato canónico con el que se guarda.
        if not is_valid_rut(rut.strip()):
            return False
        return await self.repo.get_by_rut(format_rut(rut)) is not None
