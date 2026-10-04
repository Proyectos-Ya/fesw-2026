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
