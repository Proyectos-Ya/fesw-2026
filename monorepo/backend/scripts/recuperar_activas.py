"""Pone al día, una sola vez, las licitaciones activas con cambios sin ver.

Qué resuelve
------------
Del 2026-10-06 al 10-09 el cron de estados no vio los cambios de 30,6 h hábiles:
en hora punta la API daba 504 y las corridas perdían lo listado (plan 305).
`ttl_cambio_ms` se cuenta desde ahora y no admite cursor, así que esos cambios
ya no salen en el listado de cambios. Las licitaciones afectadas pueden seguir
figurando publicadas cuando ya se cancelaron, o cerrarse con un plazo viejo.

Qué hace
--------
1. **Busca las candidatas**: activas con el cierre a más de 1 h y sin escribirse
   desde `--antes-de`.
2. **Lista por publicación** su rango de fechas (`estado=publicada`), en tramos
   de 6 h, y aplica cada página como el cron de estados: estado, cierre,
   llamado y el puntero de la cola para las que cambiaron después de la última
   bajada. Cuesta una petición cada 10 licitaciones, no una por licitación.
3. **Encola las que no aparecen como publicadas**: ya no lo están, y su
   detalle (que baja la ingesta) confirma en qué estado quedaron. Si algún tramo
   del listado vino incompleto no encola nada, porque "no aparece" ya no
   significa "dejó de estar publicada".

No baja detalles: deja la cola lista y la ingesta los baja en su próxima
corrida. Conviene correrlo de noche y no la misma noche que la primera nocturna
después del despliegue, que trae días de atraso.

Uso
---
    python -m scripts.recuperar_activas --dry-run                    # cuenta
    python -m scripts.recuperar_activas --confirmar-produccion       # corre
    python -m scripts.recuperar_activas --confirmar-produccion --limite 500
"""

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.domain.models.cambio_estado import (
    CambioDeEstado,
    Intencion,
    PunteroDeCambio,
    ResultadoPunteros,
    ResultadoSyncEstados,
)
from app.infrastructure.repositories.tender_model import (
    TenderModel,
    TenderStatusModel,
)
from app.infrastructure.services.tenders.listado_cambios import cambio_desde_item
from app.shared.constants import ACTIVE_TENDER_STATUSES
from app.shared.datetime_utils import utc_now_naive
from scripts.ingesta_compartida import construir_servicio, preparar_destino
from scripts.sync_diaria import partir_en_tramos, verificar_destino
from scripts.sync_estados import _aplicar

# Fin del último tramo sin cobertura del cron de estados (plan 305, medido sobre
# `sync_estados_run`). Lo escrito después ya pasó por un listado completo.
ANTES_DE_POR_DEFECTO = datetime(2026, 10, 9, 20, 0)
TRAMO = timedelta(hours=6)

AlRecibir = Callable[[list[CambioDeEstado]], Awaitable[None]]


@dataclass(frozen=True)
class Candidata:
    code: str
    published_at: datetime


async def recuperar(
    args: argparse.Namespace,
    *,
    buscar: Callable[[int | None], Awaitable[list[Candidata]]],
    listar: Callable[[datetime, datetime, AlRecibir], Awaitable[bool]],
    aplicar: Callable[[list[CambioDeEstado]], Awaitable[ResultadoSyncEstados]],
    encolar: Callable[[list[PunteroDeCambio]], Awaitable[ResultadoPunteros]],
) -> int:
    """Orquesta la recuperación y devuelve el código de salida.

    `listar(desde, hasta, al_recibir)` entrega cada página y devuelve si el
    tramo vino completo.
    """
    candidatas = await buscar(args.limite)
    print(f"{len(candidatas)} candidatas.")
    if not candidatas:
        return 0

    desde = min(c.published_at for c in candidatas)
    hasta = max(c.published_at for c in candidatas) + timedelta(minutes=1)
    tramos = partir_en_tramos(desde, hasta, TRAMO)
    print(
        f"Rango de publicación: {desde.isoformat()} → {hasta.isoformat()} "
        f"({len(tramos)} tramos)."
    )
    if args.dry_run:
        return 0

    vistas: set[str] = set()
    total = ResultadoSyncEstados()

    async def al_recibir(cambios: list[CambioDeEstado]) -> None:
        if not cambios:
            return
        vistas.update(c.code for c in cambios)
        total.sumar(await aplicar(cambios))

    completo = True
    for t_desde, t_hasta in tramos:
        completo = await listar(t_desde, t_hasta, al_recibir) and completo

    print(
        f"{len(vistas)} publicadas listadas: {total.actualizadas} actualizadas, "
        f"{total.reencoladas} encoladas para actualizar, {total.nuevas} nuevas."
    )
    if not completo:
        print(
            "\nAVISO: algún tramo del listado vino incompleto. No se encolan las\n"
            "candidatas que no aparecieron: puede que sigan publicadas. Vuelve a\n"
            "correr el script más tarde."
        )
        return 1

    faltan = [c for c in candidatas if c.code not in vistas]
    if faltan:
        # Sin condición, como una reapertura: el listado dice que ya no están
        # publicadas y solo el detalle dice en qué estado quedaron.
        resultado = await encolar(
            [
                PunteroDeCambio(
                    code=c.code,
                    status_code="publicada",
                    changed_at=None,
                    intencion=Intencion.REABIERTA,
                )
                for c in faltan
            ]
        )
        print(
            f"{len(faltan)} candidatas ya no aparecen publicadas: "
            f"{resultado.actualizar} encoladas para que la ingesta baje su detalle."
        )
    return 0


async def _buscar(
    engine: Any, antes_de: datetime, limite: int | None
) -> list[Candidata]:
    async with AsyncSession(engine) as session:
        stmt = (
            select(TenderModel.code, TenderModel.published_at)
            .join(TenderStatusModel, TenderStatusModel.id == TenderModel.status_id)
            .where(
                col(TenderStatusModel.code).in_(ACTIVE_TENDER_STATUSES),
                col(TenderModel.closing_at) > utc_now_naive() + timedelta(hours=1),
                col(TenderModel.updated_at) < antes_de,
            )
            .order_by(col(TenderModel.published_at))
            .limit(limite)
        )
        filas = (await session.exec(stmt)).all()
        return [Candidata(code=code, published_at=pub) for code, pub in filas]


async def _correr(args: argparse.Namespace) -> int:
    servicio, engine, qdrant = construir_servicio(con_embeddings=False)
    cliente = servicio.client

    async def listar(desde: datetime, hasta: datetime, al_recibir: AlRecibir) -> bool:
        async def traducir(items: list[dict]) -> None:
            await al_recibir(
                [c for c in (cambio_desde_item(i) for i in items) if c is not None]
            )

        listado = await cliente.get_tenders(
            desde,
            hasta,
            settings.sync_estados_limite,
            por_publicacion=True,
            estado="publicada",
            al_recibir_pagina=traducir,
        )
        return listado.completo

    try:
        if not args.dry_run:
            await preparar_destino(engine, qdrant)
        codigo = await recuperar(
            args,
            buscar=lambda limite: _buscar(engine, args.antes_de, limite),
            listar=listar,
            aplicar=lambda cambios: _aplicar(engine, qdrant, servicio, cambios),
            encolar=servicio.registrar_punteros,
        )
        print(f"Peticiones a Mercado Público: {cliente.peticiones}.")
        return codigo
    finally:
        await engine.dispose()
        await qdrant.close()


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    p.add_argument(
        "--antes-de",
        type=datetime.fromisoformat,
        default=ANTES_DE_POR_DEFECTO,
        help=(
            "candidatas sin escribirse desde este momento, UTC "
            f"({ANTES_DE_POR_DEFECTO.isoformat()})"
        ),
    )
    p.add_argument("--limite", type=int, default=None, help="tope de candidatas")
    p.add_argument(
        "--dry-run", action="store_true", help="solo cuenta, no pide nada a la API"
    )
    p.add_argument(
        "--confirmar-produccion",
        action="store_true",
        help="requerido si la base no es local",
    )
    return p


def main() -> None:
    args = construir_parser().parse_args()
    print(f"Base de datos : {settings.database_url.split('@')[-1]}\n")
    mensaje = verificar_destino(
        settings.database_url, confirmar_produccion=args.confirmar_produccion
    )
    if mensaje:
        print(mensaje, file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(_correr(args)))


if __name__ == "__main__":
    main()
