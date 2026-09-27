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

El tope de la API, que es lo primero que sorprende
-------------------------------------------------
`total_resultados` no pasa de 10.000. Medido el 2026-09-10: la ventana de
cambios de 24 h y la de 48 h devuelven **exactamente** el mismo 10.000, que es
la firma de un techo y no de una coincidencia. Un total igual a ese número es
una cota inferior, y por eso cada muestra viaja con un campo `saturada`: leerlo
como un conteo sería subestimar el volumen justo donde se juega la decisión.

El rodeo es la serie `cambios_24h_estado`. La API filtra por el estado
**actual**, así que los estados particionan el universo —ninguna licitación cae
en dos— y cada parte cabe bajo el tope aunque el todo no quepa. La suma de las
partes sí es el total de cambios del día, que es el número que decide si las
actualizaciones entran en la cuota.

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
from app.shared.constants import TENDER_STATUSES
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
# Medido el 2026-09-10: con 24 h el total ya llega al tope y deja de ser un
# número. Las ventanas cortas son las que informan; las largas se conservan como
# testigo de la saturación, porque un lector que solo viera "10.000" podría
# tomarlo por el dato real.
TTL_HORAS_POR_DEFECTO = (1, 3, 6, 12, 24, 48)

# `total_resultados` no pasa de acá. Medido el 2026-09-10: la ventana de cambios
# de 24 h y la de 48 h devuelven exactamente el mismo 10.000, que es la firma de
# un tope y no de una coincidencia. Todo total igual a este número es una **cota
# inferior**, y tratarlo como un conteo sería el peor error que puede cometer
# este arnés.
TOPE_API = 10000

# La API filtra por el estado **actual**, así que los estados particionan el
# universo: ninguna licitación cae en dos. Sumar las partes es la forma de
# obtener el total de cambios cuando la consulta sin filtro satura — cada parte
# es más chica que el tope aunque el todo no lo sea.
ESTADOS = (
    TENDER_STATUSES["PUBLISHED"],
    TENDER_STATUSES["CLOSED"],
    TENDER_STATUSES["DESERTED"],
    TENDER_STATUSES["CANCELLED"],
    TENDER_STATUSES["SUPPLIER_SELECTED"],
    TENDER_STATUSES["PO_ISSUED"],
)

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

    @property
    def saturada(self) -> bool:
        """El total tocó el tope de la API: es una cota inferior, no un conteo."""
        return self.total is not None and self.total >= TOPE_API


def _emitir(muestra: Muestra, medido_en: datetime) -> None:
    linea = {
        "schema": ESQUEMA,
        "medido_en": medido_en.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "serie": muestra.serie,
        "fecha": muestra.fecha,
        "estado": muestra.estado,
        "ventana_horas": muestra.ventana_horas,
        "total": muestra.total,
        "saturada": muestra.saturada,
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

    # Partición del día por estado. Es el rodeo al tope de la API: sin filtro,
    # las 24 h devuelven 10.000 y no se sabe cuántas son de verdad; por estado,
    # cada parte cabe y la suma sí es el total. De paso separa lo que interesa a
    # cada cadencia — las que salen de circulación son las que hay que retirar
    # del índice vectorial.
    for estado in ESTADOS:
        await _muestrear(
            cliente,
            medido_en,
            muestras,
            "cambios_24h_estado",
            medido_en - timedelta(hours=24),
            medido_en,
            estado=estado,
            ventana_horas=24,
        )

    return muestras


def _resumen(muestras: list[Muestra]) -> None:
    """Lectura humana. Las cifras que importan van igual en las líneas de arriba."""
    medidas = [m for m in muestras if m.total is not None]
    print(f"\n{len(medidas)}/{len(muestras)} muestras obtenidas.", file=sys.stderr)

    # --- Cambios por estado: la vía que rodea el tope de la API ---
    por_estado = {
        m.estado: m.total
        for m in muestras
        if m.serie == "cambios_24h_estado" and m.total is not None and m.estado
    }
    if por_estado:
        print("\nCambios en 24 h, por estado actual:", file=sys.stderr)
        for estado, total in sorted(por_estado.items(), key=lambda kv: -kv[1]):
            tope = "  (¡TOPE!)" if total >= TOPE_API else ""
            print(f"  {estado:<24} {total:>6}{tope}", file=sys.stderr)

        suma = sum(por_estado.values())
        completa = all(t < TOPE_API for t in por_estado.values())
        etiqueta = "" if completa else "  (alguna parte tocó el tope: cota inferior)"
        print(f"  {'suma':<24} {suma:>6}{etiqueta}", file=sys.stderr)
        print(
            f"\nCon las actualizaciones habilitadas, esa suma es el número de\n"
            f"peticiones de detalle por día: {suma} de las 10.000 del ticket\n"
            f"({suma / 100:.0f}%), antes de contar las licitaciones nuevas.",
            file=sys.stderr,
        )

    # --- Serie por ventana: sirve sobre todo para ver dónde satura ---
    ttl: dict[int, int] = {
        m.ventana_horas: m.total
        for m in muestras
        if m.serie == "cambios_ttl"
        and m.total is not None
        and m.ventana_horas is not None
    }
    if ttl:
        print("\nCambios acumulados por ventana:", file=sys.stderr)
        for horas in sorted(ttl):
            tope = "  (¡TOPE! el dato real es mayor)" if ttl[horas] >= TOPE_API else ""
            print(f"  últimas {horas:>3} h: {ttl[horas]:>6}{tope}", file=sys.stderr)

    sin_saturar = {h: v for h, v in ttl.items() if v < TOPE_API}
    if len(sin_saturar) > 1:
        print(
            "\nEstimación por tramo (solo ventanas que no tocaron el tope):",
            file=sys.stderr,
        )
        for anterior, actual in pairwise(sorted(sin_saturar)):
            print(
                f"  {anterior:>3}-{actual:>3} h atrás: "
                f"{sin_saturar[actual] - sin_saturar[anterior]:>6}",
                file=sys.stderr,
            )
        print(
            "  (cota inferior: una licitación que cambió dos veces se cuenta una\n"
            "   sola vez en cada ventana que la contiene)",
            file=sys.stderr,
        )

    # --- Series por publicación ---
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

    if any(m.saturada for m in muestras):
        print(
            "\nAVISO: hay muestras en el tope de la API (10.000). Ese número **no es\n"
            "un conteo**, es el techo de la respuesta: el valor real es mayor y no se\n"
            "sabe cuánto. Para esos casos usa la partición por estado o una ventana\n"
            "más corta; no cargues 10.000 como si fuera el dato.",
            file=sys.stderr,
        )

    if any(m.total is None for m in muestras):
        fallidas = [m.serie for m in muestras if m.total is None]
        print(
            f"\nAVISO: {len(fallidas)} muestras sin dato "
            f"({', '.join(sorted(set(fallidas)))}).\n"
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

    # `MERCADO_PUBLICO_API_KEYS` (plural, separados por coma) manda sobre el
    # singular, igual que en `settings.mercado_publico_tickets`. Acá se lee del
    # entorno a mano y no de `app.config` a propósito: ver el docstring del módulo.
    tickets = [
        t.strip()
        for t in os.environ.get(
            "MERCADO_PUBLICO_API_KEYS", os.environ.get("MERCADO_PUBLICO_API_KEY", "")
        ).split(",")
        if t.strip()
    ]
    if not tickets:
        sys.exit(
            "Falta MERCADO_PUBLICO_API_KEY (o MERCADO_PUBLICO_API_KEYS) en el "
            "entorno.\nEs lo único que este script necesita: no abre base de datos "
            "ni Qdrant."
        )

    if args.dias_atras < 0:
        sys.exit("--dias-atras no puede ser negativo.")

    muestras = asyncio.run(medir(args, MercadoPublicoClient(api_keys=tickets)))
    _resumen(muestras)

    if muestras and all(m.total is None for m in muestras):
        # Ninguna muestra salió: la API estuvo caída toda la corrida. Que el cron
        # figure como fallido es la señal correcta.
        sys.exit(1)


if __name__ == "__main__":
    main()
