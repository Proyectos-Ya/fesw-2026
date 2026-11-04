from sqlmodel import SQLModel

import app.infrastructure.repositories.models  # noqa: F401


def test_tender_chat_tables_are_registered_for_alembic() -> None:
    assert "tender_chat_messages" in SQLModel.metadata.tables
    assert "tender_chat_documents" in SQLModel.metadata.tables


def test_tender_attachment_is_registered_for_alembic() -> None:
    assert "tender_attachment" in SQLModel.metadata.tables
    assert "attachments_synced_at" in SQLModel.metadata.tables["tender"].c


def test_ranking_telemetry_tables_are_registered_for_alembic() -> None:
    for tabla in (
        "ranking_impression",
        "tender_interaction",
        "ranking_metric_daily",
        "attachment_priority_shadow",
    ):
        assert tabla in SQLModel.metadata.tables


def test_attachment_file_tables_are_registered_for_alembic() -> None:
    tablas = SQLModel.metadata.tables

    assert "attachment_file" in tablas
    assert "attachment_upload_quota" in tablas


def test_attachment_file_declara_los_defaults_que_compara_alembic() -> None:
    # `compare_server_default=True`: si el modelo no declara el default de la
    # migración, `alembic check` propone quitarlo.
    columnas = SQLModel.metadata.tables["attachment_file"].c

    assert columnas["visibility"].server_default is not None
    assert columnas["visibility"].server_default.arg == "private"  # type: ignore[attr-defined]
    assert columnas["trust"].server_default.arg == "pending"  # type: ignore[union-attr,attr-defined]
    cuota = SQLModel.metadata.tables["attachment_upload_quota"].c
    assert cuota["used"].server_default.arg == "0"  # type: ignore[union-attr,attr-defined]


def test_attachment_file_admite_filas_sin_empresa_para_lo_compartido() -> None:
    # Decisión 6: la versión canónica compartida no es de ninguna empresa, así el
    # CASCADE de `supplier` borra los aportes y nunca lo compartido.
    tabla = SQLModel.metadata.tables["attachment_file"]

    assert tabla.c["workspace_id"].nullable is True
    indices = {i.name: i for i in tabla.indexes}
    for nombre in ("uq_attachment_file_canonical_sha", "uq_attachment_file_shared_attachment"):
        assert indices[nombre].unique is True
    checks = {c.name for c in tabla.constraints if c.name is not None}
    assert {
        "ck_attachment_file_shared_sin_empresa",
        "ck_attachment_file_shared_corroborado",
        "ck_attachment_file_canonico_sin_autor",
    } <= checks


def test_attachment_processing_tables_are_registered_for_alembic() -> None:
    tablas = SQLModel.metadata.tables

    for tabla in (
        "attachment_processing_job",
        "attachment_extraction",
        "tender_digest",
        "attachment_gemini_daily_usage",
    ):
        assert tabla in tablas

    assert "status_reason" in tablas["attachment_file"].c
    assert tablas["attachment_processing_job"].c["attempts"].server_default.arg == "0"
    assert tablas["attachment_gemini_daily_usage"].c["calls"].server_default.arg == "0"

