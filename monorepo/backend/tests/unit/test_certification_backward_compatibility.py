from datetime import date

import pytest
from pydantic import ValidationError

from app.application.schemas.supplier_schema import (
    CreateSupplierSchema,
    UpdateSupplierSchema,
)
from app.domain.entities.supplier import CertificationItem, Supplier
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.supplier_repository import SupplierRepository

RUT_VALIDO = "76.086.428-5"


def _supplier(certifications: list[object] | None) -> Supplier:
    return Supplier.model_validate(
        {
            "rut": RUT_VALIDO,
            "legal_name": "Constructora Demo SpA",
            "certifications": certifications,
        }
    )


class TestSupplierCertifications:
    def test_acepta_strings_sueltos_de_registros_antiguos(self):
        supplier = _supplier(["ISO 9001", "SEC"])

        assert supplier.certifications == [
            CertificationItem(name="ISO 9001"),
            CertificationItem(name="SEC"),
        ]
        assert supplier.certification_names == ["ISO 9001", "SEC"]

    def test_acepta_dicts_con_fecha_de_vencimiento(self):
        supplier = _supplier([{"name": "ISO 9001", "expires_at": "2026-12-31"}])

        assert supplier.certifications is not None
        assert supplier.certifications[0].expires_at == date(2026, 12, 31)
        assert supplier.certification_names == ["ISO 9001"]

    def test_acepta_instancias_de_certification_item(self):
        item = CertificationItem(name="ISO 9001", expires_at=date(2026, 12, 31))

        assert _supplier([item]).certification_names == ["ISO 9001"]

    def test_acepta_mezcla_de_strings_y_dicts(self):
        supplier = _supplier(["SEC", {"name": "ISO 9001"}])

        assert supplier.certification_names == ["SEC", "ISO 9001"]
        assert supplier.certifications is not None
        assert supplier.certifications[1].expires_at is None

    def test_sin_certificaciones_devuelve_lista_vacia(self):
        assert _supplier(None).certifications is None
        assert _supplier(None).certification_names == []


class TestValidacion:
    @pytest.mark.parametrize("nombre", ["", "   "])
    def test_rechaza_nombre_vacio(self, nombre):
        with pytest.raises(ValidationError):
            _supplier([{"name": nombre}])

    def test_descarta_strings_sueltos_vacios_de_registros_antiguos(self):
        # Rechazarlos haría fallar la lectura de la empresa entera.
        assert _supplier(["", "  ", "SEC"]).certification_names == ["SEC"]

    def test_recorta_el_nombre(self):
        assert _supplier(["  ISO 9001 "]).certification_names == ["ISO 9001"]

    def test_quita_duplicados_sin_mayusculas_ni_tildes_y_conserva_el_primero(self):
        supplier = _supplier(
            [
                {"name": "Certificación SEC", "expires_at": "2026-12-31"},
                "certificacion sec",
                " ISO 9001",
                "iso 9001 ",
            ]
        )

        assert supplier.certification_names == ["Certificación SEC", "ISO 9001"]
        assert supplier.certifications is not None
        assert supplier.certifications[0].expires_at == date(2026, 12, 31)

    def test_reduce_los_espacios_repetidos_dentro_del_nombre(self):
        assert _supplier(["ISO   9001"]).certification_names == ["ISO 9001"]

    def test_quita_duplicados_que_solo_cambian_en_espacios_guiones_o_puntos(self):
        supplier = _supplier(
            ["ISO 9001", "ISO-9001", "iso9001", "ISO_9001", "I.S.O. 9001"]
        )

        assert supplier.certification_names == ["ISO 9001"]

    def test_la_version_de_la_norma_distingue_certificaciones(self):
        """Una base puede exigir la versión 2015; unirlas perdería ese dato."""
        supplier = _supplier(["ISO 9001", "ISO 9001:2015", "ISO 9001:2008"])

        assert supplier.certification_names == [
            "ISO 9001",
            "ISO 9001:2015",
            "ISO 9001:2008",
        ]

    def test_el_esquema_de_edicion_tambien_valida(self):
        with pytest.raises(ValidationError):
            UpdateSupplierSchema.model_validate({"certifications": [{"name": ""}]})

        schema = UpdateSupplierSchema.model_validate({"certifications": ["SEC", "sec"]})
        assert schema.certifications == [CertificationItem(name="SEC")]


class TestSchemas:
    def test_create_schema_acepta_strings_y_dicts(self):
        schema = CreateSupplierSchema.model_validate(
            {
                "rut": RUT_VALIDO,
                "legal_name": "Constructora Demo SpA",
                "description": "Constructora con veinte años en obras civiles.",
                "regions": ["RM"],
                "sectors": ["Construcción"],
                "certifications": [
                    "SEC",
                    {"name": "ISO 9001", "expires_at": "2026-12-31"},
                ],
                "years_experience": 10,
                "num_employees": 5,
            }
        )

        assert schema.certifications == [
            CertificationItem(name="SEC"),
            CertificationItem(name="ISO 9001", expires_at=date(2026, 12, 31)),
        ]

    def test_update_schema_acepta_strings_y_dicts(self):
        schema = UpdateSupplierSchema.model_validate(
            {"certifications": ["SEC", {"name": "ISO 9001"}]}
        )

        assert schema.certifications == [
            CertificationItem(name="SEC"),
            CertificationItem(name="ISO 9001"),
        ]


class TestPersistencia:
    def test_to_model_guarda_json_serializable(self):
        supplier = _supplier(["SEC", {"name": "ISO 9001", "expires_at": "2026-12-31"}])

        model = SupplierRepository(session=None)._to_model(supplier)  # type: ignore[arg-type]

        assert model.certifications == [
            {"name": "SEC", "expires_at": None},
            {"name": "ISO 9001", "expires_at": "2026-12-31"},
        ]

    def test_to_entity_lee_registros_antiguos_con_strings(self):
        supplier = _supplier(["ISO 9001"])
        model = SupplierModel(**supplier.model_dump())
        model.certifications = ["ISO 9001"]

        entity = SupplierRepository(session=None)._to_entity(model)  # type: ignore[arg-type]

        assert entity.certification_names == ["ISO 9001"]
