"""Script manual para procesar trabajos de la cola de anexos (plan 233, decisión 4)."""

import argparse
import asyncio
import sys

from sqlalchemy import update

from app.bootstrap import (
    build_attachment_processing_runner,
    build_attachment_storage,
)
from app.config import settings
from app.domain.entities.attachment_processing import (
    ProcessingJobKind,
    ProcessingJobStatus,
)
from app.domain.services.gemini_budget import dia_del_tope
from app.infrastructure.db import async_session_maker
from app.infrastructure.repositories.attachment_processing_model import (
    AttachmentProcessingJobModel,
)
from app.infrastructure.repositories.sql_gemini_usage_repository import (
    SqlGeminiUsageRepository,
)
from app.infrastructure.services.attachment_processing_scheduler import (
    AsyncioProcessingSignal,
)
from app.infrastructure.services.attachments.content_reader import (
    StdlibAttachmentContentReader,
)
from app.infrastructure.services.attachments.gemini_attachment_extraction_service import (
    GeminiAttachmentExtractionService,
)
from app.shared.datetime_utils import utc_now_naive
from scripts.sync_diaria import verificar_destino


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Procesa trabajos de la cola de anexos (extracción y resumen)."
    )
    parser.add_argument(
        "--max-trabajos",
        type=int,
        default=1,
        help="Cantidad máxima de trabajos a procesar (por defecto 1).",
    )
    parser.add_argument(
        "--solo-barrido",
        action="store_true",
        help="Solo ejecuta el barrido de archivos huérfanos sin procesar cola.",
    )
    parser.add_argument(
        "--reintentar-fallidos",
        action="store_true",
        help="Pasa los trabajos extract en failed a pending con attempts=0.",
    )
    parser.add_argument(
        "--confirmar-produccion",
        action="store_true",
        help="Permite correr contra bases no locales.",
    )
    return parser.parse_args(argv)


class MockApp:
    def __init__(self) -> None:
        self.state = type("State", (), {})()


async def reintentar_fallidos_en_db() -> int:
    async with async_session_maker() as session:
        stmt = (
            update(AttachmentProcessingJobModel)
            .where(
                AttachmentProcessingJobModel.kind == ProcessingJobKind.EXTRACT,
                AttachmentProcessingJobModel.status.in_([
                    ProcessingJobStatus.FAILED,
                    ProcessingJobStatus.PENDING,
                ]),
            )
            .values(
                status=ProcessingJobStatus.PENDING,
                attempts=0,
                last_error=None,
                not_before=utc_now_naive(),
                updated_at=utc_now_naive(),
            )
        )
        res = await session.exec(stmt)  # type: ignore[call-overload]
        await session.commit()
        return res.rowcount or 0


async def main_async(args: argparse.Namespace) -> int:
    motivo = verificar_destino(
        settings.database_url, confirmar_produccion=args.confirmar_produccion
    )
    if motivo:
        print(f"ERROR: {motivo}", file=sys.stderr)
        return 2

    # Aviso del presupuesto diario
    async with async_session_maker() as session:
        usage_repo = SqlGeminiUsageRepository(session)
        hoy = dia_del_tope(utc_now_naive())
        gastadas = await usage_repo.calls_on(hoy)
        tope = settings.attachment_gemini_daily_budget
        print(
            f"Cada trabajo 'extract' es una llamada pagada a Gemini; tope de hoy: {gastadas} de {tope}"
        )

    if args.reintentar_fallidos:
        cant = await reintentar_fallidos_en_db()
        print(f"Reactivados {cant} trabajos fallidos a pending.")

    # Simular app.state para build_attachment_processing_runner
    app = MockApp()
    app.state.attachment_storage = build_attachment_storage()
    app.state.attachment_content_reader = StdlibAttachmentContentReader()
    app.state.attachment_extraction_ai_service = (
        GeminiAttachmentExtractionService(
            api_key=settings.gemini_api_key,
            model_name=settings.attachment_extraction_model,
        )
    )
    app.state.attachment_processing_signal = AsyncioProcessingSignal()

    process_next, sweep = build_attachment_processing_runner(app)  # type: ignore[arg-type]

    # Barrido
    res_sweep = await sweep()
    print(
        f"Barrido: encolados {res_sweep.enqueued} trabajos, recuperados {res_sweep.recovered}, purgados {res_sweep.purged}."
    )

    if args.solo_barrido:
        return 0

    # Procesar trabajos
    procesados = 0
    while procesados < args.max_trabajos:
        hubo_trabajo = await process_next()
        if not hubo_trabajo:
            print("No hay más trabajos pendientes en la cola.")
            break
        procesados += 1
        print(f"Trabajo procesado ({procesados}/{args.max_trabajos}).")

    return 0


def main() -> None:
    args = parse_args()
    code = asyncio.run(main_async(args))
    sys.exit(code)


if __name__ == "__main__":
    main()
