"""Volumetría de la API de Mercado Público (spike-2).

Mide **cuántas licitaciones hay**, no cuáles. La pregunta que responde es si la
sincronización diaria conviene como cron aislado en Railway o como cola en
Postgres, y esa decisión depende de un número que nadie había medido: cuántos
cambios publica Compra Ágil al día.

Cada muestra cuesta **una petición** de las 10.000 del ticket, porque el listado
entrega `paginacion.total_resultados` en la primera página (ver
`MercadoPublicoClient.contar`). Una corrida diaria son ~11 peticiones; la corrida
retroactiva de 30 días, ~60. Frente a la cuota, es ruido.

Dos familias de series, y la diferencia entre ellas es la que obliga a que esto
sea un cron y no una sola corrida:

* **Por publicación** — `publicado_desde`/`publicado_hasta` aceptan fechas
  absolutas, así que se pueden medir **días pasados**. Una semana de historia se
  obtiene hoy mismo.
* **Por cambio** — `ttl_cambio_ms` es siempre relativa a *ahora*: no hay forma de
  preguntar "cuántas cambiaron anteayer". Esta serie **solo** se construye
  midiendo a diario, y es justamente la que decide la arquitectura.

La serie que el informe llama `cambios_24h` es la fila de `cambios_ttl` con
`ventana_horas = 24`. No se emite dos veces para no gastar una petición en un
dato que ya está.

Salida
------
Una línea por muestra, con marca fija, pensada para recuperarse de los logs de
Railway (retención de 30 días en el plan Pro):

    VOLUMETRIA {"schema":1,"medido_en":"...","serie":"cambios_ttl",...}

Uso
---
    # Corrida diaria (lo que ejecuta el cron)
    python -m scripts.volumetria_api

    # Corrida retroactiva de arranque: un mes de historia por publicación
    python -m scripts.volumetria_api --dias-atras 30 --sin-relativas

Sólo necesita `MERCADO_PUBLICO_API_KEY` en el entorno. No importa `app.config` a
propósito: ese módulo instancia el `Settings` completo al cargarse y obligaría a
este job a llevar credenciales de base de datos, Supabase y Qdrant para una tarea
que únicamente habla HTTP.
"""

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from itertools import pairwise

from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)
from app.shared.datetime_utils import CHILE_TZ

MARCA = "VOLUMETRIA"

# Versión del formato de las líneas emitidas. Si algún día cambia la forma del
# JSON, esto permite leer un CSV que mezcle corridas viejas y nuevas.
ESQUEMA = 1

# Ventanas de la serie por cambio. Diferenciando dos ventanas consecutivas se
# obtiene una estimación inmediata de los cambios de ese tramo, sin esperar los
# siete días de medición. Es una estimación, no la serie: la API responde por
# licitación cambiada, no por cambio, así que una licitación que cambió dos veces
# en la semana aparece una sola vez en todas las ventanas que la contienen.
TTL_HORAS_POR_DEFECTO = (24, 48, 72, 96, 120, 144, 168)

# Los estados que sacan una licitación de circulación. Dimensionan el barrido de
# retirada: son las que hay que sacar del índice vectorial cada día.
ESTADOS_FUERA_DE_CIRCULACION = "cerrada,desierta,cancelada"

# Pausa entre muestras. La API aplica un balde de tokens que se recarga en
# segundos y responde 429 cuando se la aprieta; el cliente reintenta, pero cada
# reintento igual sale de la cuota del día.
PAUSA_ENTRE_MUESTRAS = 0.5


@dataclass
class Muestra:
    """Una medición. `total` en `None` significa que no se pudo saber.

    No es lo mismo que un 0. Un 0 dice "ese día no se publicó nada"; un None dice
    "la API no respondió". Meter el segundo como si fuera el primero inventa un
    día vacío en la serie, y de ahí no se vuelve.
    """

    serie: str
    total: int | None
    fecha: str | None = None
    estado: str | None = None
    ventana_horas: int | None = None


def _emitir(muestra: Muestra, medido_en: datetime) -> None:
    linea = {
        "schema": ESQUEMA,
        "medido_en": medido_en.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "serie": muestra.serie,
        "fecha": muestra.fecha,
        "estado": muestra.estado,
        "ventana_horas": muestra.ventana_horas,
        "total": muestra.total,
    }
    print(f"{MARCA} {json.dumps(linea, ensure_ascii=False)}", flush=True)


def _limites_del_dia(dia: date) -> tuple[datetime, datetime]:
    """De 00:00 a 00:00 del día siguiente, **en hora de Chile**.

    El corte del día importa: la API recibe el rango en UTC, y con días UTC las
    publicaciones de la tarde chilena caerían en el día siguiente. Como el
    informe habla de días chilenos —y el scheduler ya razona en `CHILE_TZ`—, el
    corte se hace acá y la conversión la hace el cliente.
    """
    inicio = datetime.combine(dia, time.min, tzinfo=CHILE_TZ)
    return inicio, inicio + timedelta(days=1)


async def _muestrear(
    cliente: MercadoPublicoClient,
    medido_en: datetime,
    muestras: list[Muestra],
    serie: str,
    desde: datetime,
    hasta: datetime,
    *,
    por_publicacion: bool = False,
    estado: str | None = None,
    fecha: str | None = None,
    ventana_horas: int | None = None,
) -> None:
    total = await cliente.contar(
        desde, hasta, por_publicacion=por_publicacion, estado=estado
    )
    muestra = Muestra(
        serie=serie,
        total=total,
        fecha=fecha,
        estado=estado,
        ventana_horas=ventana_horas,
    )
    muestras.append(muestra)
    _emitir(muestra, medido_en)
    await asyncio.sleep(PAUSA_ENTRE_MUESTRAS)


async def medir(
    args: argparse.Namespace, cliente: MercadoPublicoClient
) -> list[Muestra]:
    """Recorre las series y emite una línea por muestra.

    Recibe el cliente ya construido en vez de la credencial: así los tests
    inyectan uno sin espera entre reintentos, que es lo que separa una suite de
    dos segundos de una de dos minutos.
    """
    medido_en = datetime.now(UTC)
    muestras: list[Muestra] = []

    # --- Series por publicación: retroactivas, un día completo cada una ---
    hoy_chile = datetime.now(CHILE_TZ).date()
    for atras in range(1, args.dias_atras + 1):
        dia = hoy_chile - timedelta(days=atras)
        desde, hasta = _limites_del_dia(dia)
        etiqueta = dia.isoformat()

        # Sin filtro de estado: cuántas se publicaron ese día, pasara lo que
        # pasara después.
        await _muestrear(
            cliente,
            medido_en,
            muestras,
            "publicadas_dia",
            desde,
            hasta,
            por_publicacion=True,
            fecha=etiqueta,
        )
        # Con filtro: cuántas de ese día siguen publicadas hoy. El cociente
        # contra la anterior es la tasa de cierre, que es la entrada del ciclo
        # de vida del corpus.
        await _muestrear(
            cliente,
            medido_en,
            muestras,
            "publicadas_dia_vigentes",
            desde,
            hasta,
            por_publicacion=True,
            estado="publicada",
            fecha=etiqueta,
        )

    if args.sin_relativas:
        return muestras

    # --- Series por cambio: solo se pueden medir desde ahora hacia atrás ---
    for horas in args.ttl_horas:
        await _muestrear(
            cliente,
            medido_en,
            muestras,
            "cambios_ttl",
            medido_en - timedelta(hours=horas),
            medido_en,
            ventana_horas=horas,
        )

    # Cuántas salieron de circulación en 24 h. Es lo que tendría que retirar del
    # índice el barrido diario.
    await _muestrear(
        cliente,
        medido_en,
        muestras,
        "cambios_24h_no_publicadas",
        medido_en - timedelta(hours=24),
        medido_en,
        estado=ESTADOS_FUERA_DE_CIRCULACION,
        ventana_horas=24,
    )

    return muestras


def _resumen(muestras: list[Muestra]) -> None:
    """Lectura humana. Las cifras que importan van igual en las líneas de arriba."""
    medidas = [m for m in muestras if m.total is not None]
    print(f"\n{len(medidas)}/{len(muestras)} muestras obtenidas.", file=sys.stderr)

    ttl: dict[int, int] = {
        m.ventana_horas: m.total
        for m in muestras
        if m.serie == "cambios_ttl"
        and m.total is not None
        and m.ventana_horas is not None
    }
    if 24 in ttl:
        cambios = ttl[24]
        print(
            f"\ncambios_24h = {cambios}  →  {cambios} peticiones de detalle al día\n"
            f"si se habilitan las actualizaciones ({cambios / 100:.0f}% de la cuota).",
            file=sys.stderr,
        )

    if len(ttl) > 1:
        print("\nEstimación por tramo (diferencia entre ventanas):", file=sys.stderr)
        for anterior, actual in pairwise(sorted(ttl)):
            print(
                f"  {anterior:>3}-{actual:>3} h atrás: "
                f"{ttl[actual] - ttl[anterior]:>6}",
                file=sys.stderr,
            )
        print(
            "  (es una cota inferior: una licitación que cambió dos veces se\n"
            "   cuenta una sola vez en cada ventana que la contiene)",
            file=sys.stderr,
        )

    for serie in ("publicadas_dia", "publicadas_dia_vigentes"):
        totales = [
            m.total for m in muestras if m.serie == serie and m.total is not None
        ]
        if totales:
            print(
                f"\n{serie}: {len(totales)} días, "
                f"mín {min(totales)} / mediana {sorted(totales)[len(totales) // 2]} "
                f"/ máx {max(totales)}",
                file=sys.stderr,
            )

    if any(m.total is None for m in muestras):
        fallidas = [m.serie for m in muestras if m.total is None]
        print(
            f"\nAVISO: {len(fallidas)} muestras sin dato ({', '.join(sorted(set(fallidas)))}).\n"
            "No son ceros: la API no respondió. No las cargues como 0 en la serie.",
            file=sys.stderr,
        )


def main() -> None:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    p.add_argument(
        "--dias-atras",
        type=int,
        default=2,
        help="días completos hacia atrás a medir por publicación (2)",
    )
    p.add_argument(
        "--sin-relativas",
        action="store_true",
        help="omitir las series por cambio (para una corrida solo retroactiva)",
    )
    p.add_argument(
        "--ttl-horas",
        type=int,
        nargs="+",
        default=list(TTL_HORAS_POR_DEFECTO),
        help="ventanas de la serie por cambio, en horas",
    )
    args = p.parse_args()

    api_key = os.environ.get("MERCADO_PUBLICO_API_KEY", "").strip()
    if not api_key:
        sys.exit(
            "Falta MERCADO_PUBLICO_API_KEY en el entorno.\n"
            "Es lo único que este script necesita: no abre base de datos ni Qdrant."
        )

    if args.dias_atras < 0:
        sys.exit("--dias-atras no puede ser negativo.")

    muestras = asyncio.run(medir(args, MercadoPublicoClient(api_key=api_key)))
    _resumen(muestras)

    if muestras and all(m.total is None for m in muestras):
        # Ninguna muestra salió: la API estuvo caída toda la corrida. Que el cron
        # figure como fallido es la señal correcta.
        sys.exit(1)


if __name__ == "__main__":
    main()
