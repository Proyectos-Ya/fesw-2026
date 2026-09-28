"""
Script para sembrar 5 usuarios de demostración y sus empresas asociadas para pruebas de HdU 14.

Uso:
    python -m scripts.seed_demo_users
"""

import asyncio
from uuid import uuid4

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.supplier_member import MemberRole, MemberStatus
from app.infrastructure.db import async_session_maker
from app.infrastructure.repositories.supplier_invitation_model import SupplierInvitationModel
from app.infrastructure.repositories.supplier_member_model import SupplierMemberModel
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.user_model import UserModel
from app.infrastructure.services.password_hasher import BcryptPasswordHasher

from app.shared.datetime_utils import utc_now_naive

PASSWORD_TEST = "Password123!"

USERS_DATA = [
    {
        "email": "admin1@chiripa.cl",
        "full_name": "Carlos Admin Alfa",
        "companies": [
            {
                "rut": "76.111.111-6",
                "legal_name": "Empresa Alfa SpA",
                "trade_name": "Alfa",
                "role": MemberRole.ADMIN,
            }
        ],
    },
    {
        "email": "admin2@chiripa.cl",
        "full_name": "Beatriz Admin Beta",
        "companies": [
            {
                "rut": "77.222.222-K",
                "legal_name": "Empresa Beta Ltda",
                "trade_name": "Beta",
                "role": MemberRole.ADMIN,
            }
        ],
    },
    {
        "email": "multi@chiripa.cl",
        "full_name": "Manuel Multiempresa",
        "companies": [
            {
                "rut": "78.333.333-3",
                "legal_name": "Empresa Gamma S.A.",
                "trade_name": "Gamma",
                "role": MemberRole.ADMIN,
            }
        ],
        "extra_memberships": [
            {"rut": "76.111.111-6", "role": MemberRole.MEMBER}
        ],
    },
    {
        "email": "invitado@chiripa.cl",
        "full_name": "Ignacio Invitado",
        "companies": [],
    },
    {
        "email": "lector@chiripa.cl",
        "full_name": "Laura Lectora",
        "companies": [],
        "extra_memberships": [
            {"rut": "77.222.222-K", "role": MemberRole.VIEWER}
        ],
    },
]


async def seed_users():
    hasher = BcryptPasswordHasher()
    hashed_pwd = hasher.hash(PASSWORD_TEST)
    now = utc_now_naive()

    async with async_session_maker() as session:
        print("[SEED] Sembrando 5 usuarios de demostracion...")
        # Limpiar invitaciones previas para idempotencia de pruebas
        invs = (await session.exec(select(SupplierInvitationModel))).all()
        for inv in invs:
            await session.delete(inv)

        # Eliminar empresa Delta si fue creada en pruebas previas
        deltas = (await session.exec(select(SupplierModel).where(SupplierModel.rut == "79.444.444-7"))).all()
        for d in deltas:
            d_mems = (await session.exec(select(SupplierMemberModel).where(SupplierMemberModel.supplier_id == d.id))).all()
            for dm in d_mems:
                await session.delete(dm)
            await session.delete(d)

        # Limpiar membresias de invitado@chiripa.cl si quedaron de pruebas previas
        inv_u = (await session.exec(select(UserModel).where(UserModel.email == "invitado@chiripa.cl"))).first()
        if inv_u:
            inv_mems = (await session.exec(select(SupplierMemberModel).where(SupplierMemberModel.user_id == inv_u.id))).all()
            for im in inv_mems:
                await session.delete(im)

        await session.commit()

        created_users = {}
        created_suppliers = {}

        for udata in USERS_DATA:
            email = udata["email"]
            stmt = select(UserModel).where(UserModel.email == email)
            res = await session.exec(stmt)
            user = res.first()

            if not user:
                user = UserModel(
                    id=uuid4(),
                    email=email,
                    hashed_password=hashed_pwd,
                    full_name=udata["full_name"],
                    active=True,
                    email_verified=True,
                    created_at=now,
                    updated_at=now,
                )
                session.add(user)
                await session.flush()
                print(f"  [OK] Usuario creado: {email}")
            else:
                print(f"  [INFO] Usuario ya existe: {email}")

            created_users[email] = user

            for cdata in udata["companies"]:
                rut = cdata["rut"]
                s_stmt = select(SupplierModel).where(SupplierModel.rut == rut)
                s_res = await session.exec(s_stmt)
                supplier = s_res.first()

                if not supplier:
                    supplier = SupplierModel(
                        id=uuid4(),
                        user_id=user.id,
                        rut=rut,
                        legal_name=cdata["legal_name"],
                        trade_name=cdata["trade_name"],
                        description=f"Empresa de demostracion {cdata['trade_name']}",
                        sectors=["Tecnologia", "Construccion"],
                        keywords=["servicios", "consultoria", "obras"],
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(supplier)
                    await session.flush()
                    print(f"    [OK] Empresa creada: {cdata['legal_name']} ({rut})")
                else:
                    print(f"    [INFO] Empresa ya existe: {cdata['legal_name']}")

                created_suppliers[rut] = supplier

                m_stmt = select(SupplierMemberModel).where(
                    SupplierMemberModel.user_id == user.id,
                    SupplierMemberModel.supplier_id == supplier.id,
                )
                m_res = await session.exec(m_stmt)
                member = m_res.first()
                if not member:
                    session.add(
                        SupplierMemberModel(
                            id=uuid4(),
                            user_id=user.id,
                            supplier_id=supplier.id,
                            role=cdata["role"],
                            status=MemberStatus.ACTIVE,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    print(f"    [OK] Membresia {cdata['role']} asignada para {email}")

        for udata in USERS_DATA:
            user = created_users[udata["email"]]
            for extra in udata.get("extra_memberships", []):
                supplier = created_suppliers.get(extra["rut"])
                if not supplier:
                    s_stmt = select(SupplierModel).where(SupplierModel.rut == extra["rut"])
                    supplier = (await session.exec(s_stmt)).first()

                if supplier:
                    m_stmt = select(SupplierMemberModel).where(
                        SupplierMemberModel.user_id == user.id,
                        SupplierMemberModel.supplier_id == supplier.id,
                    )
                    member = (await session.exec(m_stmt)).first()
                    if not member:
                        session.add(
                            SupplierMemberModel(
                                id=uuid4(),
                                user_id=user.id,
                                supplier_id=supplier.id,
                                role=extra["role"],
                                status=MemberStatus.ACTIVE,
                                created_at=now,
                                updated_at=now,
                            )
                        )
                        print(f"  [OK] Membresia extra {extra['role']} asignada para {user.email} en {supplier.legal_name}")

        await session.commit()
        print("[SEED] Seeding de usuarios y empresas completado con exito.")


if __name__ == "__main__":
    asyncio.run(seed_users())
