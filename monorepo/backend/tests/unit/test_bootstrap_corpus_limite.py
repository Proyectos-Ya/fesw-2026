"""La carga inicial no puede truncarse en silencio contra producción.

`fetch_tenders_metadata` cae en `MERCADOPUBLICO_FETCHING_LIMIT` (2000) cuando no
recibe `limite`, y `get_tenders` corta la lista con `all_items[:quantity]`. El
script de carga inicial dejaba ese argumento en None, así que un corpus de más de
2000 licitaciones se cargaba a medias y el log decía "N licitaciones encoladas",
que parece un éxito.

Lo grave no es el truncado sino que sea silencioso: la cuota es de 10.000
peticiones diarias **del ticket, no de la máquina**, así que la corrida no se
puede repetir el mismo día para comprobar.
"""

from scripts.bootstrap_corpus import _falta_limite_explicito, _hay_riesgo_de_truncado


class TestFaltaLimiteExplicito:
    def test_contra_produccion_sin_limite_falta(self):
        assert _falta_limite_explicito(limite=None, es_local=False) is True

    def test_contra_produccion_con_limite_no_falta(self):
        assert _falta_limite_explicito(limite=5000, es_local=False) is False

    def test_en_local_sin_limite_no_falta(self):
        """En local la cuota da igual y se puede repetir: no se estorba."""
        assert _falta_limite_explicito(limite=None, es_local=True) is False


class TestRiesgoDeTruncado:
    def test_avisa_cuando_el_total_supera_el_limite_por_defecto(self):
        assert _hay_riesgo_de_truncado(total=5000, limite=None, tope=2000) is True

    def test_no_avisa_si_el_total_cabe(self):
        assert _hay_riesgo_de_truncado(total=1500, limite=None, tope=2000) is False

    def test_no_avisa_si_el_limite_alcanza(self):
        assert _hay_riesgo_de_truncado(total=5000, limite=6000, tope=2000) is False

    def test_avisa_si_el_limite_explicito_se_queda_corto(self):
        """Pasar --limite no basta: puede quedar por debajo del total real."""
        assert _hay_riesgo_de_truncado(total=5000, limite=3000, tope=2000) is True

    def test_un_total_desconocido_no_dispara_el_aviso(self):
        assert _hay_riesgo_de_truncado(total=0, limite=None, tope=2000) is False
