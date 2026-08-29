from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.repositories.tender_model import RegionModel, TenderStatusModel
from app.shared.constants import TENDER_STATUS_CODE_BY_ID
from app.shared.regions import (
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

    # Seed de Estados. `code` guarda el `estado.codigo` de la API tal cual, que es
    # lo que lee TenderRepository._to_entity. Antes guardaba str(id) y el código
    # semántico se derivaba de un mapa aparte, heredado de la API de
    # Licitaciones: ahí es donde el 6 figuraba como "publicada" siendo
    # "desierta".
    #
    # Una fila que ya exista con otro código se corrige: las bases sembradas con
    # la numeración vieja seguirían sirviendo el valor equivocado para siempre.
    for e_id, e_code in TENDER_STATUS_CODE_BY_ID.items():
        e_name = e_code.replace("_", " ").capitalize()
        statement = select(TenderStatusModel).where(TenderStatusModel.id == e_id)
        results = await session.exec(statement)
        existente = results.first()
        if not existente:
            session.add(TenderStatusModel(id=e_id, code=e_code, name=e_name))
        elif existente.code != e_code:
            existente.code = e_code
            existente.name = e_name
            session.add(existente)

    await session.commit()
