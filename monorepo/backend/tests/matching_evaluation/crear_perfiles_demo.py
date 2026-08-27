"""Crea tres cuentas de proveedor de prueba, en rubros distintos.

Complemento del Modo A: sin un proveedor con perfil no hay a quién recomendarle
nada, así que el dashboard queda vacío aunque la base tenga corpus.

    python tests/matching_evaluation/crear_perfiles_demo.py

Las contraseñas están escritas acá a propósito: son cuentas de demostración y su
valor es que cualquiera del equipo pueda entrar sin coordinarse. Eso solo es
aceptable si es **imposible** que lleguen a un entorno real, de ahí las guardas
de `_verificar_entorno_de_desarrollo`.

Al terminar imprime las credenciales.
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.models import Distance, VectorParams  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlmodel import select  # noqa: E402
from sqlmodel.ext.asyncio.session import AsyncSession  # noqa: E402

from app.application.services.text_builder import TextBuilder  # noqa: E402
from app.config import settings  # noqa: E402
from app.domain.entities.supplier import Supplier  # noqa: E402
from app.infrastructure.db import engine  # noqa: E402
from app.infrastructure.repositories.qdrant_supplier_repository import (  # noqa: E402
    QdrantSupplierRepository,
)
from app.infrastructure.repositories.supplier_model import SupplierModel  # noqa: E402
from app.infrastructure.repositories.user_model import UserModel  # noqa: E402
from app.infrastructure.services.bge_m3_embedding_service import (  # noqa: E402
    BgeM3EmbeddingService,
)
from app.infrastructure.services.password_hasher import (  # noqa: E402
    BcryptPasswordHasher,
)

# Dominio reservado por la RFC 2606 justamente para esto: no existe ni puede
# registrarse, así que estas cuentas nunca reciben correo real.
CONTRASENA = "demo1234"

PERFILES = [
    {
        "email": "construccion@demo.invalid",
        "full_name": "Demo Construcción",
        "rut": "76.111.111-6",
        "legal_name": "Constructora Demo Ltda.",
        "trade_name": "Demo Obras Civiles",
        "description": (
            "Ejecución de obras menores de construcción, pintura de edificios "
            "públicos, mantención de techumbres, reparaciones eléctricas, "
            "gasfitería y mejoramiento de espacios comunitarios."
        ),
        "regions": [
            "Región Metropolitana de Santiago",
            "Región de Valparaíso",
            "Región del Biobío",
        ],
        "sectors": ["Construcción", "Obras Menores", "Mantención de Infraestructura"],
        "keywords": [
            "construcción",
            "pintura",
            "techumbre",
            "reparación",
            "gasfitería",
            "obras civiles",
        ],
    },
    {
        "email": "tecnologia@demo.invalid",
        "full_name": "Demo Tecnología",
        "rut": "76.222.222-1",
        "legal_name": "TecnoDemo SpA",
        "trade_name": "Demo Soluciones Digitales",
        "description": (
            "Desarrollo de software a medida, aplicaciones web, soluciones "
            "cloud, ciberseguridad y soporte de infraestructura TI."
        ),
        "regions": [
            "Región Metropolitana de Santiago",
            "Región de Los Ríos",
        ],
        "sectors": ["Desarrollo de Software", "Informática", "Telecomunicaciones"],
        "keywords": [
            "software",
            "cloud",
            "desarrollo web",
            "licencias",
            "servidor",
            "soporte ti",
        ],
    },
    {
        "email": "salud@demo.invalid",
        "full_name": "Demo Salud",
        "rut": "76.333.333-7",
        "legal_name": "Distribuidora Médica Demo SpA",
        "trade_name": "Demo Insumos Clínicos",
        "description": (
            "Importación y comercialización de insumos médicos descartables, "
            "material de curación, jeringas, guantes quirúrgicos y equipamiento "
            "de diagnóstico menor para hospitales y CESFAM."
        ),
        "regions": [
            "Región Metropolitana de Santiago",
            "Región de Los Lagos",
            "Región de La Araucanía",
        ],
        "sectors": ["Insumos Médicos", "Salud", "Equipamiento Clínico"],
        "keywords": [
            "insumos médicos",
            "jeringas",
            "guantes",
            "curación",
            "clínico",
            "hospital",
        ],
    },
]

# Cada perfil declara regiones distintas, y las tres incluyen la Metropolitana.
# Importa porque `rank_tenders` filtra de forma ESTRICTA por región: un perfil
# solo ve licitaciones de las suyas. Con este reparto se puede comparar el efecto
# del filtro entre perfiles sin que ninguno se quede sin resultados.

_HOSTS_DE_DESARROLLO = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def _verificar_entorno_de_desarrollo(forzar: bool) -> None:
    """Impide que estas cuentas lleguen a un entorno real.

    Son credenciales conocidas y publicadas en el repositorio: en producción
    equivalen a una puerta abierta. Se comprueban dos cosas independientes,
    porque cualquiera de las dos puede estar mal por descuido:

    1. `IS_DEV` debe estar activo.
    2. La base debe ser local. Un `IS_DEV=true` olvidado en una máquina que
       apunta a Supabase en la nube pasaría el primer control.
    """
    problemas = []
    if not settings.is_dev:
        problemas.append("IS_DEV no está en true")

    host = (make_url(settings.database_url).host or "").lower()
    if host not in _HOSTS_DE_DESARROLLO:
        problemas.append(f"la base no es local (host: {host})")

    if problemas and not forzar:
        raise SystemExit(
            "Cuentas de demostración con contraseña conocida: no se crean acá.\n"
            + "\n".join(f"  - {p}" for p in problemas)
            + "\n\nSi de verdad es un entorno desechable, repite con --forzar."
        )
    if problemas:
        print(f"[AVISO] --forzar activo pese a: {', '.join(problemas)}", flush=True)


def _asegurar_coleccion(cliente: QdrantClient) -> None:
    """Crea la colección `suppliers` si falta.

    Normalmente la crea el arranque de la aplicación (`main.py`), pero este
    script se corre antes de levantarla, así que no puede darla por hecha.
    """
    existentes = {c.name for c in cliente.get_collections().collections}
    if "suppliers" not in existentes:
        cliente.create_collection(
            collection_name="suppliers",
            vectors_config=VectorParams(
                size=settings.embedding_vector_size, distance=Distance.COSINE
            ),
        )
        print("[QDRANT] Colección 'suppliers' creada.", flush=True)


async def main(forzar: bool) -> None:
    _verificar_entorno_de_desarrollo(forzar)

    hasher = BcryptPasswordHasher()
    constructor = TextBuilder()
    embeddings = BgeM3EmbeddingService()
    cliente_qdrant = QdrantClient(url=settings.qdrant_url)
    _asegurar_coleccion(cliente_qdrant)
    vectores = QdrantSupplierRepository(cliente_qdrant)

    creados = []
    async with AsyncSession(engine) as sesion:
        for datos in PERFILES:
            existente = (
                await sesion.exec(
                    select(UserModel).where(UserModel.email == datos["email"])
                )
            ).first()
            if existente:
                print(f"[SALTA] {datos['email']} ya existe", flush=True)
                continue

            ahora = datetime.utcnow()
            usuario = UserModel(
                id=uuid4(),
                email=datos["email"],
                hashed_password=hasher.hash(CONTRASENA),
                full_name=datos["full_name"],
                active=True,
                email_verified=True,
                created_at=ahora,
                updated_at=ahora,
            )
            sesion.add(usuario)
            # Sin este flush, el INSERT del proveedor puede salir antes que el
            # del usuario y violar la clave foránea: `user_id` es una FK plana,
            # sin relación declarada, así que SQLAlchemy no conoce el orden.
            await sesion.flush()

            proveedor = SupplierModel(
                id=uuid4(),
                user_id=usuario.id,
                rut=datos["rut"],
                legal_name=datos["legal_name"],
                trade_name=datos["trade_name"],
                description=datos["description"],
                regions=datos["regions"],
                sectors=datos["sectors"],
                keywords=datos["keywords"],
                certifications=None,
                created_at=ahora,
                updated_at=ahora,
            )
            sesion.add(proveedor)

            # El vector del proveedor es lo que busca contra las licitaciones.
            # Sin él, el dashboard responde SupplierVectorNotFound.
            texto = constructor.build_from_supplier(
                Supplier(
                    id=proveedor.id,
                    rut=proveedor.rut,
                    legal_name=proveedor.legal_name,
                    trade_name=proveedor.trade_name,
                    description=proveedor.description,
                    regions=datos["regions"],
                    sectors=datos["sectors"],
                    keywords=datos["keywords"],
                )
            )
            vector = (await embeddings.embed([texto]))[0]
            vectores.upsert(supplier_id=proveedor.id, embedding=vector)

            creados.append((datos["email"], datos["legal_name"], datos["sectors"][0]))
            print(f"[OK] {datos['legal_name']}", flush=True)

        await sesion.commit()

    await engine.dispose()

    if creados:
        print("\n" + "=" * 62)
        print("CREDENCIALES DE PRUEBA  (contraseña común: " + CONTRASENA + ")")
        print("=" * 62)
        for correo, nombre, rubro in creados:
            print(f"  {correo:<32} {nombre}  [{rubro}]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crea tres proveedores de prueba.")
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Omite las guardas de entorno. Solo para bases desechables.",
    )
    asyncio.run(main(parser.parse_args().forzar))
