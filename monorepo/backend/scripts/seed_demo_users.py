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
from app.infrastructure.repositories.supplier_member_model import SupplierMemberModel
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.user_model import UserModel
from app.infrastructure.services.password_hasher import BcryptPasswordHasher

PASSWORD_TEST = "Password123!"

USERS_DATA = [
    {
        "email": "admin1@chiripa.cl",
        "full_name": "Carlos Admin Alfa",
        "companies": [
            {
                "rut": "76.111.111-1",
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
                "rut": "77.222.222-2",
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
            {"rut": "76.111.111-1", "role": MemberRole.MEMBER}
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
            {"rut": "77.222.222-2", "role": MemberRole.VIEWER}
        ],
    },
]


async def seed_users():
    hasher = BcryptPasswordHasher()
    hashed_pwd = hasher.hash(PASSWORD_TEST)

    async with async_session_maker() as session:
        print("🌱 Sembrando 5 usuarios de demostración...")
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
                )
                session.add(user)
                await session.flush()
                print(f"  ✓ Usuario creado: {email}")
            else:
                print(f"  · Usuario ya existe: {email}")

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
                        description=f"Empresa de demostración {cdata['trade_name']}",
                        sectors=["Tecnología", "Construcción"],
                        keywords=["servicios", "consultoría", "obras"],
                    )
                    session.add(supplier)
                    await session.flush()
                    print(f"    ✓ Empresa creada: {cdata['legal_name']} ({rut})")
                else:
                    print(f"    · Empresa ya existe: {cdata['legal_name']}")

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
                        )
                    )
                    print(f"    ✓ Membresía {cdata['role']} asignada para {email}")

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
                            )
                        )
                        print(f"  ✓ Membresía extra {extra['role']} asignada para {user.email} en {supplier.legal_name}")

        await session.commit()
        print("✨ Seeding de usuarios y empresas completado con éxito.")


if __name__ == "__main__":
    asyncio.run(seed_users())
