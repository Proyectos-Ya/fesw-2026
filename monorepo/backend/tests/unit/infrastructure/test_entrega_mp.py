"""La entrega y los requisitos del detalle se leen sin inventar datos (plan #294)."""

from typing import Any

import pytest

from app.infrastructure.services.tenders.entrega import leer_entrega, leer_requisitos


def _con_entrega(**entrega: object) -> dict[str, Any]:
    return {"entrega": entrega}


def _con_flags(**flags: object) -> dict[str, Any]:
    return {"flags": flags}


class TestEntrega:
    def test_la_forma_documentada_se_lee_tal_cual(self):
        entrega = leer_entrega(
            _con_entrega(
                direccion_entrega="SERVIU REGION DE AYSEN RAMON FREIRE 5",
                plazo_entrega_dias=5,
            )
        )

        assert entrega.direccion == "SERVIU REGION DE AYSEN RAMON FREIRE 5"
        assert entrega.plazo_dias == 5

    def test_la_direccion_pierde_los_espacios_del_borde(self):
        entrega = leer_entrega(_con_entrega(direccion_entrega="  Calle 1  "))

        assert entrega.direccion == "Calle 1"

    @pytest.mark.parametrize("valor", ["", "   ", None, 17, True, ["Calle 1"]])
    def test_una_direccion_vacia_o_rara_es_none(self, valor):
        assert leer_entrega(_con_entrega(direccion_entrega=valor)).direccion is None

    def test_un_plazo_de_cero_dias_es_un_dato(self):
        assert leer_entrega(_con_entrega(plazo_entrega_dias=0)).plazo_dias == 0

    @pytest.mark.parametrize("valor", [None, -1, "5", 5.0, True, False])
    def test_un_plazo_raro_es_none(self, valor):
        assert leer_entrega(_con_entrega(plazo_entrega_dias=valor)).plazo_dias is None

    @pytest.mark.parametrize(
        "detalle",
        [{}, {"entrega": None}, {"entrega": "Calle 1"}, {"entrega": ["Calle 1"]}],
        ids=["sin entrega", "entrega null", "entrega texto", "entrega lista"],
    )
    def test_sin_un_objeto_entrega_todo_es_none(self, detalle):
        entrega = leer_entrega(detalle)

        assert entrega.direccion is None
        assert entrega.plazo_dias is None


class TestRequisitos:
    def test_los_dos_flags_se_leen_tal_cual(self):
        requisitos = leer_requisitos(
            _con_flags(
                considera_requisitos_medioambientales=True,
                considera_requisitos_impacto_social_economico=False,
            )
        )

        assert requisitos.medioambientales is True
        # `False` es un dato: el comprador dijo que no los considera.
        assert requisitos.impacto_social is False

    @pytest.mark.parametrize("valor", [None, 1, 0, "true", "false"])
    def test_un_flag_que_no_es_booleano_es_none(self, valor):
        requisitos = leer_requisitos(
            _con_flags(
                considera_requisitos_medioambientales=valor,
                considera_requisitos_impacto_social_economico=valor,
            )
        )

        assert requisitos.medioambientales is None
        assert requisitos.impacto_social is None

    @pytest.mark.parametrize(
        "detalle",
        [{}, {"flags": None}, {"flags": "si"}, {"flags": [True]}],
        ids=["sin flags", "flags null", "flags texto", "flags lista"],
    )
    def test_sin_un_objeto_flags_todo_es_none(self, detalle):
        requisitos = leer_requisitos(detalle)

        assert requisitos.medioambientales is None
        assert requisitos.impacto_social is None
