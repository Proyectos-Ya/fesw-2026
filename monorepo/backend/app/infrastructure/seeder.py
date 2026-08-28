from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.infrastructure.repositories.tender_model import TenderStatusModel, RegionModel

async def seed_database_metadata(session: AsyncSession):
    # Seed de Regiones
    regiones_data = {
        1: "Arica y Parinacota", 2: "Tarapacá", 3: "Antofagasta", 4: "Atacama",
        5: "Coquimbo", 6: "Valparaíso", 7: "Metropolitana de Santiago", 
        8: "Libertador General Bernardo O'Higgins", 9: "Maule", 10: "Ñuble",
        11: "Biobío", 12: "La Araucanía", 13: "Los Ríos", 14: "Los Lagos",
        15: "Aysén del General Carlos Ibáñez del Campo", 16: "Magallanes y de la Antártica Chilena"
    }
    
    for r_id, r_name in regiones_data.items():
        exists = await session.get(RegionModel, r_id)
        if not exists:
            session.add(RegionModel(id=r_id, name=r_name))

    # Seed de Estados. El campo code tiene índice único, por lo que se usa str(id);
    # el código semántico ('publicada', ...) se deriva del status_id vía
    # TENDER_STATUS_CODE_BY_ID al construir la entidad (ver TenderRepository._to_entity).
    estados_data = {
        1: "Publicada",
        2: "Publicada",
        6: "Publicada",
        7: "Cerrada",
        8: "Desierta",
        18: "Adjudicada"
    }
    for e_id, e_name in estados_data.items():
        statement = select(TenderStatusModel).where(TenderStatusModel.id == e_id)
        results = await session.exec(statement)
        if not results.first():
            session.add(TenderStatusModel(id=e_id, code=str(e_id), name=e_name))

    await session.commit()