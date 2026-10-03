"""La licitación expone el llamado vigente y el cierre de cada llamado.

`closing_at` no cambia de significado (sigue siendo el cierre del llamado
vigente) y `esta_cerrada` no mira los campos nuevos: en el primer llamado el
cierre del segundo es solo una fecha posible.
"""

from datetime import datetime

from app.domain.entities.tender import Tender

AHORA = datetime(2026, 9, 29, 17, 0)


def _tender(**cambios: object) -> Tender:
    base: dict[str, object] = {
        "code": "5052-431-COT26",
        "status_id": 2,
        "status_code": "publicada",
        "name": "Chile crece contigo - mesas plegables",
        "published_at": datetime(2026, 9, 28, 16, 19),
        "closing_at": datetime(2026, 9, 29, 16, 30),
        "last_change_at": datetime(2026, 9, 28, 16, 20),
        "buyer_rut": "61.606.901-2",
        "buyer_unit": "Generales",
    }
    base.update(cambios)
    return Tender(**base)  # type: ignore[arg-type]


def test_una_licitacion_antigua_no_trae_llamado():
    tender = _tender()

    assert tender.call_number is None
    assert tender.first_call_closing_at is None
    assert tender.second_call_closing_at is None


def test_se_serializan_en_utc_con_z():
    tender = _tender(
        call_number=1,
        first_call_closing_at=datetime(2026, 9, 29, 16, 30),
        second_call_closing_at=datetime(2026, 9, 30, 16, 40),
    )

    dumped = tender.model_dump(mode="json")

    assert dumped["call_number"] == 1
    assert dumped["first_call_closing_at"] == "2026-09-29T16:30:00Z"
    assert dumped["second_call_closing_at"] == "2026-09-30T16:40:00Z"


def test_sin_llamado_se_serializan_en_null():
    dumped = _tender().model_dump(mode="json")

    assert dumped["call_number"] is None
    assert dumped["first_call_closing_at"] is None
    assert dumped["second_call_closing_at"] is None


def test_el_dump_de_python_conserva_los_datetime():
    # Los repositorios escriben en la base con el valor naive original.
    tender = _tender(second_call_closing_at=datetime(2026, 9, 30, 16, 40))

    assert tender.model_dump()["second_call_closing_at"] == datetime(
        2026, 9, 30, 16, 40
    )


class TestEstaCerradaNoCambia:
    def test_vencido_el_primer_llamado_sigue_cerrada_aunque_haya_fecha_de_segundo(
        self,
    ):
        tender = _tender(
            call_number=1, second_call_closing_at=datetime(2026, 9, 30, 16, 40)
        )

        assert tender.esta_cerrada(AHORA) is True

    def test_en_segundo_llamado_manda_closing_at(self):
        cierre = datetime(2026, 9, 30, 16, 40)
        tender = _tender(
            call_number=2,
            closing_at=cierre,
            first_call_closing_at=datetime(2026, 9, 29, 16, 30),
            second_call_closing_at=cierre,
        )

        assert tender.esta_cerrada(AHORA) is False
