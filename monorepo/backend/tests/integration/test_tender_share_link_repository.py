"""Repositorio de enlaces compartidos contra Postgres real (HdU 19)."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.tender_share_link import TenderShareLink, hash_share_token
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    RegionModel,
    TenderModel,
    TenderStatusModel,
)
from app.infrastructure.repositories.tender_share_link_repository import (
    TenderShareLinkRepository,
)
from app.infrastructure.repositories.user_model import UserModel
from app.shared.datetime_utils import utc_now_naive
from app.shared.regions import CHILE_REGIONS

AHORA = datetime(2026, 9, 28, 12, 0, 0)


async def _escenario(session: AsyncSession) -> tuple[UUID, UUID, UUID]:
    """Crea usuario, empresa y licitación; devuelve sus ids."""
    ahora = utc_now_naive()
    user_id, supplier_id, tender_id = uuid4(), uuid4(), uuid4()
    session.add(RegionModel(id=13, name=CHILE_REGIONS[13]))
    session.add(TenderStatusModel(id=1, code="publicada", name="Publicada"))
    session.add(
        BuyerInstitutionModel(
            rut="12.345.678-9",
            name="Municipalidad de Santiago",
            region_id=13,
            created_at=ahora,
            updated_at=ahora,
        )
    )
    session.add(
        UserModel(
            id=user_id,
            email=f"{user_id.hex[:8]}@demo.cl",
            full_name="Representante",
            created_at=ahora,
            updated_at=ahora,
        )
    )
    session.add(
        SupplierModel(
            id=supplier_id,
            rut="76.123.456-7",
            legal_name="Empresa Alpha SpA",
            created_at=ahora,
            updated_at=ahora,
        )
    )
    session.add(
        TenderModel(
            id=tender_id,
            code="1057539-228-COT26",
            name="Materiales eléctricos",
            status_id=1,
            published_at=ahora,
            closing_at=ahora + timedelta(days=10),
            last_change_at=ahora,
            buyer_rut="12.345.678-9",
            buyer_unit="Operaciones",
            created_at=ahora,
            updated_at=ahora,
        )
    )
    await session.commit()
    return user_id, supplier_id, tender_id


def _emitir(user_id: UUID, supplier_id: UUID, tender_id: UUID, now: datetime = AHORA):
    return TenderShareLink.emitir(
        tender_id=tender_id, supplier_id=supplier_id, created_by=user_id, now=now
    )


async def test_guarda_y_encuentra_por_el_hash_del_token(db_session: AsyncSession):
    ids = await _escenario(db_session)
    repo = TenderShareLinkRepository(db_session)
    enlace, token = _emitir(*ids)

    await repo.save(enlace)

    encontrado = await repo.get_by_token_hash(hash_share_token(token))
    assert encontrado == enlace
    assert await repo.get_by_token_hash(hash_share_token("otro")) is None


async def test_revocar_se_persiste(db_session: AsyncSession):
    ids = await _escenario(db_session)
    repo = TenderShareLinkRepository(db_session)
    enlace, _ = _emitir(*ids)
    await repo.save(enlace)

    await repo.save(enlace.revocar(AHORA + timedelta(hours=1)))

    guardado = await repo.get(enlace.id)
    assert guardado is not None
    assert guardado.revoked_at == AHORA + timedelta(hours=1)


async def test_lista_solo_los_vigentes_del_mas_nuevo_al_mas_viejo(db_session: AsyncSession):
    user_id, supplier_id, tender_id = await _escenario(db_session)
    repo = TenderShareLinkRepository(db_session)
    viejo, _ = _emitir(user_id, supplier_id, tender_id, AHORA - timedelta(days=1))
    nuevo, _ = _emitir(user_id, supplier_id, tender_id, AHORA)
    caducado, _ = _emitir(user_id, supplier_id, tender_id, AHORA - timedelta(days=8))
    revocado, _ = _emitir(user_id, supplier_id, tender_id, AHORA)
    for enlace in (viejo, nuevo, caducado, revocado.revocar(AHORA)):
        await repo.save(enlace)

    vigentes = await repo.list_active(tender_id, supplier_id, AHORA)

    assert [e.id for e in vigentes] == [nuevo.id, viejo.id]


async def test_borrar_la_licitacion_borra_sus_enlaces(db_session: AsyncSession):
    ids = await _escenario(db_session)
    repo = TenderShareLinkRepository(db_session)
    enlace, _ = _emitir(*ids)
    await repo.save(enlace)

    await db_session.delete(await db_session.get(TenderModel, ids[2]))
    await db_session.commit()
    db_session.expunge_all()

    assert await repo.get(enlace.id) is None
