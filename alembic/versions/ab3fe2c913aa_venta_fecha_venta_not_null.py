"""venta_fecha_venta_not_null Hace NOT NULL la columna fecha_venta en la tabla venta."""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ab3fe2c913aa"
down_revision: str | Sequence[str] | None = "11ba81a9e43f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Rellena las fechas NULL y hace fecha_venta obligatoria.
def upgrade() -> None:
    # Actualizar NULLs existentes a la fecha/hora actual
    op.execute(
        "UPDATE venta SET fecha_venta = datetime('now') "
        "WHERE fecha_venta IS NULL"
    )

    # batch_alter_table para SQLite (recrea la tabla internamente)
    with op.batch_alter_table("venta") as batch_op:
        batch_op.alter_column(
            "fecha_venta",
            existing_type=sa.DATETIME(),
            nullable=False,
        )


# Devuelve fecha_venta a opcional.
def downgrade() -> None:
    with op.batch_alter_table("venta") as batch_op:
        batch_op.alter_column(
            "fecha_venta",
            existing_type=sa.DATETIME(),
            nullable=True,
        )
