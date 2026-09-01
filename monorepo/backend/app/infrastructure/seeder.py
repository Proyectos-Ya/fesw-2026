from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.repositories.tender_model import (
    ComunaModel,
    ProvinciaModel,
    RegionModel,
    TenderStatusModel,
)
from app.shared.comunas import CHILE_COMUNAS, CHILE_PROVINCIAS
from app.shared.constants import TENDER_STATUS_CODE_BY_ID
from app.shared.regions import (
    CHILE_REGIONS,
    UNKNOWN_REGION_ID,
    UNKNOWN_REGION_NAME,
    region_id_by_name,
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

    # Seed de Provincias y Comunas. Ninguna de las tres APIs de Mercado
    # Público entrega este dato directamente (ver PENDIENTES.md 6.16/6.19),
    # así que la fuente es un dataset estático de shared/comunas.py, sembrado
    # una vez y corregido in-place igual que región/estado.
    for p_id, (p_name, region_name) in CHILE_PROVINCIAS.items():
        region_id = region_id_by_name(region_name)
        assert region_id is not None, f"Región desconocida en seed: {region_name!r}"
        provincia = await session.get(ProvinciaModel, p_id)
        if not provincia:
            session.add(ProvinciaModel(id=p_id, name=p_name, region_id=region_id))
        elif provincia.name != p_name or provincia.region_id != region_id:
            provincia.name = p_name
            provincia.region_id = region_id

    provincia_id_by_name = {
        name: p_id for p_id, (name, _region) in CHILE_PROVINCIAS.items()
    }

    for c_id, (c_name, prov_name) in CHILE_COMUNAS.items():
        provincia_id = provincia_id_by_name[prov_name]
        comuna = await session.get(ComunaModel, c_id)
        if not comuna:
            session.add(ComunaModel(id=c_id, name=c_name, provincia_id=provincia_id))
        elif comuna.name != c_name or comuna.provincia_id != provincia_id:
            comuna.name = c_name
            comuna.provincia_id = provincia_id

    await session.commit()
