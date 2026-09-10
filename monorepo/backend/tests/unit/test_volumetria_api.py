"""El arnés de volumetría (spike-2).

Dos cosas se comprueban acá y ninguna es cosmética.

**El corte del día es chileno, no UTC.** La API recibe el rango en UTC, así que
si el día se cortara a las 00:00 Z, todo lo publicado después de las 20:00 en
Chile caería en el día siguiente del informe. Con el corte en `CHILE_TZ` el
desfase se convierte en el offset correcto, y ese offset cambia con el horario
de verano.

**Un `None` nunca se convierte en 0.** La serie distingue "ese día no se publicó
nada" de "no se pudo preguntar". Si la segunda se emitiera como cero, un día de
caída de la API entraría al informe como un día sin actividad.
"""

import argparse
import json
from datetime import date

import httpx
import pytest
import respx

from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)
from scripts import volumetria_api
from scripts.volumetria_api import _limites_del_dia, medir

URL = "https://api2.mercadopublico.cl/v2/compra-agil"


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    """Ni pausa entre muestras ni backoff entre reintentos.

    Los dos existen para no apretar la API de verdad; contra respx solo hacen
    que la suite tarde minutos.
    """
    monkeypatch.setattr(volumetria_api, "PAUSA_ENTRE_MUESTRAS", 0)


def _cliente() -> MercadoPublicoClient:
    return MercadoPublicoClient(api_key="t", espera_base=0)


def _args(**extra) -> argparse.Namespace:
    base = {"dias_atras": 1, "sin_relativas": False, "ttl_horas": [24, 48]}
    base.update(extra)
    return argparse.Namespace(**base)


def _con_total(total: int) -> httpx.Response:
    return httpx.Response(
        200, json={"payload": {"items": [], "paginacion": {"total_resultados": total}}}
    )


class TestCorteDelDia:
    def test_el_dia_empieza_a_medianoche_en_chile(self):
        desde, hasta = _limites_del_dia(date(2026, 8, 1))

        assert desde.isoformat() == "2026-08-01T00:00:00-04:00"
        assert hasta.isoformat() == "2026-08-02T00:00:00-04:00"

    def test_el_offset_sigue_al_horario_de_verano(self):
        """En enero Chile está en -03:00. Un corte en UTC no lo notaría."""
        desde, _ = _limites_del_dia(date(2026, 1, 15))

        assert desde.isoformat() == "2026-01-15T00:00:00-03:00"

    def test_la_ventana_dura_exactamente_un_dia(self):
        desde, hasta = _limites_del_dia(date(2026, 8, 1))

        assert (hasta - desde).total_seconds() == 24 * 3600


class TestSeriesQueSeMiden:
    @respx.mock
    @pytest.mark.asyncio
    async def test_una_peticion_por_muestra(self):
        """1 día × 2 series + 2 ventanas ttl + los 6 estados = 10."""
        ruta = respx.get(URL).mock(return_value=_con_total(7))

        muestras = await medir(_args(), _cliente())

        assert len(muestras) == 10
        assert ruta.call_count == 10

    @respx.mock
    @pytest.mark.asyncio
    async def test_emite_las_series_esperadas(self):
        respx.get(URL).mock(return_value=_con_total(7))

        muestras = await medir(_args(), _cliente())

        assert [m.serie for m in muestras][:4] == [
            "publicadas_dia",
            "publicadas_dia_vigentes",
            "cambios_ttl",
            "cambios_ttl",
        ]
        assert {m.serie for m in muestras[4:]} == {"cambios_24h_estado"}

    @respx.mock
    @pytest.mark.asyncio
    async def test_los_estados_particionan_el_universo(self):
        """Sin esta partición, la ventana de 24 h satura y deja de ser un número."""
        respx.get(URL).mock(return_value=_con_total(7))

        muestras = await medir(_args(), _cliente())

        estados = [m.estado for m in muestras if m.serie == "cambios_24h_estado"]
        assert estados == list(volumetria_api.ESTADOS)
        assert len(estados) == len(set(estados))

    @respx.mock
    @pytest.mark.asyncio
    async def test_sin_relativas_deja_solo_lo_retroactivo(self):
        """Para la corrida de arranque, que pide un mes de historia de una vez."""
        respx.get(URL).mock(return_value=_con_total(7))

        muestras = await medir(_args(dias_atras=3, sin_relativas=True), _cliente())

        assert len(muestras) == 6
        assert {m.serie for m in muestras} == {
            "publicadas_dia",
            "publicadas_dia_vigentes",
        }

    @respx.mock
    @pytest.mark.asyncio
    async def test_las_series_por_dia_llevan_su_fecha(self):
        respx.get(URL).mock(return_value=_con_total(7))

        muestras = await medir(_args(sin_relativas=True), _cliente())

        assert all(m.fecha is not None for m in muestras)
        assert len({m.fecha for m in muestras}) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_la_serie_vigentes_filtra_por_estado_en_el_servidor(self):
        respx.get(URL).mock(return_value=_con_total(7))

        muestras = await medir(_args(sin_relativas=True), _cliente())

        vigentes = next(m for m in muestras if m.serie == "publicadas_dia_vigentes")
        assert vigentes.estado == "publicada"


class TestTopeDeLaApi:
    """10.000 es el techo de la respuesta, no un conteo.

    Medido el 2026-09-10: las ventanas de cambios de 24 h y de 48 h devuelven
    exactamente el mismo 10.000. Cargar ese número como si fuera el dato real
    sería subestimar el volumen justo donde la decisión de arquitectura se juega.
    """

    @respx.mock
    @pytest.mark.asyncio
    async def test_la_muestra_en_el_tope_queda_marcada(self):
        respx.get(URL).mock(return_value=_con_total(10000))

        muestras = await medir(_args(sin_relativas=True), _cliente())

        assert all(m.saturada for m in muestras)

    @respx.mock
    @pytest.mark.asyncio
    async def test_un_total_normal_no_queda_marcado(self):
        respx.get(URL).mock(return_value=_con_total(4598))

        muestras = await medir(_args(sin_relativas=True), _cliente())

        assert not any(m.saturada for m in muestras)

    @respx.mock
    @pytest.mark.asyncio
    async def test_la_marca_viaja_en_la_linea_emitida(self, capsys):
        respx.get(URL).mock(return_value=_con_total(10000))

        await medir(_args(sin_relativas=True), _cliente())

        lineas = [
            json.loads(ln.removeprefix("VOLUMETRIA "))
            for ln in capsys.readouterr().out.splitlines()
            if ln.startswith("VOLUMETRIA ")
        ]
        assert lineas
        assert all(ln["saturada"] is True for ln in lineas)

    @respx.mock
    @pytest.mark.asyncio
    async def test_sin_dato_no_cuenta_como_saturada(self):
        respx.get(URL).mock(return_value=httpx.Response(504))

        muestras = await medir(_args(sin_relativas=True), _cliente())

        assert not any(m.saturada for m in muestras)


class TestCuandoLaApiNoResponde:
    @respx.mock
    @pytest.mark.asyncio
    async def test_la_muestra_queda_en_none_y_no_en_cero(self):
        respx.get(URL).mock(return_value=httpx.Response(504))

        muestras = await medir(_args(), _cliente())

        assert all(m.total is None for m in muestras)

    @respx.mock
    @pytest.mark.asyncio
    async def test_la_linea_emitida_lleva_null_y_no_cero(self, capsys):
        respx.get(URL).mock(return_value=httpx.Response(504))

        await medir(_args(dias_atras=1, sin_relativas=True), _cliente())

        lineas = [
            json.loads(ln.removeprefix("VOLUMETRIA "))
            for ln in capsys.readouterr().out.splitlines()
            if ln.startswith("VOLUMETRIA ")
        ]
        assert lineas
        assert all(ln["total"] is None for ln in lineas)


class TestLineasEmitidas:
    @respx.mock
    @pytest.mark.asyncio
    async def test_cada_muestra_sale_como_json_con_la_marca(self, capsys):
        respx.get(URL).mock(return_value=_con_total(42))

        await medir(_args(dias_atras=1, sin_relativas=True), _cliente())

        lineas = [
            ln
            for ln in capsys.readouterr().out.splitlines()
            if ln.startswith("VOLUMETRIA ")
        ]
        assert len(lineas) == 2

        primera = json.loads(lineas[0].removeprefix("VOLUMETRIA "))
        assert primera["schema"] == 1
        assert primera["serie"] == "publicadas_dia"
        assert primera["total"] == 42
        assert primera["medido_en"].endswith("Z")
