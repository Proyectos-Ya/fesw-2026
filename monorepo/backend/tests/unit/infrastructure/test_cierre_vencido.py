"""Descartar por fecha de cierre tiene que respetar la zona horaria.

El bug: el filtro hacía `datetime.fromisoformat(texto).replace(tzinfo=None)`, y
`replace` **descarta** el offset en vez de convertir. Con un sufijo `Z` acierta
por casualidad, porque la hora de pared ya es UTC. Con cualquier otro offset
—`-04:00` es la hora de Chile— se queda con la hora local y la compara contra
UTC: tres o cuatro horas de error, suficiente para descartar licitaciones que
siguen abiertas.

La API documenta ISO-8601 (glosario: `2026-04-01T12:00:00Z`), así que el offset
explícito es un formato válido que puede llegar en cualquier momento.
"""

from datetime import UTC, datetime

from app.infrastructure.services.tenders.tender_ingestion_service import (
    _cierre_ya_vencio,
)

AHORA = datetime(2026, 8, 29, 0, 0, tzinfo=UTC).replace(tzinfo=None)


class TestZonaHoraria:
    def test_un_cierre_futuro_en_utc_no_vence(self):
        assert _cierre_ya_vencio("2026-08-29T10:00:00Z", AHORA) is False

    def test_un_cierre_pasado_en_utc_vence(self):
        assert _cierre_ya_vencio("2026-08-28T10:00:00Z", AHORA) is True

    def test_un_offset_no_utc_se_convierte_en_vez_de_descartarse(self):
        """El caso que el bug rompía.

        Las 22:00 del 28 en Chile (-04:00) son las 02:00 del 29 en UTC, o sea
        dos horas *después* de `AHORA`: la licitación sigue abierta. Descartando
        el offset quedaban las 22:00 del 28 "en UTC", anteriores a AHORA, y la
        licitación se descartaba estando viva.
        """
        assert _cierre_ya_vencio("2026-08-28T22:00:00-04:00", AHORA) is False

    def test_un_naive_se_asume_en_hora_de_chile(self):
        """Convención del proyecto (`to_utc_naive`), y la fuente es chilena.

        Las 21:00 del 28 en Chile son las 01:00 del 29 en UTC: aún abierta.
        """
        assert _cierre_ya_vencio("2026-08-28 21:00", AHORA) is False


class TestAnteLaDudaSeConserva:
    def test_sin_fecha_no_se_descarta(self):
        """La API la documenta siempre presente, pero ausente no es cerrada."""
        assert _cierre_ya_vencio(None, AHORA) is False
        assert _cierre_ya_vencio("", AHORA) is False

    def test_una_fecha_ilegible_no_se_descarta(self):
        """Perder una licitación viva es peor que ingerir una ya cerrada."""
        assert _cierre_ya_vencio("no es una fecha", AHORA) is False
