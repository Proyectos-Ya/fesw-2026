"""`reset_cuentas --solo-empresas` borra las empresas y conserva lo compartido.

El modo de siempre hace `TRUNCATE ... CASCADE`, que vacía tablas enteras: se
llevaría las filas compartidas (`workspace_id` nulo) de `tender_digest` y
`attachment_processing_job`, y todas las cuentas de `users`. Este modo borra con
`DELETE` solo lo que es de las empresas (HdU 311, tarea A4).

Es seguro: usa `db_session`, que apunta a `<db>_test`, y **nunca** llama a
`_ejecutar`, que abre la base de `settings` (en desarrollo, la compartida).
"""

import hashlib
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

import app.infrastructure.repositories.models  # noqa: F401
from app.infrastructure.repositories.attachment_processing_model import (
    AttachmentProcessingJobModel,
    TenderDigestModel,
)
from app.infrastructure.repositories.matching_result_model import MatchingResultModel
from app.infrastructure.repositories.sql_attachment_file_repository import (
    SqlAttachmentFileRepository,
)
from scripts.reset_cuentas import _borrar_empresas, _contar_empresas
from tests.integration.attachment_seed import (
    AHORA,
    MundoAnexo,
    aporte,
    canonica,
    sembrar_anexo,
    sembrar_empresa,
)

pytestmark = pytest.mark.asyncio

SHA = hashlib.sha256(b"hola").hexdigest()


async def _contar(session: AsyncSession, tabla: str, donde: str = "true") -> int:
    resultado = await session.execute(
        text(f'SELECT count(*) FROM "{tabla}" WHERE {donde}')  # noqa: S608
    )
    return resultado.scalar_one()


def _digest(m: MundoAnexo, empresa: UUID | None) -> TenderDigestModel:
    return TenderDigestModel(
        id=uuid4(),
        tender_id=m.tender_id,
        workspace_id=empresa,
        version=1,
        extraction_set_hash="h" * 64,
        is_current=True,
        source_count=0,
        data={},
        api_snapshot={},
        created_at=AHORA,
    )


def _trabajo(m: MundoAnexo, empresa: UUID | None) -> AttachmentProcessingJobModel:
    return AttachmentProcessingJobModel(
        id=uuid4(),
        kind="digest",
        status="done",
        not_before=AHORA,
        tender_id=m.tender_id,
        workspace_id=empresa,
        created_at=AHORA,
        updated_at=AHORA,
    )


def _match(m: MundoAnexo, empresa: UUID) -> MatchingResultModel:
    # `matching_result` apunta a `supplier` sin CASCADE: el script tiene que
    # borrarlo antes que la empresa o el DELETE falla por clave foránea.
    return MatchingResultModel(
        id=uuid4(),
        supplier_id=empresa,
        tender_id=m.tender_id,
        final_score=0.5,
        model_version="test",
        calculated_at=AHORA,
    )


async def _sembrar_mundo(session: AsyncSession) -> MundoAnexo:
    """Dos empresas con una fila propia en cada tabla y una fila compartida."""
    m = await sembrar_anexo(session)
    repo = SqlAttachmentFileRepository(session)
    for rut in ("76.000.001-1", "76.000.002-2"):
        empresa, dueno = await sembrar_empresa(session, rut)
        session.add(_digest(m, empresa))
        session.add(_trabajo(m, empresa))
        session.add(_match(m, empresa))
        await session.commit()
        await repo.create(aporte(m, empresa, dueno, sha=SHA))
    session.add(_digest(m, None))
    session.add(_trabajo(m, None))
    await session.commit()
    await repo.create(canonica(m, sha=SHA))
    return m


async def test_borra_las_empresas_y_conserva_lo_compartido_y_las_cuentas(
    db_session: AsyncSession,
):
    await _sembrar_mundo(db_session)
    cuentas_antes = await _contar(db_session, "users")

    await _borrar_empresas(db_session)
    await db_session.commit()

    assert await _contar(db_session, "supplier") == 0
    assert await _contar(db_session, "matching_result") == 0
    # Lo compartido sigue, y es lo único que queda.
    for tabla in ("tender_digest", "attachment_processing_job", "attachment_file"):
        assert await _contar(db_session, tabla) == 1, tabla
        assert await _contar(db_session, tabla, "workspace_id IS NULL") == 1, tabla
    # Las cuentas no se tocan: vuelven a pasar por el wizard.
    assert cuentas_antes == 2
    assert await _contar(db_session, "users") == 2
    # Lo que no depende de una empresa tampoco.
    assert await _contar(db_session, "tender") == 1
    assert await _contar(db_session, "tender_attachment") == 1


async def test_el_ensayo_no_cambia_nada_e_informa_el_conteo_por_tabla(
    db_session: AsyncSession,
):
    await _sembrar_mundo(db_session)
    tablas = (
        "supplier",
        "users",
        "matching_result",
        "tender_digest",
        "attachment_processing_job",
        "attachment_file",
    )
    antes = {t: await _contar(db_session, t) for t in tablas}

    conteos = await _contar_empresas(db_session)
    await db_session.commit()

    assert {t: await _contar(db_session, t) for t in tablas} == antes
    assert conteos["supplier"] == 2
    assert conteos["matching_result"] == 2
    assert conteos["tender_digest"] == 2
    assert conteos["attachment_processing_job"] == 2
    assert conteos["attachment_file"] == 2
    assert "users" not in conteos


async def test_sin_empresas_no_borra_nada(db_session: AsyncSession):
    m = await sembrar_anexo(db_session)
    db_session.add(_digest(m, None))
    await db_session.commit()

    conteos = await _contar_empresas(db_session)
    await _borrar_empresas(db_session)
    await db_session.commit()

    assert conteos["supplier"] == 0
    assert await _contar(db_session, "tender_digest") == 1
