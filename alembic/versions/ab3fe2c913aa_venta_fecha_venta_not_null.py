"""venta_fecha_venta_not_null

Hace NOT NULL la columna fecha_venta en la tabla venta.
En SQLite se usa batch_alter_table porque no soporta ALTER COLUMN.

Revision ID: ab3fe2c913aa
Revises: 11ba81a9e43f

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ab3fe2c913aa"
down_revision: Union[str, Sequence[str], None] = "11ba81a9e43f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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


def downgrade() -> None:
    with op.batch_alter_table("venta") as batch_op:
        batch_op.alter_column(
            "fecha_venta",
            existing_type=sa.DATETIME(),
            nullable=True,
        )
