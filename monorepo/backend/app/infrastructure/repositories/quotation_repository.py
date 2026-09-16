from uuid import UUID, uuid4

from sqlalchemy import delete
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.quotation import MaterialItem, Quotation, QuotationInput
from app.infrastructure.repositories.quotation_model import (
    QuotationMaterialModel,
    QuotationModel,
)
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.shared.datetime_utils import utc_now_naive


class QuotationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _model(self, supplier_id: UUID, tender_id: UUID) -> QuotationModel | None:
        result = await self.session.exec(
            select(QuotationModel).where(
                QuotationModel.supplier_id == supplier_id,
                QuotationModel.tender_id == tender_id,
            )
        )
        return result.first()

    async def get(self, supplier_id: UUID, tender_id: UUID) -> Quotation | None:
        model = await self._model(supplier_id, tender_id)
        if model is None:
            return None
        result = await self.session.exec(
            select(QuotationMaterialModel)
            .where(QuotationMaterialModel.quotation_id == model.id)
            .order_by(QuotationMaterialModel.position)
        )
        return Quotation(
            id=model.id,
            supplier_id=supplier_id,
            tender_id=tender_id,
            currency=model.currency,
            updated_at=model.updated_at,
            items=[
                MaterialItem(
                    description=row.description,
                    unit=row.unit,
                    quantity=row.quantity,
                    unit_price=row.unit_price,
                )
                for row in result.all()
            ],
        )

    async def save(
        self, supplier_id: UUID, tender_id: UUID, data: QuotationInput
    ) -> Quotation:
        try:
            # Serializa también la primera creación: no existe aún una cotización
            # que bloquear. Toda la sustitución de materiales es una transacción.
            await self.session.exec(
                select(SupplierModel)
                .where(SupplierModel.id == supplier_id)
                .with_for_update()
            )
            model = await self._model(supplier_id, tender_id)
            if model is None:
                model = QuotationModel(
                    id=uuid4(),
                    supplier_id=supplier_id,
                    tender_id=tender_id,
                    currency=data.currency,
                    updated_at=utc_now_naive(),
                )
                self.session.add(model)
                await self.session.flush()
            model.currency = data.currency
            model.updated_at = utc_now_naive()
            await self.session.exec(
                delete(QuotationMaterialModel).where(
                    QuotationMaterialModel.quotation_id == model.id
                )
            )
            for position, item in enumerate(data.items):
                self.session.add(
                    QuotationMaterialModel(
                        id=uuid4(),
                        quotation_id=model.id,
                        position=position,
                        description=item.description,
                        unit=item.unit,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                    )
                )
            result = Quotation(
                id=model.id,
                supplier_id=supplier_id,
                tender_id=tender_id,
                currency=data.currency,
                items=data.items,
                updated_at=model.updated_at,
            )
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise
