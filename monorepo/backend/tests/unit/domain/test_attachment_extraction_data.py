"""Tests de los modelos de datos de extracción (plan 233, decisión 4)."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.domain.entities.attachment_extraction import AttachmentExtractionData
from tests.unit.application.attachment_processing_fakes import EXTRACCION_VALIDA


def test_extraccion_valida():
    data = AttachmentExtractionData.model_validate(EXTRACCION_VALIDA)
    assert data.resumen_general.texto.startswith("Consultoría")
    assert len(data.requisitos) == 1
    assert data.fecha_cierre_primer_llamado is not None
    assert data.fecha_cierre_primer_llamado.hora == "15:00"


def test_requisito_sin_citas_lanza_validation_error():
    invalido = deepcopy(EXTRACCION_VALIDA)
    invalido["requisitos"][0]["citas"] = []
    with pytest.raises(ValidationError) as exc:
        AttachmentExtractionData.model_validate(invalido)
    error = exc.value.errors()[0]
    assert error["loc"] == ("requisitos", 0, "citas")
    assert error["type"] == "too_short"

    del invalido["requisitos"][0]["citas"]
    with pytest.raises(ValidationError) as exc_missing:
        AttachmentExtractionData.model_validate(invalido)
    error_missing = exc_missing.value.errors()[0]
    assert error_missing["loc"] == ("requisitos", 0, "citas")
    assert error_missing["type"] == "missing"


def test_falta_resumen_general():
    invalido = deepcopy(EXTRACCION_VALIDA)
    del invalido["resumen_general"]
    with pytest.raises(ValidationError):
        AttachmentExtractionData.model_validate(invalido)


def test_fechas_y_horas_invalidas():
    invalido_fecha = deepcopy(EXTRACCION_VALIDA)
    invalido_fecha["fecha_cierre_primer_llamado"]["fecha"] = "2026-13-01"
    with pytest.raises(ValidationError):
        AttachmentExtractionData.model_validate(invalido_fecha)

    invalido_hora = deepcopy(EXTRACCION_VALIDA)
    invalido_hora["fecha_cierre_primer_llamado"]["hora"] = "25:00"
    with pytest.raises(ValidationError):
        AttachmentExtractionData.model_validate(invalido_hora)

    valido_hora_none = deepcopy(EXTRACCION_VALIDA)
    valido_hora_none["fecha_cierre_primer_llamado"]["hora"] = None
    data = AttachmentExtractionData.model_validate(valido_hora_none)
    assert data.fecha_cierre_primer_llamado.hora is None


def test_monto_clp_negativo_lanza():
    invalido = deepcopy(EXTRACCION_VALIDA)
    invalido["presupuesto"]["monto_clp"] = -1
    with pytest.raises(ValidationError):
        AttachmentExtractionData.model_validate(invalido)


def test_clave_extra_se_ignora():
    con_extra = deepcopy(EXTRACCION_VALIDA)
    con_extra["instrucciones"] = "instruccion ignorada"
    data = AttachmentExtractionData.model_validate(con_extra)
    dump = data.model_dump()
    assert "instrucciones" not in dump


def test_todas_las_citas_y_con_documento():
    data = AttachmentExtractionData.model_validate(EXTRACCION_VALIDA)
    citas = list(data.todas_las_citas())
    # 1 presupuesto + 1 cierre + 1 requisito + 1 entregable + 1 punto + 1 resumen = 6 citas
    assert len(citas) == 6

    con_doc = data.con_documento("Bases.pdf")
    # Todas las citas de con_doc tienen 'Bases.pdf'
    assert all(c.documento == "Bases.pdf" for c in con_doc.todas_las_citas())
    # El original no mutó ('x.pdf')
    assert all(c.documento == "x.pdf" for c in data.todas_las_citas())
