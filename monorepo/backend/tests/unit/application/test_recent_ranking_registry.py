"""El registro reusa el ranking_id si la misma lista se sirvió hace poco."""

from datetime import datetime, timedelta
from uuid import uuid4

from app.application.services.recent_ranking_registry import RecentRankingRegistry

T0 = datetime(2026, 10, 3, 12, 0)


def _pedir(
    registro: RecentRankingRegistry,
    *,
    user,
    supplier,
    tenders,
    now,
    model="m1",
):
    return registro.resolve(
        user_id=user,
        supplier_id=supplier,
        model_version=model,
        tender_ids=tenders,
        now=now,
    )


def test_la_misma_lista_reusa_el_id_y_la_primera_vez_es_nueva():
    registro = RecentRankingRegistry()
    user, supplier, tenders = uuid4(), uuid4(), [uuid4(), uuid4(), uuid4()]

    id1, nuevo1 = _pedir(registro, user=user, supplier=supplier, tenders=tenders, now=T0)
    id2, nuevo2 = _pedir(
        registro,
        user=user,
        supplier=supplier,
        tenders=tenders,
        now=T0 + timedelta(minutes=10),
    )

    assert nuevo1 is True
    assert nuevo2 is False
    assert id1 == id2


def test_otro_orden_de_licitaciones_es_otro_ranking():
    registro = RecentRankingRegistry()
    user, supplier = uuid4(), uuid4()
    a, b = uuid4(), uuid4()

    id1, _ = _pedir(registro, user=user, supplier=supplier, tenders=[a, b], now=T0)
    id2, nuevo = _pedir(
        registro, user=user, supplier=supplier, tenders=[b, a], now=T0
    )

    assert nuevo is True
    assert id1 != id2


def test_otra_version_del_modelo_es_otro_ranking():
    registro = RecentRankingRegistry()
    user, supplier, tenders = uuid4(), uuid4(), [uuid4()]

    id1, _ = _pedir(registro, user=user, supplier=supplier, tenders=tenders, now=T0)
    id2, nuevo = _pedir(
        registro, user=user, supplier=supplier, tenders=tenders, now=T0, model="m2"
    )

    assert nuevo is True
    assert id1 != id2


def test_pasada_la_ventana_es_un_ranking_nuevo():
    registro = RecentRankingRegistry()
    user, supplier, tenders = uuid4(), uuid4(), [uuid4()]

    id1, _ = _pedir(registro, user=user, supplier=supplier, tenders=tenders, now=T0)
    id2, nuevo = _pedir(
        registro,
        user=user,
        supplier=supplier,
        tenders=tenders,
        now=T0 + timedelta(minutes=31),
    )

    assert nuevo is True
    assert id1 != id2


def test_la_ventana_es_deslizante():
    registro = RecentRankingRegistry()
    user, supplier, tenders = uuid4(), uuid4(), [uuid4()]

    id1, _ = _pedir(registro, user=user, supplier=supplier, tenders=tenders, now=T0)
    id2, _ = _pedir(
        registro,
        user=user,
        supplier=supplier,
        tenders=tenders,
        now=T0 + timedelta(minutes=20),
    )
    # 40 min desde el primero, pero solo 20 desde la última vez que se sirvió.
    id3, nuevo = _pedir(
        registro,
        user=user,
        supplier=supplier,
        tenders=tenders,
        now=T0 + timedelta(minutes=40),
    )

    assert id1 == id2 == id3
    assert nuevo is False


def test_otro_usuario_tiene_otro_ranking():
    registro = RecentRankingRegistry()
    supplier, tenders = uuid4(), [uuid4()]

    id1, _ = _pedir(registro, user=uuid4(), supplier=supplier, tenders=tenders, now=T0)
    id2, nuevo = _pedir(
        registro, user=uuid4(), supplier=supplier, tenders=tenders, now=T0
    )

    assert nuevo is True
    assert id1 != id2


def test_con_el_tope_lleno_expulsa_la_clave_mas_vieja():
    registro = RecentRankingRegistry(max_entries=2)
    supplier, tenders = uuid4(), [uuid4()]
    u1, u2, u3 = uuid4(), uuid4(), uuid4()

    id_u1, _ = _pedir(registro, user=u1, supplier=supplier, tenders=tenders, now=T0)
    _pedir(registro, user=u2, supplier=supplier, tenders=tenders, now=T0)
    _pedir(registro, user=u3, supplier=supplier, tenders=tenders, now=T0)

    # u1 fue expulsada por u3: volver a pedirla da un id nuevo.
    nuevo_id, es_nuevo = _pedir(
        registro, user=u1, supplier=supplier, tenders=tenders, now=T0
    )
    assert es_nuevo is True
    assert nuevo_id != id_u1
