"""Cuándo se sincroniza la metadata de licitaciones.

Dos defectos que estos tests fijan, y que se agravaban entre sí:

1. `fetch_tenders_metadata()` se ejecutaba en cada arranque del proceso. En un
   entorno gestionado eso ocurre en cada despliegue y en cada reinicio, y si la
   aplicación entra en bucle de caídas, cada intento dispara otra descarga
   completa contra Mercado Público.

2. La próxima ejecución se calculaba como `(ahora + 1 día).replace(hour=2)`, o
   sea siempre mañana. Arrancando a las 00:30, esperaba 25,5 horas en vez de 1,5.

Combinados dan algo peor que la suma: como cada reinicio reinicia el temporizador
de 24 horas, en un entorno con despliegues frecuentes la ejecución programada
nunca llegaba a dispararse, y la descarga del arranque era lo único que mantenía
los datos frescos. Por eso no se puede quitar una sin arreglar la otra.
"""

from datetime import datetime, timedelta

from app.infrastructure.services.tenders.tender_scheduler import (
    HORA_SINCRONIZACION,
    VENTANA_FRESCURA,
    _hace_falta_sincronizar,
    _proxima_ejecucion,
)
from app.shared.datetime_utils import CHILE_TZ


def _chile(dia: int, hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 8, dia, hora, minuto, tzinfo=CHILE_TZ)


class TestProximaEjecucion:
    def test_si_la_hora_de_hoy_no_ha_pasado_se_programa_para_hoy(self):
        """El bug original: sumaba un día antes de fijar la hora."""
        proxima = _proxima_ejecucion(_chile(28, 0, 30))

        assert proxima == _chile(28, HORA_SINCRONIZACION)
        assert (proxima - _chile(28, 0, 30)) == timedelta(hours=1, minutes=30)

    def test_si_la_hora_de_hoy_ya_paso_se_programa_para_manana(self):
        proxima = _proxima_ejecucion(_chile(28, 15))

        assert proxima == _chile(29, HORA_SINCRONIZACION)

    def test_justo_en_la_hora_se_programa_para_manana(self):
        """Si no, al terminar la ejecución de las 02:00 volvería a dispararse."""
        assert _proxima_ejecucion(_chile(28, HORA_SINCRONIZACION)) == _chile(
            29, HORA_SINCRONIZACION
        )

    def test_la_espera_nunca_supera_las_24_horas(self):
        for hora in range(24):
            espera = _proxima_ejecucion(_chile(28, hora)) - _chile(28, hora)
            assert timedelta(0) < espera <= timedelta(hours=24)


class TestSincronizacionAlArrancar:
    def test_sin_datos_previos_sincroniza(self):
        """Primer despliegue: la base está vacía y hay que llenarla."""
        assert _hace_falta_sincronizar(None, _chile(28, 12)) is True

    def test_con_datos_recientes_no_sincroniza(self):
        """Reinicio o despliegue seguido: los datos ya están frescos."""
        ahora = _chile(28, 12)
        hace_poco = ahora - VENTANA_FRESCURA + timedelta(minutes=1)

        assert _hace_falta_sincronizar(hace_poco, ahora) is False

    def test_con_datos_viejos_sincroniza(self):
        """Tras una caída larga no hay que esperar hasta las 02:00."""
        ahora = _chile(28, 12)
        hace_mucho = ahora - VENTANA_FRESCURA - timedelta(minutes=1)

        assert _hace_falta_sincronizar(hace_mucho, ahora) is True

    def test_compara_bien_entre_zonas_horarias(self):
        """La última sincronización llega en UTC y `ahora` viene en hora de Chile.

        Restar dos datetimes con zona distinta es correcto en Python siempre que
        ambos la tengan; el fallo aparecería si uno llegara naive.
        """
        from datetime import UTC

        ahora_chile = _chile(28, 12)
        hace_una_hora_utc = ahora_chile.astimezone(UTC) - timedelta(hours=1)

        assert _hace_falta_sincronizar(hace_una_hora_utc, ahora_chile) is False
