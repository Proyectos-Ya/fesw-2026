from datetime import datetime, timedelta
from uuid import uuid4

from app.domain.entities.export_job import (
    EXPORT_FILE_TTL,
    ExportFormat,
    ExportJob,
    ExportJobStatus,
)

AHORA = datetime(2026, 9, 28, 12, 0, 0)


def _job(formato: ExportFormat = ExportFormat.PDF) -> ExportJob:
    return ExportJob.crear(
        user_id=uuid4(),
        supplier_id=uuid4(),
        tender_id=uuid4(),
        format=formato,
        sections=["hitos"],
        file_name="licitacion-1057539-228-COT26.pdf",
        now=AHORA,
    )


def test_nace_en_proceso_y_sin_contenido():
    job = _job()

    assert job.status is ExportJobStatus.PROCESSING
    assert job.content is None
    assert job.expires_at == AHORA + EXPORT_FILE_TTL


def test_el_archivo_se_guarda_siete_dias():
    assert EXPORT_FILE_TTL == timedelta(days=7)


def test_marcar_listo_guarda_el_contenido():
    listo = _job().listo(b"%PDF-1.4", AHORA + timedelta(seconds=30))

    assert listo.status is ExportJobStatus.READY
    assert listo.content == b"%PDF-1.4"
    assert listo.finished_at == AHORA + timedelta(seconds=30)


def test_marcar_fallido_registra_el_motivo():
    fallido = _job().fallido("ReportLab explotó", AHORA)

    assert fallido.status is ExportJobStatus.FAILED
    assert fallido.error == "ReportLab explotó"
    assert fallido.content is None


def test_se_puede_descargar_solo_listo_y_antes_de_vencer():
    listo = _job().listo(b"x", AHORA)

    assert listo.descargable(AHORA + timedelta(days=6)) is True
    assert listo.descargable(AHORA + timedelta(days=7)) is False
    assert _job().descargable(AHORA) is False


def test_el_tipo_de_contenido_depende_del_formato():
    assert ExportFormat.PDF.media_type == "application/pdf"
    assert ExportFormat.XLSX.media_type == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
