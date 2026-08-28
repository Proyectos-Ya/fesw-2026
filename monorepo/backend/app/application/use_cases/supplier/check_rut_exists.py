from app.application.repositories.supplier_repository import ISupplierRepository


class CheckRutExistsUseCase:
    """Informa si ya existe una empresa registrada con el RUT consultado.

    Permite al formulario de creación detectar el RUT duplicado de forma
    temprana; la garantía definitiva sigue siendo la verificación de
    CreateSupplierUseCase al momento de crear.
    """

    def __init__(self, repo: ISupplierRepository):
        self.repo = repo

    async def execute(self, rut: str) -> bool:
        return await self.repo.get_by_rut(rut) is not None
