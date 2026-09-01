"""De cuándo a cuándo se le pregunta a Mercado Público en cada corrida.

`fetch_tenders_metadata` pedía siempre las últimas 24 h contadas desde *ahora*,
sin persistir la marca de la última corrida buena. Mientras el scheduler vivía
dentro del proceso web daba casi igual; con un cron diario no, porque una
ejecución que no corre —el servicio caído, un despliegue fallido, la cuota
agotada— deja un hueco que no se vuelve a mirar nunca.

Dos topes acotan el cálculo:

- **Piso**: la ventana nunca baja de 24 h. Pedir de más no cuesta nada, porque
  la cola inserta con ON CONFLICT DO NOTHING; pedir de menos pierde datos.
- **Tope**: la ventana nunca supera los 30 días. Tras un mes caído, una ventana
  de "todo lo que pasó" haría una carga inicial disfrazada de sincronización
  diaria, y se comería la cuota del día sin avisar.
"""

from datetime import UTC, datetime, timedelta

from app.shared.ingestion_window import PISO_VENTANA, TOPE_VENTANA, calcular_ventana


def _utc(dia: int, hora: int = 12) -> datetime:
    return datetime(2026, 9, dia, hora, tzinfo=UTC)


class TestSinCorridasPrevias:
    def test_la_primera_corrida_pide_el_piso(self):
        ahora = _utc(10)

        desde, hasta = calcular_ventana(None, ahora)

        assert hasta == ahora
        assert ahora - desde == PISO_VENTANA


class TestConCorridaPrevia:
    def test_retoma_desde_donde_quedo_la_anterior(self):
        """Lo que se perdió durante la caída se recupera en la corrida siguiente."""
        ahora = _utc(10)
        hace_diez_dias = ahora - timedelta(days=10)

        desde, hasta = calcular_ventana(hace_diez_dias, ahora)

        assert desde == hace_diez_dias
        assert hasta == ahora

    def test_una_corrida_reciente_igual_pide_el_piso(self):
        """Solapar es gratis: la cola deduplica por código con ON CONFLICT."""
        ahora = _utc(10)
        hace_dos_horas = ahora - timedelta(hours=2)

        desde, hasta = calcular_ventana(hace_dos_horas, ahora)

        assert ahora - desde == PISO_VENTANA

    def test_una_caida_larguisima_se_corta_en_el_tope(self):
        """Si no, la sincronización diaria se convierte en una carga inicial."""
        ahora = _utc(10)
        hace_un_ano = ahora - timedelta(days=365)

        desde, hasta = calcular_ventana(hace_un_ano, ahora)

        assert ahora - desde == TOPE_VENTANA

    def test_una_marca_en_el_futuro_no_invierte_la_ventana(self):
        """Un reloj desajustado no puede producir un rango negativo."""
        ahora = _utc(10)
        manana = ahora + timedelta(days=1)

        desde, hasta = calcular_ventana(manana, ahora)

        assert desde < hasta
        assert ahora - desde == PISO_VENTANA


class TestInvariantes:
    def test_la_ventana_siempre_termina_ahora(self):
        ahora = _utc(10)
        for dias in (0, 1, 5, 30, 400):
            _, hasta = calcular_ventana(ahora - timedelta(days=dias), ahora)
            assert hasta == ahora

    def test_la_ventana_nunca_queda_fuera_de_los_topes(self):
        ahora = _utc(10)
        for dias in (0, 1, 5, 30, 400):
            desde, _ = calcular_ventana(ahora - timedelta(days=dias), ahora)
            assert PISO_VENTANA <= (ahora - desde) <= TOPE_VENTANA

    def test_el_piso_es_menor_que_el_tope(self):
        assert PISO_VENTANA < TOPE_VENTANA
