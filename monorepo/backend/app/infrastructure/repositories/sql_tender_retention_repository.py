"""Retención de licitaciones cerradas que nadie usó, en Postgres (plan 306).

Medido el 2026-10-13: 30 tablas apuntan a `tender`. Cada una cae en una de las
tres listas de abajo, y `test_retencion_licitaciones.py` falla si aparece una
tabla nueva sin clasificar.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.repositories.tender_retention_repository import (
    ITenderRetentionRepository,
)
from app.shared.constants import ACTIVE_TENDER_STATUSES

# Lo que hace una persona o una empresa. Una fila en cualquiera conserva la
# licitación. Varias tienen CASCADE (borradores, links, archivos subidos): si no
# se revisaran, borrar la licitación se llevaría ese trabajo en silencio.
TABLAS_DE_USO: tuple[str, ...] = (
    "saved_tender",
    "kanban_card",
    "tender_milestone",
    "quotation",
    "deep_analysis",
    "tender_chat_sessions",
    "tender_chat_messages",
    "tender_chat_documents",
    "proposal_drafts",
    "tender_share_link",
    "tender_milestone_document",
    "tender_milestone_attachment",
    "attachment_file",
    # Retroalimentación del usuario (HU-24).
    "match_report",
    "assistant_message_feedback",
    # Hoy ningún código crea estas tareas. Cuenta como uso por precaución.
    "extension_fetch_job",
)

# Lo que genera el sistema y tiene la clave foránea en NO ACTION: hay que
# borrarlo a mano antes que la licitación.
TABLAS_DEL_SISTEMA_SIN_CASCADA: tuple[str, ...] = (
    "tender_item",
    "matching_result",
    "notification",
    "tender_ai_analysis",
    "calendar_oauth_state",
)

# Lo que genera el sistema y se resuelve solo al borrar la licitación: CASCADE,
# salvo `capability_answer`, que es SET NULL y conserva la respuesta.
# `tender_interaction` es telemetría del ranking y no cuenta como uso
# (decidido el 2026-10-13).
TABLAS_DEL_SISTEMA_EN_CASCADA: tuple[str, ...] = (
    "tender_attachment",
    "tender_attachment_item",
    "attachment_extraction",
    "attachment_processing_job",
    "tender_digest",
    "export_job",
    "ranking_impression",
    "tender_interaction",
    "matching_shadow_score",
    "attachment_priority_shadow",
    "capability_answer",
)

# Los nombres de tabla son constantes de este módulo, no entrada de usuario.
_SIN_USO = "\n".join(
    f"AND NOT EXISTS (SELECT 1 FROM {tabla} u WHERE u.tender_id = t.id)"
    for tabla in TABLAS_DE_USO
)

_BORRABLE = f"""
    t.closing_at < :corte
    AND t.status_id NOT IN (
        SELECT id FROM tender_status WHERE code = ANY(CAST(:activos AS varchar[]))
    )
    {_SIN_USO}
"""


class SqlTenderRetentionRepository(ITenderRetentionRepository):
    """Abre su propia conexión por llamada: cada lote es una transacción."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def ids_borrables(self, corte: datetime, limite: int) -> list[UUID]:
        async with self.engine.connect() as conn:
            filas = await conn.execute(
                text(
                    f"""
                    SELECT t.id FROM tender t
                     WHERE {_BORRABLE}
                     ORDER BY t.closing_at, t.id
                     LIMIT :limite
                    """
                ),
                {"corte": corte, "activos": _activos(), "limite": limite},
            )
            return [fila[0] for fila in filas]

    async def borrar(self, tender_ids: list[UUID], corte: datetime) -> int:
        if not tender_ids:
            return 0
        async with self.engine.begin() as conn:
            # 1. Bloquear las filas del lote. Un INSERT que las referencie toma
            #    FOR KEY SHARE y queda esperando hasta que esta transacción
            #    termine, así que desde acá no aparece uso nuevo. En orden de id
            #    para no cruzarse con otro bloqueo.
            bloqueadas = (
                await conn.execute(
                    text(
                        "SELECT id FROM tender WHERE id = ANY(:ids)"
                        " ORDER BY id FOR UPDATE"
                    ),
                    {"ids": tender_ids},
                )
            ).all()
            if not bloqueadas:
                return 0
            # 2. Revisar de nuevo, en otra sentencia: en READ COMMITTED cada una
            #    toma su propio snapshot y ve el uso que alguien confirmó entre
            #    `ids_borrables` y el bloqueo. Dentro de la sentencia del
            #    bloqueo, la subconsulta seguiría viendo el snapshot viejo.
            confirmadas = [
                fila[0]
                for fila in await conn.execute(
                    text(
                        f"SELECT t.id FROM tender t WHERE t.id = ANY(:ids) AND {_BORRABLE}"
                    ),
                    {
                        "ids": [fila[0] for fila in bloqueadas],
                        "corte": corte,
                        "activos": _activos(),
                    },
                )
            ]
            if not confirmadas:
                return 0
            # 3. Las hijas sin cascada primero; el resto cae con la licitación.
            for tabla in TABLAS_DEL_SISTEMA_SIN_CASCADA:
                await conn.execute(
                    text(f"DELETE FROM {tabla} WHERE tender_id = ANY(:ids)"),
                    {"ids": confirmadas},
                )
            resultado = await conn.execute(
                text("DELETE FROM tender WHERE id = ANY(:ids)"), {"ids": confirmadas}
            )
            return resultado.rowcount or 0


def _activos() -> list[str]:
    return sorted(ACTIVE_TENDER_STATUSES)
