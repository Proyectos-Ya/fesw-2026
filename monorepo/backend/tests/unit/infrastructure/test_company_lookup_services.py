"""Adaptadores de SRE y Web Empresario: cada API a su manera, el mismo `CompanyRecord`.

No tocan la red: `respx` intercepta httpx. Los payloads reproducen lo que el spike 1
vio en respuestas reales (`spikes/spike-1/1.1-onboarding.md`), incluidas sus
trampas: códigos como entero sin cero a la izquierda, texto con la codificación
rota y domicilios repetidos en Web Empresario; solo códigos y ningún domicilio en
SRE.
"""

import json

import httpx
import pytest
import respx

from app.domain.errors.company_lookup_errors import (
    CompanyLookupUnavailable,
    CompanyNotFoundInSource,
)
from app.infrastructure.services.company_lookup.http_company_lookup_service import (
    ChileRutLookupService,
    SreLookupService,
    WebEmpresarioLookupService,
    repair_mojibake,
)

RUT = "76668304-5"
WE_BASE = "https://api-sii-chile.webempresario.com"
WE_URL = f"{WE_BASE}/v1/{RUT}"
SRE_BASE = "https://sre.cl"
SRE_URL = f"{SRE_BASE}/api/company_info"
CHILERUT_BASE = "https://chilerutempresa.cl"
CHILERUT_URL = f"{CHILERUT_BASE}/api/lookup/{RUT}"

# "VALPARAÍSO" en UTF-8 leído como Latin-1, tal como llega de Web Empresario.
VALPARAISO_ROTO = "VALPARAÍSO".encode().decode("latin-1")

WE_PAYLOAD = {
    "success": True,
    "data": {
        "RUT": 76668304,
        "DV": "5",
        "RAZON_SOCIAL": "PLANETA LIBRE SOLUCIONES SUSTENTABLES LIMITADA",
        "FECHA_INICIO_VIG": "2014-08-22",
        "FECHA_TG_VIG": "",
        "actividades": [
            {
                "CODIGO_ACTIVIDAD": 433000,
                "DESC_ACTIVIDAD": "TERMINACION Y ACABADO DE EDIFICIOS",
                "AFECTA_IVA": "S",
            },
            {"CODIGO_ACTIVIDAD": 11101, "DESC_ACTIVIDAD": "CULTIVO DE TRIGO"},
            {"CODIGO_ACTIVIDAD": "no-es-un-codigo"},
        ],
        "domicilios": [
            {"REGION": f"V REGION {VALPARAISO_ROTO}", "COMUNA": VALPARAISO_ROTO},
            {"REGION": f"V REGION {VALPARAISO_ROTO}", "COMUNA": VALPARAISO_ROTO},
            {"REGION": "XIII REGION METROPOLITANA", "COMUNA": "SANTIAGO"},
        ],
    },
}

SRE_PAYLOAD = {
    "razon_social": "Planeta Libre Soluciones Sustentables Limitada",
    "rut": RUT,
    "dte_email": "cl.empresas@defontanadte.com",
    "fecha_resol": "22-08-2014",
    "numero_resol": 80,
    "actecos": ["433000", "479100", "952200"],
    "url": "",
    "actualizado": "2026-08-25",
    "glosa_giro": None,
    "es_mipyme": False,
    "consultas_restantes": 48,
}


def _we() -> WebEmpresarioLookupService:
    return WebEmpresarioLookupService(api_key="we-secreto", base_url=WE_BASE)


CHILERUT_PAYLOAD = {
    "found": True,
    "rut": "76668304",
    "dv": "5",
    "razon_social": "REBOBINADOS SPA",
    "fecha_inicio_actividades": "15-11-2024",
    "giro": "FABRICACION DE PAPEL Y CARTON ONDULADO Y DE ENVASES DE PAPEL Y CARTON",
    "rubro": "INDUSTRIA MANUFACTURERA",
    "subrubro": "FABRICACION DE PAPEL Y DE PRODUCTOS DE PAPEL",
    "categoria_tributaria": "1",
    "afecta_iva": "S",
    "actividades": [
        {
            "codigo": "476103",
            "descripcion": "VENTA AL POR MENOR DE ARTICULOS DE PAPELERIA Y ESCRITORIO EN COMERCIOS ESPECIALIZADOS",
            "afecta_iva": "S",
            "categoria": "1",
        },
        {"codigo": "invalido", "descripcion": "SIN CODIGO"},
    ],
    "comuna": "LA FLORIDA",
    "region": "XIII REGION METROPOLITANA",
    "num_trabajadores": "0",
}


def _sre() -> SreLookupService:
    return SreLookupService(api_key="sre-secreto", base_url=SRE_BASE)


def _chilerut() -> ChileRutLookupService:
    return ChileRutLookupService(api_key="cre-secreto", base_url=CHILERUT_BASE)


class TestReparacionDeCodificacion:
    def test_repara_utf8_leido_como_latin1(self):
        assert repair_mojibake(VALPARAISO_ROTO) == "VALPARAÍSO"

    def test_no_toca_un_texto_correcto(self):
        assert repair_mojibake("VALPARAÍSO") == "VALPARAÍSO"


class TestWebEmpresario:
    @respx.mock
    async def test_consulta_por_get_con_la_key_en_la_cabecera(self):
        ruta = respx.get(WE_URL).mock(return_value=httpx.Response(200, json=WE_PAYLOAD))

        await _we().lookup(RUT)

        assert ruta.calls.last.request.headers["x-api-key"] == "we-secreto"

    @respx.mock
    async def test_traduce_el_payload_al_registro_comun(self):
        respx.get(WE_URL).mock(return_value=httpx.Response(200, json=WE_PAYLOAD))

        record = await _we().lookup(RUT)

        assert record.source == "web-empresario"
        assert record.rut == RUT
        assert record.legal_name == "PLANETA LIBRE SOLUCIONES SUSTENTABLES LIMITADA"
        assert record.is_active is True
        assert [a.code for a in record.activities] == [433000, 11101]
        assert record.activities[0].description == "TERMINACION Y ACABADO DE EDIFICIOS"
        assert record.raw_regions == ["V REGION VALPARAÍSO", "XIII REGION METROPOLITANA"]

    @respx.mock
    async def test_termino_de_giro_registrado_no_esta_vigente(self):
        payload = json.loads(json.dumps(WE_PAYLOAD))
        payload["data"]["FECHA_TG_VIG"] = "2020-01-01"
        respx.get(WE_URL).mock(return_value=httpx.Response(200, json=payload))

        record = await _we().lookup(RUT)

        assert record.is_active is False

    @respx.mock
    async def test_sin_exito_es_empresa_no_encontrada(self):
        respx.get(WE_URL).mock(
            return_value=httpx.Response(200, json={"success": False, "data": None})
        )
        with pytest.raises(CompanyNotFoundInSource):
            await _we().lookup(RUT)


class TestSre:
    @respx.mock
    async def test_consulta_por_post_con_el_token_en_el_cuerpo(self):
        ruta = respx.post(SRE_URL).mock(return_value=httpx.Response(200, json=SRE_PAYLOAD))

        await _sre().lookup(RUT)

        cuerpo = json.loads(ruta.calls.last.request.content)
        assert cuerpo == {"token": "sre-secreto", "rut": RUT, "version": "2.0"}

    @respx.mock
    async def test_traduce_el_payload_al_registro_comun(self):
        respx.post(SRE_URL).mock(return_value=httpx.Response(200, json=SRE_PAYLOAD))

        record = await _sre().lookup(RUT)

        assert record.source == "sre"
        assert record.rut == RUT
        assert record.legal_name == "Planeta Libre Soluciones Sustentables Limitada"
        assert [a.code for a in record.activities] == [433000, 479100, 952200]
        assert all(a.description == "" for a in record.activities)
        assert record.raw_regions == []
        assert record.is_active is None

    @respx.mock
    async def test_sin_razon_social_es_empresa_no_encontrada(self):
        respx.post(SRE_URL).mock(return_value=httpx.Response(200, json={"rut": RUT}))
        with pytest.raises(CompanyNotFoundInSource):
            await _sre().lookup(RUT)


class TestChileRut:
    @respx.mock
    async def test_consulta_por_get_con_la_key_en_la_cabecera(self):
        ruta = respx.get(CHILERUT_URL).mock(return_value=httpx.Response(200, json=CHILERUT_PAYLOAD))

        await _chilerut().lookup(RUT)

        assert ruta.calls.last.request.headers["x-api-key"] == "cre-secreto"

    @respx.mock
    async def test_traduce_el_payload_al_registro_comun(self):
        respx.get(CHILERUT_URL).mock(return_value=httpx.Response(200, json=CHILERUT_PAYLOAD))

        record = await _chilerut().lookup(RUT)

        assert record.source == "chilerut"
        assert record.rut == RUT
        assert record.legal_name == "REBOBINADOS SPA"
        assert [a.code for a in record.activities] == [476103]
        assert (
            record.activities[0].description
            == "VENTA AL POR MENOR DE ARTICULOS DE PAPELERIA Y ESCRITORIO EN COMERCIOS ESPECIALIZADOS"
        )
        assert record.raw_regions == ["XIII REGION METROPOLITANA"]
        assert record.is_active is None

    @respx.mock
    async def test_found_false_es_empresa_no_encontrada(self):
        respx.get(CHILERUT_URL).mock(return_value=httpx.Response(200, json={"found": False}))
        with pytest.raises(CompanyNotFoundInSource):
            await _chilerut().lookup(RUT)


class TestErroresComunes:
    @respx.mock
    async def test_404_es_empresa_no_encontrada(self):
        respx.get(WE_URL).mock(return_value=httpx.Response(404))
        with pytest.raises(CompanyNotFoundInSource):
            await _we().lookup(RUT)

    @pytest.mark.parametrize("codigo", [401, 403, 429, 500, 503])
    @respx.mock
    async def test_credencial_cuota_o_caida_es_fuente_no_disponible(self, codigo):
        respx.post(SRE_URL).mock(return_value=httpx.Response(codigo))
        with pytest.raises(CompanyLookupUnavailable):
            await _sre().lookup(RUT)

    @respx.mock
    async def test_timeout_es_fuente_no_disponible(self):
        respx.get(WE_URL).mock(side_effect=httpx.ConnectTimeout("lento"))
        with pytest.raises(CompanyLookupUnavailable):
            await _we().lookup(RUT)

    @respx.mock
    async def test_respuesta_que_no_es_json_es_fuente_no_disponible(self):
        respx.post(SRE_URL).mock(return_value=httpx.Response(200, content=b"<html>"))
        with pytest.raises(CompanyLookupUnavailable):
            await _sre().lookup(RUT)
