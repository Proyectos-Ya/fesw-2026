"""El mapeo de `id_estado` a código semántico, fijado contra lo medido.

Los valores anteriores venían heredados de la API de Licitaciones, que usa otra
numeración, y nadie los había contrastado con Compra Ágil v2. La guía oficial
documenta `estado.codigo` como enum de strings pero **no publica el mapeo
numérico**, así que la única fuente posible es la observación.

Medido el 28 de agosto de 2026 consultando el listado con `estado=<valor>` y una
ventana de 7 días, y registrando qué `id_estado` devolvía cada uno:

    2 → publicada     3 → cerrada     5 → cancelada     6 → desierta

`proveedor_seleccionado` devolvió 0 resultados y `oc_emitida` un 400, así que sus
ids siguen sin observarse y no se inventan aquí.
"""

from app.shared.constants import (
    ACTIVE_TENDER_STATUSES,
    TENDER_STATUS_CODE_BY_ID,
    TENDER_STATUSES,
)

MEDIDO = {2: "publicada", 3: "cerrada", 5: "cancelada", 6: "desierta"}


class TestMapeoMedido:
    def test_coincide_exactamente_con_lo_observado(self):
        assert TENDER_STATUS_CODE_BY_ID == MEDIDO

    def test_no_declara_ids_que_nunca_se_observaron(self):
        """1, 7, 8 y 18 venían de la API de Licitaciones, no de esta.

        Inventar un significado es peor que no tenerlo: un id desconocido cae en
        "desconocido" y queda fuera de las recomendaciones, que es lo prudente.
        """
        assert not {1, 7, 8, 18} & TENDER_STATUS_CODE_BY_ID.keys()

    def test_los_codigos_salen_del_enum_documentado(self):
        """Nada de literales sueltos: la guía define los seis valores válidos."""
        assert set(TENDER_STATUS_CODE_BY_ID.values()) <= set(TENDER_STATUSES.values())


class TestQueSeConsideraActivo:
    def test_solo_publicada_cuenta_como_activa(self):
        assert ACTIVE_TENDER_STATUSES == {"publicada"}

    def test_desierta_y_cancelada_no_son_activas(self):
        """El bug que esto previene: el 6 estaba mapeado a `publicada`.

        Una licitación desierta quedaba etiquetada como abierta y entraba en
        recomendaciones, ficha y alertas.
        """
        assert TENDER_STATUS_CODE_BY_ID[6] not in ACTIVE_TENDER_STATUSES
        assert TENDER_STATUS_CODE_BY_ID[5] not in ACTIVE_TENDER_STATUSES
