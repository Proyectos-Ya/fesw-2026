"""Descartar por fecha de cierre tiene que leer la hora como la da la API.

Mercado Público entrega todas sus fechas en hora de Chile, aunque el listado
etiquete algunas con "Z" (verificado el 2026-09-28, ver
`tests/unit/shared/test_fechas_mercado_publico.py`). El filtro usa el parser
compartido `fecha_mp_a_utc`, el mismo que el cron de estados, para que las dos
rutas no puedan interpretar distinto la misma fecha.

Antes se tomaba la "Z" como UTC. Con `fecha_cierre` no se notaba, porque ese
campo llega sin zona, pero un cambio de formato habría descartado licitaciones
vivas con tres o cuatro horas de error.
"""

from datetime import UTC, datetime

from app.infrastructure.services.tenders.tender_ingestion_service import (
    _cierre_ya_vencio,
)

AHORA = datetime(2026, 8, 29, 0, 0, tzinfo=UTC).replace(tzinfo=None)


class TestZonaHoraria:
    def test_el_formato_real_se_lee_en_hora_de_chile(self):
        """Las 21:00 del 28 en Chile (UTC-4 en agosto) son la 01:00 del 29 UTC."""
        assert _cierre_ya_vencio("2026-08-28 21:00", AHORA) is False

    def test_un_cierre_pasado_vence(self):
        assert _cierre_ya_vencio("2026-08-28 10:00", AHORA) is True

    def test_la_z_no_se_toma_como_utc(self):
        """El caso que la versión anterior resolvía mal.

        Las 22:00 del 28 "con Z" son las 22:00 en Chile, o sea las 02:00 del 29
        en UTC: dos horas *después* de AHORA, la licitación sigue abierta.
        Tomando la Z como UTC quedaban antes de AHORA y se descartaba viva.
        """
        assert _cierre_ya_vencio("2026-08-28T22:00:00Z", AHORA) is False

    def test_un_offset_explicito_tampoco_cambia_la_hora_de_pared(self):
        assert _cierre_ya_vencio("2026-08-28T22:00:00-04:00", AHORA) is False


class TestAnteLaDudaSeConserva:
    def test_sin_fecha_no_se_descarta(self):
        """La API la documenta siempre presente, pero ausente no es cerrada."""
        assert _cierre_ya_vencio(None, AHORA) is False
        assert _cierre_ya_vencio("", AHORA) is False

    def test_una_fecha_ilegible_no_se_descarta(self):
        """Perder una licitación viva es peor que ingerir una ya cerrada."""
        assert _cierre_ya_vencio("no es una fecha", AHORA) is False
