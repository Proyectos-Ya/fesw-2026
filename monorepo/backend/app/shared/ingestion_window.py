"""De cuándo a cuándo se le pregunta a Mercado Público en cada sincronización.

La ingesta pedía siempre las últimas 24 h contadas desde *ahora*, sin guardar
cuándo terminó la corrida anterior. Con el scheduler dentro del proceso web eso
casi nunca fallaba, porque el proceso está siempre vivo. Con un cron diario sí:
una ejecución que no corre —el servicio caído, un despliegue fallido, la cuota
agotada a mitad— deja un hueco de horas o días que no se vuelve a mirar nunca,
porque la ventana siguiente arranca de nuevo desde *ahora*.

El cálculo vive acá y no en el servicio para poder probarlo sin base de datos:
es aritmética de fechas, y es donde están los casos raros.
"""

from datetime import datetime, timedelta

# La ventana nunca baja de esto, aunque la corrida anterior haya sido hace un
# minuto. Solapar sale gratis —la cola inserta con ON CONFLICT DO NOTHING, así
# que un código repetido no escribe nada— y el error queda del lado seguro: se
# pregunta de más, nunca de menos.
PISO_VENTANA = timedelta(hours=24)

# La ventana nunca supera esto. Tras un mes caído, pedir "todo lo que pasó"
# sería una carga inicial disfrazada de sincronización diaria: se comería las
# 10.000 peticiones del día sin que nadie lo haya decidido. Para eso está
# `scripts/bootstrap_corpus.py`, que es explícito y pide confirmación.
TOPE_VENTANA = timedelta(days=30)


def calcular_ventana(
    ultimo_cierre: datetime | None,
    ahora: datetime,
    *,
    piso: timedelta = PISO_VENTANA,
    tope: timedelta = TOPE_VENTANA,
) -> tuple[datetime, datetime]:
    """Rango a consultar, dado hasta dónde llegó la última corrida buena.

    `ultimo_cierre` es el `window_to` de la última corrida con estado `ok`, o
    None si nunca hubo una. Un valor en el futuro —reloj desajustado, o una
    corrida registrada con la hora mal— se trata como si no existiera: lo que no
    puede pasar es devolver un rango invertido.
    """
    if ultimo_cierre is None or ultimo_cierre >= ahora:
        return ahora - piso, ahora

    antiguedad = ahora - ultimo_cierre
    if antiguedad < piso:
        return ahora - piso, ahora
    if antiguedad > tope:
        return ahora - tope, ahora
    return ultimo_cierre, ahora
