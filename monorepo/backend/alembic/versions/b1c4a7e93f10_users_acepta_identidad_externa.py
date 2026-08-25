"""users acepta una identidad externa

Primera de dos migraciones para mover la autenticación a Supabase Auth. Esta es
compatible hacia atrás a propósito: agrega la columna como nullable y afloja
`hashed_password`, así que el login propio sigue funcionando mientras se migra
el resto. La segunda exige la identidad externa y elimina las contraseñas.

Revision ID: b1c4a7e93f10
Revises: 2d2720796d82
Create Date: 2026-08-24 19:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c4a7e93f10"
down_revision: str | Sequence[str] | None = "2d2720796d82"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # El `sub` del JWT. Es texto y no UUID: por OIDC es una cadena opaca, y
    # aunque Supabase emita UUIDs, tiparlo así hornearía un detalle suyo.
    op.add_column(
        "users",
        sa.Column(
            "auth_provider_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
    )
    op.create_index(
        op.f("ix_users_auth_provider_id"),
        "users",
        ["auth_provider_id"],
        unique=True,
    )

    # El correo deja de ser la clave de identidad. Mantenerlo único abre una
    # clase de fallos —cambio de correo en el proveedor, dos identidades con el
    # mismo correo— que aparecerían como un 500 al crear el perfil, no como un
    # conflicto que se pueda explicar.
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    # Quien entra por un proveedor externo no tiene contraseña que guardar. Se
    # afloja acá y se elimina la columna en la segunda migración, para que este
    # paso no rompa el login propio que todavía está en pie.
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema.

    Deja `hashed_password` con cadena vacía donde sea NULL: la columna vuelve a
    ser obligatoria y sin eso el ALTER falla. Una cadena vacía no es un hash
    válido, así que esas cuentas no podrán iniciar sesión con contraseña —que es
    exactamente su situación, no una pérdida de información.
    """
    op.execute("UPDATE users SET hashed_password = '' WHERE hashed_password IS NULL")
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        nullable=False,
    )

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.drop_index(op.f("ix_users_auth_provider_id"), table_name="users")
    op.drop_column("users", "auth_provider_id")
