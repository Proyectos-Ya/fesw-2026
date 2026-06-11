from uuid import UUID
from datetime import datetime, timezone
from app.application.repositories.supplier_repository import ISupplierRepository

class AnswerQuestionUseCase:
    def __init__(self, supplier_repo: ISupplierRepository):
        self.supplier_repo = supplier_repo

    async def execute(self, supplier_id: UUID, field_name: str, answer: str) -> None:
        supplier = await self.supplier_repo.get_by_id(supplier_id)
        if not supplier:
            raise ValueError(f"Supplier con ID {supplier_id} no existe.")

        if supplier.keywords is None:
            supplier.keywords = []

        new_keyword = f"{field_name}:{answer}"

        supplier.keywords = [kw for kw in supplier.keywords if not kw.startswith(f"{field_name}:")]

        supplier.keywords.append(new_keyword)
        supplier.updated_at = datetime.now(timezone.utc)

        await self.supplier_repo.update(supplier)