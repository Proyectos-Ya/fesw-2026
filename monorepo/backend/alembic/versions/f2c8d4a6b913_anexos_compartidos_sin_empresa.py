"""anexos compartidos sin empresa dueña

Revision ID: f2c8d4a6b913
Revises: e4a7c2d9b815
Create Date: 2026-10-03 18:00:00.000000

Plan 233, decisión 6. La versión compartida de un anexo es una fila de
`attachment_file` sin empresa (`workspace_id` NULL): así el CASCADE de `supplier`
borra los aportes de una empresa y nunca lo compartido. Compatible hacia atrás:
la versión anterior nunca escribe NULL ni `shared`, y los CHECK nuevos solo
restringen lo que esta decisión escribe.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2c8d4a6b913"
down_revision: str | Sequence[str] | None = "e4a7c2d9b815"  # = salida de `alembic heads`
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("attachment_file", "workspace_id", existing_type=sa.Uuid(), nullable=True)
    op.create_check_constraint(
        "ck_attachment_file_shared_sin_empresa",
        "attachment_file",
        "visibility = 'private' OR workspace_id IS NULL",
    )
    op.create_check_constraint(
        "ck_attachment_file_shared_corroborado",
        "attachment_file",
        "visibility = 'private' OR trust = 'corroborated'",
    )
    op.create_check_constraint(
        "ck_attachment_file_canonico_sin_autor",
        "attachment_file",
        "workspace_id IS NOT NULL OR uploader_user_id IS NULL",
    )
    # Únicos parciales: la UQ (anexo, sha, empresa) de la decisión 2 no protege las
    # filas sin empresa, porque NULL es distinto de NULL.
    op.create_index(
        "uq_attachment_file_canonical_sha",
        "attachment_file",
        ["tender_attachment_id", "sha256"],
        unique=True,
        postgresql_where=sa.text("workspace_id IS NULL"),
    )
    op.create_index(
        "uq_attachment_file_shared_attachment",
        "attachment_file",
        ["tender_attachment_id"],
        unique=True,
        postgresql_where=sa.text("visibility = 'shared'"),
    )


def downgrade() -> None:
    op.drop_index("uq_attachment_file_shared_attachment", table_name="attachment_file")
    op.drop_index("uq_attachment_file_canonical_sha", table_name="attachment_file")
    op.drop_constraint("ck_attachment_file_canonico_sin_autor", "attachment_file", type_="check")
    op.drop_constraint("ck_attachment_file_shared_corroborado", "attachment_file", type_="check")
    op.drop_constraint("ck_attachment_file_shared_sin_empresa", "attachment_file", type_="check")
    # La versión anterior no admite filas sin empresa (NOT NULL). Se borran las
    # canónicas: sus objetos siguen en `shared/` y la promoción las recrea con la
    # próxima subida del anexo.
    op.execute("DELETE FROM attachment_file WHERE workspace_id IS NULL")
    op.alter_column("attachment_file", "workspace_id", existing_type=sa.Uuid(), nullable=False)
