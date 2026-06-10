from typing import List, Optional
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
import uuid

from app.domain.entities.tender import utc_now_naive
from app.application.repositories.tender_repository import ITenderRepository, TenderFilters
from app.domain.entities.tender import Tender, TenderItem

from app.infrastructure.repositories.tender_model import (
    TenderModel,
    BuyerInstitutionModel,
    RegionModel,
    TenderStatusModel,
    TenderItemModel,
)


class TenderRepository(ITenderRepository):
    """Concrete repository implementing ITenderRepository with SQLModel."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: TenderModel) -> Tender:
        """Convert DB Model to Domain Entity."""
        return Tender(
            id=model.id,
            code=model.code,
            name=model.name,
            description=model.description,
            status_id=model.status_id,
            status_code=model.status.code if model.status else None,
            published_at=model.published_at,
            closing_at=model.closing_at,
            last_change_at=model.last_change_at,
            buyer_rut=model.buyer_rut,
            buyer_name=model.buyer.name if model.buyer else None,
            buyer_unit=model.buyer_unit,
            province=model.province,
            available_amount_clp=model.available_amount_clp,
            created_at=model.created_at,
            updated_at=model.updated_at,
            items=[
                TenderItem(
                    id=item.id,
                    tender_id=item.tender_id,
                    product_code=item.product_code,
                    name=item.name,
                    description=item.description,
                    quantity=item.quantity,
                    unit_of_measure=item.unit_of_measure,
                )
                for item in (model.items or [])
            ],
        )


    def _to_model(self, entity: Tender) -> TenderModel:
        """Convert Domain Entity to DB Model."""
        return TenderModel(
            id=entity.id,
            code=entity.code,
            name=entity.name,
            description=entity.description,
            status_id=entity.status_id,
            published_at=entity.published_at,
            closing_at=entity.closing_at,
            last_change_at=entity.last_change_at,
            buyer_rut=entity.buyer_rut,
            buyer_unit=entity.buyer_unit,
            province=entity.province,
            available_amount_clp=entity.available_amount_clp,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def get_tenders(self, filters: TenderFilters) -> List[Tender]:
        """Retrieve tenders matching specified filters."""
        query = select(TenderModel).options(
            selectinload(TenderModel.status),
            selectinload(TenderModel.buyer),
            selectinload(TenderModel.items)
        )

        # Apply join if region name filtering is requested
        if filters.regions:
            query = (
                query.join(BuyerInstitutionModel, TenderModel.buyer_rut == BuyerInstitutionModel.rut)
                .join(RegionModel, BuyerInstitutionModel.region_id == RegionModel.id)
                .where(RegionModel.name.in_(filters.regions))
            )

        if filters.ids:
            query = query.where(TenderModel.id.in_(filters.ids))

        if filters.provinces:
            query = query.where(TenderModel.province.in_(filters.provinces))

        result = await self.session.exec(query)
        models = result.all()

        return [self._to_entity(m) for m in models]

    async def get_by_code(self, code: str) -> Optional[TenderModel]:
        statement = select(TenderModel).where(TenderModel.code == code)
        result = await self.session.exec(statement)
        return result.first()

    async def get_or_create_buyer(self, rut: str, name: str, region_id: int) -> str:
        statement = select(BuyerInstitutionModel).where(BuyerInstitutionModel.rut == rut)
        result = await self.session.exec(statement)
        buyer = result.first()
        
        if not buyer:
            now = utc_now_naive()
            buyer = BuyerInstitutionModel(
                rut=rut, name=name, region_id=region_id,
                created_at=now, updated_at=now
            )
            self.session.add(buyer)
            await self.session.flush()
        return rut

    async def get_or_create_status(self, status_id: int) -> int:
        statement = select(TenderStatusModel).where(TenderStatusModel.id == status_id)
        result = await self.session.exec(statement)
        status = result.first()
        
        if not status:
            ESTADOS_MAP = {
                1: "Publicada",
                2: "Publicada",
                6: "Publicada",
                7: "Cerrada",
                8: "Desierta",
                18: "Adjudicada"
            }
            
            if status_id in ESTADOS_MAP:
                name_str = ESTADOS_MAP[status_id]
                code_str = f"{name_str.lower().strip()}_{status_id}"
            else:
                name_str = f"Estado Desconocido ({status_id})"
                code_str = f"desconocido_{status_id}"

            status = TenderStatusModel(
                id=status_id,
                code=code_str,
                name=name_str
            )
            self.session.add(status)
            await self.session.flush()
            
        return status_id

    async def save_complex_tender(self, tender_model: TenderModel, items: List[TenderItemModel]):
        self.session.add(tender_model)
        for item in items:
            self.session.add(item)
        await self.session.commit()

    async def rollback(self) -> None:
        # Limpia buffer
        await self.session.rollback()