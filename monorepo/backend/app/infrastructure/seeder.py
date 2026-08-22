from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.repositories.tender_model import RegionModel, TenderStatusModel
from app.shared.constants import (
    CHILE_REGIONS,
    UNKNOWN_REGION_ID,
    UNKNOWN_REGION_NAME,
)


async def seed_database_metadata(session: AsyncSession):
    # Seed de Regiones. La numeración vive en shared/constants para que la
    # ingesta y esta tabla no puedan divergir: cuando eran dos listas separadas,
    # no coincidían en ninguna región.
    regiones_data = {UNKNOWN_REGION_ID: UNKNOWN_REGION_NAME, **CHILE_REGIONS}

    for r_id, r_name in regiones_data.items():
        exists = await session.get(RegionModel, r_id)
        if not exists:
            session.add(RegionModel(id=r_id, name=r_name))
        elif exists.name != r_name:
            # Corrige las bases sembradas con la numeración antigua. El seeder
            # corre en cada arranque, así que es el punto natural para hacerlo
            # sin pedirle una migración manual a nadie.
            exists.name = r_name

    # Seed de Estados. El campo code tiene índice único, por lo que se usa str(id);
    # el código semántico ('publicada', ...) se deriva del status_id vía
    # TENDER_STATUS_CODE_BY_ID al construir la entidad (ver TenderRepository._to_entity).
    estados_data = {
        1: "Publicada",
        2: "Publicada",
        6: "Publicada",
        7: "Cerrada",
        8: "Desierta",
        18: "Adjudicada",
    }
    for e_id, e_name in estados_data.items():
        statement = select(TenderStatusModel).where(TenderStatusModel.id == e_id)
        results = await session.exec(statement)
        if not results.first():
            session.add(TenderStatusModel(id=e_id, code=str(e_id), name=e_name))

    await session.commit()
