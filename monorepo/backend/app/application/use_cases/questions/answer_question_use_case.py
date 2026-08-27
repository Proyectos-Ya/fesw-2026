from uuid import UUID

from app.application.repositories.supplier_repository import ISupplierRepository
from app.shared.datetime_utils import utc_now_naive


class AnswerQuestionUseCase:
    def __init__(self, supplier_repo: ISupplierRepository):
        self.supplier_repo = supplier_repo

    async def execute(self, supplier_id: UUID, field_name: str, answer: str) -> None:
        supplier = await self.supplier_repo.get_by_id(supplier_id)
        if supplier is None:
            supplier = await self.supplier_repo.get_by_user_id(supplier_id)

        if supplier is None:
            raise ValueError(
                f"No se encontró ninguna empresa vinculada al ID: {supplier_id}"
            )

        if supplier.keywords is None:
            supplier.keywords = []

        new_keyword = f"{field_name}:{answer}"

        supplier.keywords = [
            kw for kw in supplier.keywords if not kw.startswith(f"{field_name}:")
        ]

        supplier.keywords.append(new_keyword)
        supplier.updated_at = utc_now_naive()

        await self.supplier_repo.update(supplier)
