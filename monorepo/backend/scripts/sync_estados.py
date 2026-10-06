"""Sincronización de estados de licitaciones ya guardadas, para correr como cron.

Qué resuelve
------------
`sync_diaria.py` solo **descubre** licitaciones nuevas: una ya procesada no se
vuelve a mirar. Sin este cron, una desierta o cancelada seguía figurando
publicada (y generando alertas) hasta su cierre original, y una con el plazo
ampliado se cerraba con la fecha vieja mientras todavía se podía postular.

Qué hace, en orden
------------------
1. **Lista lo que cambió** en las últimas `--ventana-horas` (listado por
   `ttl_cambio_ms`, sin filtro de estado). Cuesta una petición cada 20
   licitaciones; no pide el detalle.
2. **Aplica estado y cierre** a las que ya tenemos (`SyncTenderStatusesUseCase`):
   borra del índice la que dejó de estar activa, actualiza el payload de la que
   sigue activa, y reencola las publicadas que cambiaron después de la última
   bajada de su detalle, para que el nocturno vea si cambió el texto.
3. **Marca vencidas.** Después de aplicar, para que un plazo ampliado no se
   cierre con la fecha vieja. Antes lo hacía `sync_diaria`.

Sobre la ventana
----------------
`ttl_cambio_ms` se cuenta siempre hacia atrás desde ahora: **no admite cursor**.
Por eso la ventana (2 h por defecto) es más ancha que el intervalo del cron
(1 h): una corrida perdida la cubre la siguiente, y reaplicar un cambio es
idempotente.

El volumen manda sobre el tamaño. Medido el 2026-09-29 a mediodía: **1.620
cambios en una hora** (661 publicadas, 535 cerradas, 64 desiertas, 24
canceladas) y 3.090 en dos. A 20 por página y ~12 s por página, una ventana de
2 h en hora punta son ~150 páginas y 15-30 min. El techo es 6 h porque la API
corta el listado en 10.000 resultados y a ese ritmo 6 h ya rondan los 9.000.

No escribe en `ingestion_run` ni toca el cursor: `sync_diaria` se niega a correr
si ve una corrida en `running`, y compartir la tabla la bloquearía cada vez que
coincidan. Los dos crons pueden correr a la vez.

Uso
---
    python -m scripts.sync_estados                              # local
    python -m scripts.sync_estados --confirmar-produccion       # el cron

Códigos de salida
-----------------
Railway manda un correo de "crashed" por cada salida distinta de 0, así que el
1 se reserva para lo que pide que alguien mire:

- **0**: el listado vino completo, o vino incompleto y es pasajero. En hora
  punta la API responde 504 casi cada hora (medido el 2026-10-05: once corridas
  seguidas entre 10:00 y 18:00), y la ventana de 2 h hace que la corrida
  siguiente vuelva a pedir lo que faltó. Lo avisa en el log con la cuenta.
- **1**: se juntaron `--incompletas-toleradas` incompletas seguidas (horas sin
  mirar), se tocó el techo de `--limite` (la configuración se queda corta y
  esperar no lo arregla) o venció el tope de tiempo. Lo que sí llegó se aplica
  igual.
- **2**: se negó a correr contra una base no local o la ventana es inválida.

La racha de incompletas se cuenta en la tabla `sync_estados_run`.
"""

import argparse
import asyncio
import sys
import time
from collections.abc import Awaitable, Callable, Coroutine
from datetime import timedelta
from typing import Any

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.use_cases.sync_tender_statuses import SyncTenderStatusesUseCase
from app.config import settings
from app.domain.models.cambio_estado import CambioDeEstado, ResultadoSyncEstados
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.repositories.sync_estados_run_repository import (
    SyncEstadosRunRepository,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.infrastructure.services.tenders.tender_ingestion_service import (
    ListadoCambios,
    TenderIngestionService,
)
from scripts.ingesta_compartida import (
    construir_servicio,
    marcar_vencidas,
    preparar_destino,
)
from scripts.sync_diaria import verificar_destino

# Los valores por defecto de ventana, tope de ítems, tope de tiempo e
# incompletas toleradas vienen de `SYNC_ESTADOS_VENTANA_HORAS`,
# `SYNC_ESTADOS_LIMITE`, `SYNC_ESTADOS_TIMEOUT_MINUTOS` y
# `SYNC_ESTADOS_INCOMPLETAS_TOLERADAS` (ver `app/config.py`): 2 h, 9.000 (bajo
# los 10.000 en que corta la API), 50 min (en hora punta una corrida lista ~150
# páginas, 15-30 min, y el tope tiene que quedar bajo el intervalo de 1 h) y 3.
MAX_VENTANA_HORAS = 6.0


def validar_ventana(horas: float) -> str | None:
    """El motivo para rechazar la ventana, o `None` si sirve."""
    if horas <= 0:
        return "La ventana tiene que ser mayor que cero."
    if horas > MAX_VENTANA_HORAS:
        return (
            f"La ventana no puede pasar de {MAX_VENTANA_HORAS:g} h: la API corta "
            "el listado en 10.000 resultados, y en hora punta hay ~1.600 cambios "
            "por hora. El resto se perdería en silencio."
        )
    return None


async def con_tope(corutina: Coroutine[Any, Any, int], segundos: float) -> int:
    """Corre con un tope de tiempo y lo da por fallido al vencer.

    Railway no termina una corrida colgada y omite las siguientes: sin tope, un
    cron que espera una respuesta que no llega deja de correr para siempre.
    """
    try:
        return await asyncio.wait_for(corutina, timeout=segundos)
    except TimeoutError:
        print(
            f"\nERROR: la corrida superó el tope de {segundos / 60:.0f} min y se "
            "canceló. Lo aplicado hasta ahí queda; la corrida siguiente vuelve a "
            "listar la ventana."
        )
        return 1


async def sincronizar_estados(
    args: argparse.Namespace,
    *,
    listar: Callable[[timedelta, int], Awaitable[ListadoCambios]],
    aplicar: Callable[[list[CambioDeEstado]], Awaitable[ResultadoSyncEstados]],
    marcar_vencidas: Callable[[], Awaitable[int]],
    preparar_destino: Callable[[], Awaitable[None]] | None = None,
    registrar_corrida: Callable[[bool, int], Awaitable[int]] | None = None,
) -> int:
    """Orquesta la corrida y devuelve el código de salida.

    Recibe sus colaboradores en vez de construirlos, igual que `sync_diaria`:
    el orden de las etapas y el código de salida se prueban sin Postgres ni
    Qdrant.

    `registrar_corrida(completo, listadas)` guarda la corrida y devuelve cuántas
    incompletas van seguidas contándola. Sin él no hay historial y cualquier
    incompleta sale con 1, como antes.
    """
    inicio = time.perf_counter()
    if preparar_destino is not None:
        await preparar_destino()

    listado = await listar(timedelta(hours=args.ventana_horas), args.limite)
    print(
        f"{listado.listadas} cambios listados ({listado.ilegibles} ilegibles) en "
        f"las últimas {args.ventana_horas:g} h."
    )

    resultado = await aplicar(listado.cambios)
    print(
        f"{resultado.conocidas} conocidas: {resultado.actualizadas} actualizadas, "
        f"{resultado.sacadas_del_indice} sacadas del índice, "
        f"{resultado.reabiertas} reabiertas, {resultado.reencoladas} reencoladas."
    )

    if not args.sin_marcar:
        print(f"Vencidas marcadas como cerradas: {await marcar_vencidas()}")

    techo = listado.listadas >= args.limite
    seguidas = (
        await registrar_corrida(listado.completo, listado.listadas)
        if registrar_corrida is not None
        else 0
    )
    if techo:
        print(
            f"\nAVISO: se listaron {listado.listadas}, que es el techo de la corrida.\n"
            "Quedaron cambios sin mirar. Achica --ventana-horas o sube --limite\n"
            "(sin pasar de 10.000, donde corta la API)."
        )
        codigo = 1
    elif listado.completo:
        codigo = 0
    elif registrar_corrida is not None and seguidas < args.incompletas_toleradas:
        print(
            "\nAVISO: el listado quedó incompleto (la API cortó la paginación o se\n"
            "agotó la cuota). Lo que llegó se aplicó; la corrida siguiente vuelve\n"
            f"a pedir la ventana. Incompletas seguidas: {seguidas} de "
            f"{args.incompletas_toleradas}\n"
            "toleradas antes de salir con error."
        )
        codigo = 0
    else:
        print(
            f"\nERROR: el listado quedó incompleto ({seguidas or 1} corridas seguidas).\n"
            "La API de Mercado Público lleva horas fallando o la cuota se agotó:\n"
            "hay cambios de estado sin mirar. Lo que llegó se aplicó."
        )
        codigo = 1

    print(f"\nCorrida en {(time.perf_counter() - inicio) / 60:.1f} min.")
    return codigo


async def _aplicar(
    engine: AsyncEngine,
    qdrant: AsyncQdrantClient,
    servicio: TenderIngestionService,
    cambios: list[CambioDeEstado],
) -> ResultadoSyncEstados:
    async with AsyncSession(engine) as session:
        caso = SyncTenderStatusesUseCase(
            repository=TenderRepository(session),
            tender_vector_repo=QdrantTenderRepository(
                client=qdrant, vector_size=settings.embedding_vector_size
            ),
            cola=servicio,
        )
        return await caso.execute(cambios)


async def _registrar(engine: AsyncEngine, completo: bool, listadas: int) -> int:
    async with AsyncSession(engine) as session:
        return await SyncEstadosRunRepository(session).registrar(
            completo=completo, listadas=listadas
        )


async def _correr(args: argparse.Namespace) -> int:
    """Arma las piezas reales y cierra lo que abrió.

    Railway omite la ejecución siguiente de un cron si la anterior sigue viva:
    dejar el engine o el cliente de Qdrant abiertos es un cron que deja de correr.
    """
    servicio, engine, qdrant = construir_servicio(con_embeddings=False)
    try:
        return await sincronizar_estados(
            args,
            listar=servicio.listar_cambios,
            aplicar=lambda cambios: _aplicar(engine, qdrant, servicio, cambios),
            marcar_vencidas=lambda: marcar_vencidas(engine, qdrant),
            preparar_destino=lambda: preparar_destino(engine, qdrant),
            registrar_corrida=lambda completo, listadas: _registrar(
                engine, completo, listadas
            ),
        )
    finally:
        await engine.dispose()
        await qdrant.close()


def construir_parser() -> argparse.ArgumentParser:
    """Los defaults salen de la configuración, así se ajustan por entorno."""
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    p.add_argument(
        "--ventana-horas",
        type=float,
        default=settings.sync_estados_ventana_horas,
        help=(
            "cuántas horas hacia atrás mirar (SYNC_ESTADOS_VENTANA_HORAS, "
            f"{settings.sync_estados_ventana_horas:g}; máx. {MAX_VENTANA_HORAS:g})"
        ),
    )
    p.add_argument(
        "--limite",
        type=int,
        default=settings.sync_estados_limite,
        help=(
            "tope de ítems del listado (SYNC_ESTADOS_LIMITE, "
            f"{settings.sync_estados_limite})"
        ),
    )
    p.add_argument(
        "--sin-marcar",
        action="store_true",
        help="omitir el barrido de vencidas",
    )
    p.add_argument(
        "--confirmar-produccion",
        action="store_true",
        help="requerido si la base no es local",
    )
    p.add_argument(
        "--timeout-minutos",
        type=float,
        default=settings.sync_estados_timeout_minutos,
        help=(
            "tope de la corrida (SYNC_ESTADOS_TIMEOUT_MINUTOS, "
            f"{settings.sync_estados_timeout_minutos:g})"
        ),
    )
    p.add_argument(
        "--incompletas-toleradas",
        type=int,
        default=settings.sync_estados_incompletas_toleradas,
        help=(
            "corridas incompletas seguidas que salen con 0 antes de dar error "
            "(SYNC_ESTADOS_INCOMPLETAS_TOLERADAS, "
            f"{settings.sync_estados_incompletas_toleradas})"
        ),
    )
    return p


def main() -> None:
    args = construir_parser().parse_args()

    print(f"Base de datos : {settings.database_url.split('@')[-1]}\n")

    mensaje = validar_ventana(args.ventana_horas) or verificar_destino(
        settings.database_url, confirmar_produccion=args.confirmar_produccion
    )
    if mensaje:
        print(mensaje, file=sys.stderr)
        sys.exit(2)

    sys.exit(asyncio.run(con_tope(_correr(args), segundos=args.timeout_minutos * 60)))


if __name__ == "__main__":
    main()
