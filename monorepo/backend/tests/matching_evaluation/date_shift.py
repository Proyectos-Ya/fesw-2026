"""Rejuvenece las fechas del dataset de prueba (`chiripa_tenders.xlsx`).

El xlsx es una foto de Mercado Público tomada un día concreto. A las pocas
semanas todas sus licitaciones están cerradas, y el matching descarta lo que
tenga `closing_at` en el pasado: se carga el dataset completo y el dashboard sale
vacío.

Este módulo le suma a cada licitación vencida un mes (los que hagan falta si la
foto es más vieja) en sus tres fechas, manteniendo la separación entre
publicación, cierre y último cambio.

Lo llama `load_postgres_robust.py` al cargar el dump: es lo que mantiene el corpus
de prueba visible en la app sin tener que regenerarlo ni gastar cuota de la API.
Las licitaciones son auténticas, con la fecha corrida.
"""

import pandas as pd

COLUMNAS_DE_FECHA = ("published_at", "closing_at", "last_change_at")


def desplazar_licitaciones_vencidas(
    licitaciones: pd.DataFrame, ahora: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Devuelve una copia con las licitaciones cerradas corridas hacia adelante.

    El desplazamiento es por licitación y en meses enteros: los mínimos para que
    su `closing_at` vuelva a estar en el futuro. Las vigentes quedan intactas.
    """
    ahora = ahora if ahora is not None else pd.Timestamp.now()
    desplazadas = licitaciones.copy()
    if "closing_at" not in desplazadas.columns:
        return desplazadas

    cierres = pd.to_datetime(desplazadas["closing_at"])
    vencidas = cierres.notna() & (cierres <= ahora)
    if not vencidas.any():
        return desplazadas

    for indice in desplazadas.index[vencidas]:
        meses = _meses_para_revivir(cierres[indice], ahora)
        for columna in COLUMNAS_DE_FECHA:
            if columna not in desplazadas.columns:
                continue
            fecha = desplazadas.at[indice, columna]
            if pd.isna(fecha):
                continue
            desplazadas.at[indice, columna] = pd.Timestamp(fecha) + pd.DateOffset(
                months=meses
            )
    return desplazadas


def _meses_para_revivir(cierre: pd.Timestamp, ahora: pd.Timestamp) -> int:
    """Cuántos meses hay que sumarle a `cierre` para dejarlo después de `ahora`.

    Se itera en vez de calcular la diferencia porque los meses no duran lo mismo:
    un cierre el día 31 puede caer en un mes de 30 y adelantarse un día.
    """
    meses = 1
    while cierre + pd.DateOffset(months=meses) <= ahora:
        meses += 1
    return meses


def fechas_de_registro(
    licitaciones: pd.DataFrame, ahora: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Devuelve una copia con `created_at` y `updated_at` listos para insertar.

    Salen de `published_at` y `last_change_at`, pero nunca pasan de `ahora`. Esas
    dos fechas ya vienen corridas hacia adelante, y una licitación revivida queda
    "publicada" en el futuro. `created_at` dice cuándo llegó la fila a la base, así
    que un valor futuro es falso, y además rompe el caché del ranking: este compara
    la licitación más reciente contra la hora del último cálculo, y con una fecha
    futura la caché queda obsoleta en cada visita.
    """
    ahora = ahora if ahora is not None else pd.Timestamp.now()
    con_registro = licitaciones.copy()
    con_registro["created_at"] = _acotar(licitaciones["published_at"], ahora)
    con_registro["updated_at"] = _acotar(licitaciones["last_change_at"], ahora)
    return con_registro


def _acotar(fechas: pd.Series, ahora: pd.Timestamp) -> pd.Series:
    """El menor entre cada fecha y `ahora`; las nulas siguen nulas."""
    fechas = pd.to_datetime(fechas)
    return fechas.where(fechas.isna() | (fechas <= ahora), ahora)
