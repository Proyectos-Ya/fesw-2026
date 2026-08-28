"""Diagnóstico: licitaciones en Postgres sin su vector en Qdrant (y viceversa).

Contexto
--------
La ingesta escribe en dos almacenes sin una frontera transaccional común:
`save_complex_tender` hace commit en Postgres y recién después se calcula el
embedding y se hace el `upsert` en Qdrant. Si ese segundo tramo falla, el
`except Exception` del caso de uso absorbe el error con un print y la fila queda
persistida sin vector.

El costo es total, no parcial: Qdrant es el único punto de entrada del pipeline
de recomendación (`RankTendersUseCase` parte de `search_by_supplier_vector`), y
no existe ningún listado de licitaciones respaldado por SQL. Una licitación sin
vector es invisible para el producto, nunca genera un `MatchingResult` y por lo
tanto su análisis de compatibilidad responde `ScoreMatchingNoEncontrado`.

Además el daño es permanente sin intervención: `get_by_code` da por procesada
la licitación y jamás la reintenta, y la única reconciliación que existe
(`rank_tenders.py`, paso 3.3.1) corre en la dirección contraria — borra puntos
de Qdrant sin fila en SQL, no repara filas en SQL sin punto en Qdrant.

Este script solo mide. No escribe en ninguno de los dos almacenes.

Uso
---
    python -m scripts.check_tender_vector_orphans              # reporte legible
    python -m scripts.check_tender_vector_orphans --json       # salida para máquinas
    python -m scripts.check_tender_vector_orphans --sample 50  # más ejemplos

Código de salida: 0 si no hay huérfanos, 1 si los hay (sirve como check en CI).
"""

import argparse
import asyncio
import json
from collections import Counter
from dataclasses import dataclass, field
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.config import settings
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.shared.constants import ACTIVE_TENDER_STATUSES, TENDER_STATUS_CODE_BY_ID
from app.shared.datetime_utils import utc_now_naive

# Qdrant limita el tamaño de cada retrieve; 500 mantiene el número de viajes bajo
# sin construir payloads enormes.
_BATCH_SIZE = 500

_SELECT_TENDERS = text("SELECT id, code, status_id, closing_at FROM tender")


@dataclass
class TenderRow:
    id: UUID
    code: str
    status_code: str
    is_active: bool


@dataclass
class Report:
    total_tenders: int = 0
    collection_exists: bool = True
    with_vector: int = 0
    missing_vector: list[TenderRow] = field(default_factory=list)
    # Punto presente pero sin el vector nombrado 'tender': igual de invisible
    # para la búsqueda, y no lo detectaría una comprobación de sola existencia.
    point_without_named_vector: list[TenderRow] = field(default_factory=list)
    qdrant_points_without_row: list[str] = field(default_factory=list)

    @property
    def orphans(self) -> list[TenderRow]:
        return self.missing_vector + self.point_without_named_vector

    @property
    def active_orphans(self) -> list[TenderRow]:
        return [t for t in self.orphans if t.is_active]


async def _load_tenders(conn: AsyncConnection) -> list[TenderRow]:
    now = utc_now_naive()
    rows = (await conn.execute(_SELECT_TENDERS)).all()

    tenders: list[TenderRow] = []
    for row in rows:
        status_code = TENDER_STATUS_CODE_BY_ID.get(row.status_id, "desconocido")
        tenders.append(
            TenderRow(
                id=row.id,
                code=row.code,
                status_code=status_code,
                # Mismo criterio que usa el pipeline para considerar una
                # licitación recomendable (rank_tenders, pasos 3.4 y 2).
                is_active=(
                    status_code in ACTIVE_TENDER_STATUSES and row.closing_at > now
                ),
            )
        )
    return tenders


async def _check_vectors(
    client: AsyncQdrantClient, tenders: list[TenderRow], report: Report
) -> None:
    by_id = {str(t.id): t for t in tenders}
    ids = list(by_id)

    for start in range(0, len(ids), _BATCH_SIZE):
        batch = ids[start : start + _BATCH_SIZE]
        records = await client.retrieve(
            collection_name=QdrantTenderRepository._COLLECTION_NAME,
            ids=list(batch),
            with_vectors=True,
            with_payload=False,
        )
        found = {str(record.id): record for record in records}

        for point_id in batch:
            tender = by_id[point_id]
            record = found.get(point_id)
            if record is None:
                report.missing_vector.append(tender)
                continue

            vectors = record.vector
            named = QdrantTenderRepository._VECTOR_NAME
            if not isinstance(vectors, dict) or not vectors.get(named):
                report.point_without_named_vector.append(tender)
                continue

            report.with_vector += 1


async def _find_points_without_row(
    client: AsyncQdrantClient, tenders: list[TenderRow], report: Report
) -> None:
    """Dirección inversa: puntos en Qdrant que ya no tienen fila en Postgres."""
    known = {str(t.id) for t in tenders}
    offset = None

    while True:
        points, offset = await client.scroll(
            collection_name=QdrantTenderRepository._COLLECTION_NAME,
            limit=_BATCH_SIZE,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        for point in points:
            if str(point.id) not in known:
                report.qdrant_points_without_row.append(str(point.id))
        if offset is None:
            break


class DiagnosticError(RuntimeError):
    """Fallo de conectividad, reportado sin traceback."""


async def diagnose() -> Report:
    report = Report()
    client = AsyncQdrantClient(url=settings.qdrant_url)
    # Engine propio en vez del compartido: `app.infrastructure.db` fija
    # echo=True, y ese log de SQL en stdout rompe la salida --json.
    engine = create_async_engine(settings.database_url, echo=False)

    try:
        try:
            # Conexión directa en vez de AsyncSession: es SQL crudo de solo
            # lectura y no necesita las semánticas de sesión de SQLModel.
            async with engine.connect() as conn:
                tenders = await _load_tenders(conn)
        except OSError as e:
            raise DiagnosticError(
                f"No se pudo conectar a Postgres ({settings.database_url}): {e}\n"
                "  ¿Está levantado el contenedor de la base de datos?"
            ) from e

        report.total_tenders = len(tenders)

        try:
            collections = await client.get_collections()
        except Exception as e:
            raise DiagnosticError(
                f"No se pudo conectar a Qdrant ({settings.qdrant_url}): {e}\n"
                "  ¿Está levantado el contenedor de Qdrant?"
            ) from e

        existing = {c.name for c in collections.collections}
        if QdrantTenderRepository._COLLECTION_NAME not in existing:
            # Sin colección, absolutamente ninguna licitación es recomendable.
            report.collection_exists = False
            report.missing_vector = tenders
            return report

        if tenders:
            await _check_vectors(client, tenders, report)
        await _find_points_without_row(client, tenders, report)

        return report
    finally:
        await client.close()
        await engine.dispose()


def _print_report(report: Report, sample: int) -> None:
    print("\n" + "=" * 60)
    print("DIAGNÓSTICO: licitaciones sin vector en Qdrant")
    print("=" * 60)

    if not report.collection_exists:
        print(
            f"\n  La colección '{QdrantTenderRepository._COLLECTION_NAME}' NO EXISTE "
            "en Qdrant.\n"
            "  Ninguna licitación es recomendable. El pipeline de matching está\n"
            "  completamente caído para todos los proveedores."
        )

    total = report.total_tenders
    orphans = report.orphans
    active_orphans = report.active_orphans
    pct = (len(orphans) / total * 100) if total else 0.0

    print(f"\n  Licitaciones en Postgres : {total}")
    print(f"  Con vector en Qdrant     : {report.with_vector}")
    print(f"  Sin vector (huérfanas)   : {len(orphans)}  ({pct:.1f}%)")

    if report.point_without_named_vector:
        print(
            f"    · sin punto en Qdrant        : {len(report.missing_vector)}\n"
            f"    · con punto pero sin vector  : "
            f"{len(report.point_without_named_vector)}"
        )

    print(f"\n  De esas, activas y vigentes: {len(active_orphans)}")
    print("  (son las que un proveedor debería estar viendo hoy y no ve)")

    if orphans:
        by_status = Counter(t.status_code for t in orphans)
        print("\n  Huérfanas por estado:")
        for status, count in by_status.most_common():
            print(f"    {status:<24} {count}")

        shown = active_orphans or orphans
        print(f"\n  Ejemplos ({min(sample, len(shown))} de {len(shown)}):")
        for tender in shown[:sample]:
            marca = "activa" if tender.is_active else tender.status_code
            print(f"    {tender.code:<24} [{marca}]")

    if report.qdrant_points_without_row:
        print(
            f"\n  Dirección inversa: {len(report.qdrant_points_without_row)} puntos en "
            "Qdrant\n  sin fila en Postgres. El paso 3.3.1 de rank_tenders los va "
            "limpiando\n  solo, a medida que aparecen en alguna búsqueda."
        )

    print("\n" + "-" * 60)
    if not orphans:
        print("  Sin huérfanas. Los dos almacenes están sincronizados.")
    elif active_orphans:
        print(
            f"  {len(active_orphans)} licitaciones activas están invisibles para el\n"
            "  matching. Requieren backfill: recalcular su embedding e insertarlas\n"
            "  en Qdrant. El fix de la ingesta no las recupera de forma retroactiva."
        )
    else:
        print(
            "  Hay huérfanas, pero ninguna activa: no afectan las recomendaciones\n"
            "  de hoy. Conviene arreglar la causa antes de que caiga una vigente."
        )
    print("-" * 60 + "\n")


def _json_report(report: Report) -> str:
    return json.dumps(
        {
            "collection_exists": report.collection_exists,
            "total_tenders": report.total_tenders,
            "with_vector": report.with_vector,
            "orphans": len(report.orphans),
            "orphans_missing_point": len(report.missing_vector),
            "orphans_without_named_vector": len(report.point_without_named_vector),
            "active_orphans": len(report.active_orphans),
            "active_orphan_codes": [t.code for t in report.active_orphans],
            "qdrant_points_without_row": len(report.qdrant_points_without_row),
        },
        indent=2,
        ensure_ascii=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emite el reporte como JSON en vez del formato legible.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=15,
        help="Cantidad de códigos de ejemplo a mostrar (por defecto 15).",
    )
    args = parser.parse_args()

    try:
        report = asyncio.run(diagnose())
    except DiagnosticError as e:
        # El diagnóstico no pudo ejecutarse; distinto de "ejecutó y halló huérfanas".
        print(f"\n[Diagnóstico] {e}\n")
        raise SystemExit(2) from None

    if args.json:
        print(_json_report(report))
    else:
        _print_report(report, sample=args.sample)

    raise SystemExit(1 if report.orphans else 0)


if __name__ == "__main__":
    main()
