"""`reset_cuentas` conserva los anexos compartidos (plan 233, decisión 6).

`TRUNCATE ... CASCADE` vacía tablas enteras, sin importar el `ON DELETE`: como los
aportes de cada empresa apuntan a `supplier`, vaciaría también `attachment_file`
entera, con las versiones canónicas (que no son de ninguna cuenta). El script las
aparta en una tabla temporal y las repone en la misma transacción.

Es seguro: usa `db_session`, que apunta a `<db>_test`, y **nunca** llama a
`_ejecutar`, que abre la base de `settings` (en desarrollo, la compartida).
"""

import hashlib

import pytest
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.infrastructure.repositories.models  # noqa: F401
from app.domain.entities.attachment_file import AttachmentTrust, AttachmentVisibility
from app.infrastructure.repositories.attachment_file_model import AttachmentFileModel
from app.infrastructure.repositories.sql_attachment_file_repository import (
    SqlAttachmentFileRepository,
)
from scripts.reset_cuentas import _truncar_conservando_compartidos
from tests.integration.attachment_seed import (
    aporte,
    canonica,
    sembrar_anexo,
    sembrar_empresa,
)

pytestmark = pytest.mark.asyncio

SHA = hashlib.sha256(b"hola").hexdigest()


async def _contar(session: AsyncSession, tabla: str) -> int:
    resultado = await session.execute(text(f'SELECT count(*) FROM "{tabla}"'))  # noqa: S608
    return resultado.scalar_one()


async def test_el_reset_borra_las_cuentas_y_conserva_la_version_compartida(
    db_session: AsyncSession,
):
    m = await sembrar_anexo(db_session)
    empresa, dueno = await sembrar_empresa(db_session, "76.000.001-1")
    repo = SqlAttachmentFileRepository(db_session)
    await repo.create(aporte(m, empresa, dueno, sha=SHA))
    compartida = await repo.create(canonica(m, sha=SHA))

    conservadas = await _truncar_conservando_compartidos(db_session)
    await db_session.commit()

    assert conservadas == 1
    ids = [f.id for f in (await db_session.exec(select(AttachmentFileModel))).all()]
    assert ids == [compartida.id]
    assert await _contar(db_session, "supplier") == 0
    assert await _contar(db_session, "users") == 0
    # Lo que no depende de una cuenta no se toca.
    assert await _contar(db_session, "tender_attachment") == 1
    assert await _contar(db_session, "tender") == 1
    # La versión conservada sigue entera.
    [fila] = (await db_session.exec(select(AttachmentFileModel))).all()
    assert (fila.workspace_id, fila.uploader_user_id) == (None, None)
    assert (fila.visibility, fila.trust, fila.storage_key) == (
        "shared",
        "corroborated",
        compartida.storage_key,
    )


async def test_sin_versiones_compartidas_el_reset_vacia_todo_y_cuenta_cero(
    db_session: AsyncSession,
):
    m = await sembrar_anexo(db_session)
    empresa, dueno = await sembrar_empresa(db_session, "76.000.001-1")
    await SqlAttachmentFileRepository(db_session).create(aporte(m, empresa, dueno, sha=SHA))

    conservadas = await _truncar_conservando_compartidos(db_session)
    await db_session.commit()

    assert conservadas == 0
    assert await _contar(db_session, "attachment_file") == 0


async def test_una_version_oculta_tambien_se_conserva(db_session: AsyncSession):
    # Suspendida por un conflicto: tampoco es de una cuenta, y la promoción la
    # puede volver a mostrar.
    m = await sembrar_anexo(db_session)
    await sembrar_empresa(db_session, "76.000.001-1")
    await SqlAttachmentFileRepository(db_session).create(
        canonica(
            m, sha=SHA, visibilidad=AttachmentVisibility.PRIVATE, trust=AttachmentTrust.CONFLICT
        )
    )

    conservadas = await _truncar_conservando_compartidos(db_session)
    await db_session.commit()

    assert conservadas == 1
    [fila] = (await db_session.exec(select(AttachmentFileModel))).all()
    assert (fila.visibility, fila.trust) == ("private", "conflict")
