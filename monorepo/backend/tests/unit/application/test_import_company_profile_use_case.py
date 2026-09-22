"""Importación del perfil de la empresa a partir de su RUT (HdU 16).

El caso de uso no sabe de qué API vienen los datos: recibe un `CompanyRecord` del
puerto y siempre arma el mismo borrador. Los dos registros de prueba reproducen lo
que entregan SRE (solo códigos, sin domicilio) y Web Empresario (glosas y
domicilios) para la misma empresa real del spike 1.
"""

import pytest

from app.application.use_cases.supplier.import_company_profile import (
    ImportCompanyProfileUseCase,
)
from app.domain.entities.company_profile import CompanyRecord, EconomicActivity
from app.domain.errors.company_lookup_errors import (
    CompanyLookupNotConfigured,
    CompanyNotFoundInSource,
    InvalidRutForLookup,
)
from tests.unit.application.fakes import FakeCompanyLookupService

RUT = "76668304-5"


def _registro_sre() -> CompanyRecord:
    return CompanyRecord(
        source="sre",
        rut=RUT,
        legal_name="Planeta Libre Soluciones Sustentables Limitada",
        activities=[
            EconomicActivity(code=433000),
            EconomicActivity(code=479100),
            EconomicActivity(code=952200),
        ],
    )


def _registro_web_empresario() -> CompanyRecord:
    return CompanyRecord(
        source="web-empresario",
        rut=RUT,
        legal_name="PLANETA LIBRE SOLUCIONES SUSTENTABLES LIMITADA",
        activities=[
            EconomicActivity(code=433000, description="TERMINACION Y ACABADO DE EDIFICIOS"),
            EconomicActivity(code=479100, description="VENTA AL POR MENOR POR INTERNET"),
            EconomicActivity(code=952200, description="REPARACION DE APARATOS DOMESTICOS"),
        ],
        raw_regions=["V REGION VALPARAISO", "V REGION VALPARAISO", "XIII REGION METROPOLITANA"],
        is_active=True,
    )


async def _importar(registro: CompanyRecord, rut: str = RUT):
    return await ImportCompanyProfileUseCase(FakeCompanyLookupService(registro)).execute(rut)


class TestMismaEstructuraParaCualquierFuente:
    @pytest.mark.parametrize("registro", [_registro_sre(), _registro_web_empresario()])
    async def test_rubros_y_palabras_clave_no_dependen_de_la_fuente(self, registro):
        borrador = await _importar(registro)

        assert borrador.sectors == [
            "Obras de Construcción e Infraestructura",
            "Equipos e Insumos Industriales",
            "Mantención y Reparación",
        ]
        assert "pintura" in borrador.keywords
        assert "reparación de electrodomésticos" in borrador.keywords
        assert borrador.source == registro.source

    async def test_web_empresario_entrega_regiones_con_el_nombre_del_wizard(self):
        borrador = await _importar(_registro_web_empresario())

        assert borrador.regions == ["Valparaíso", "Metropolitana"]
        assert borrador.is_active is True

    async def test_sre_no_entrega_regiones_y_se_avisa(self):
        borrador = await _importar(_registro_sre())

        assert borrador.regions == []
        assert any("regiones" in aviso for aviso in borrador.notices)


class TestCodigosSinCurar:
    async def test_el_rubro_sale_de_la_glosa_oficial_y_no_hay_palabras_clave(self):
        # 432100: "INSTALACIONES ELÉCTRICAS" en el catálogo, sin curación fina.
        registro = CompanyRecord(source="sre", rut=RUT, activities=[EconomicActivity(code=432100)])

        borrador = await _importar(registro)

        assert borrador.keywords == []
        assert borrador.sectors != []
        assert any("palabras clave" in aviso for aviso in borrador.notices)

    async def test_sin_actividades_no_hay_nada_que_sugerir(self):
        registro = CompanyRecord(source="sre", rut=RUT)

        borrador = await _importar(registro)

        assert borrador.sectors == []
        assert borrador.keywords == []
        assert any("actividades" in aviso for aviso in borrador.notices)

    async def test_actividades_repetidas_no_duplican_palabras_clave(self):
        registro = CompanyRecord(
            source="sre",
            rut=RUT,
            activities=[EconomicActivity(code=433000), EconomicActivity(code=433000)],
        )

        borrador = await _importar(registro)

        assert len(borrador.keywords) == len(set(borrador.keywords))


class TestAvisos:
    async def test_mas_de_dos_rubros_pide_confirmar(self):
        borrador = await _importar(_registro_sre())
        assert any("3 rubros" in aviso for aviso in borrador.notices)

    async def test_termino_de_giro_se_avisa(self):
        registro = _registro_web_empresario().model_copy(update={"is_active": False})
        borrador = await _importar(registro)
        assert any("término de giro" in aviso for aviso in borrador.notices)


class TestRut:
    async def test_normaliza_el_rut_antes_de_consultar(self):
        servicio = FakeCompanyLookupService(_registro_sre())

        await ImportCompanyProfileUseCase(servicio).execute("76.668.304-5")

        assert servicio.calls == ["76668304-5"]

    async def test_rut_invalido_no_llega_a_la_fuente(self):
        servicio = FakeCompanyLookupService(_registro_sre())

        with pytest.raises(InvalidRutForLookup):
            await ImportCompanyProfileUseCase(servicio).execute("76.668.304-0")
        assert servicio.calls == []


class TestErrores:
    async def test_sin_fuente_configurada(self):
        with pytest.raises(CompanyLookupNotConfigured):
            await ImportCompanyProfileUseCase(None).execute(RUT)

    async def test_propaga_empresa_no_encontrada(self):
        servicio = FakeCompanyLookupService(error=CompanyNotFoundInSource(RUT))
        with pytest.raises(CompanyNotFoundInSource):
            await ImportCompanyProfileUseCase(servicio).execute(RUT)
