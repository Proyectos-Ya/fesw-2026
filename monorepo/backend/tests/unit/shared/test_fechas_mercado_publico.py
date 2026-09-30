"""Las fechas de Mercado Público son siempre hora de Chile, traigan o no "Z".

Verificado el 2026-09-28 contra la API real (fixture `mp_listado_cambios.json`):
capturado a las 13:28 hora de Chile (16:28 UTC), el último cambio más reciente
del listado decía `13:25:00Z`. Si esa Z fuera UTC, el cambio habría ocurrido
tres horas antes de la captura y antes de la publicación de la licitación. El
detalle de la misma licitación trae `"2026-09-28 13:20"` donde el listado dice
`"2026-09-28T13:20:00.353Z"`: es el mismo reloj.
"""

from datetime import datetime

from app.shared.datetime_utils import fecha_mp_a_utc, leer_fecha_mp


class TestLeerFechaMp:
    def test_el_formato_con_espacio_se_lee_tal_cual(self):
        assert leer_fecha_mp("2026-09-29 13:30") == datetime(2026, 9, 29, 13, 30)

    def test_la_z_se_ignora_porque_es_hora_de_chile(self):
        assert leer_fecha_mp("2026-09-28T13:20:00.353Z") == datetime(
            2026, 9, 28, 13, 20, 0, 353000
        )

    def test_un_offset_explicito_tambien_se_ignora(self):
        """La hora de pared es la de Chile; el sufijo no la cambia."""
        assert leer_fecha_mp("2026-09-28T13:20:00-03:00") == datetime(
            2026, 9, 28, 13, 20
        )

    def test_devuelve_naive(self):
        leida = leer_fecha_mp("2026-09-28T13:20:00Z")
        assert leida is not None and leida.tzinfo is None

    def test_sin_valor_o_ilegible_devuelve_none(self):
        assert leer_fecha_mp(None) is None
        assert leer_fecha_mp("") is None
        assert leer_fecha_mp("no es una fecha") is None


class TestFechaMpAUtc:
    def test_convierte_la_hora_de_chile_a_utc(self):
        # Septiembre de 2026: Chile en horario de verano (UTC-3).
        assert fecha_mp_a_utc("2026-09-29 13:30") == datetime(2026, 9, 29, 16, 30)

    def test_la_z_no_se_toma_como_utc(self):
        assert fecha_mp_a_utc("2026-09-28T13:25:00Z") == datetime(2026, 9, 28, 16, 25)

    def test_el_mismo_instante_en_los_dos_formatos_coincide(self):
        """Listado (con Z) y detalle (sin zona) de la misma licitación."""
        assert fecha_mp_a_utc("2026-09-28T13:20:00Z") == fecha_mp_a_utc(
            "2026-09-28 13:20"
        )

    def test_en_invierno_aplica_utc_menos_4(self):
        assert fecha_mp_a_utc("2026-07-27 17:42") == datetime(2026, 7, 27, 21, 42)

    def test_sin_valor_devuelve_none(self):
        assert fecha_mp_a_utc(None) is None
        assert fecha_mp_a_utc("basura") is None
