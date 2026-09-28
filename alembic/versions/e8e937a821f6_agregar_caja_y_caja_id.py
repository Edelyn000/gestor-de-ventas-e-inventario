"""agregar_caja_y_caja_id Crea la tabla caja y la columna caja_id en venta."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op
from sistema_financiero.models.conexion import engine

# revision identifiers, used by Alembic.
revision: str = "e8e937a821f6"
down_revision: str | Sequence[str] | None = "2ff54d5c1e57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Upgrade schema.
def upgrade() -> None:
    """Upgrade schema."""
    inspector = Inspector.from_engine(engine)
    tablas = inspector.get_table_names()

    if "caja" not in tablas:
        op.create_table(
            "caja",
            sa.Column("id", sa.INTEGER(), nullable=False),
            sa.Column("fecha_apertura", sa.DATETIME(), nullable=False),
            sa.Column("monto_apertura_bs", sa.NUMERIC(precision=12, scale=2), nullable=False),
            sa.Column("fecha_cierre", sa.DATETIME(), nullable=True),
            sa.Column("monto_cierre_bs", sa.NUMERIC(precision=12, scale=2), nullable=True),
            sa.Column("estado", sa.VARCHAR(length=20), nullable=False),
            sa.Column("usuario_id", sa.INTEGER(), nullable=False),
            sa.Column("total_ventas_bs", sa.NUMERIC(precision=12, scale=2), nullable=True),
            sa.Column("total_ventas_usd", sa.NUMERIC(precision=12, scale=2), nullable=True),
            sa.Column("cantidad_ventas", sa.INTEGER(), nullable=True),
            sa.Column("efectivo_bs", sa.NUMERIC(precision=12, scale=2), nullable=True),
            sa.Column("efectivo_usd", sa.NUMERIC(precision=12, scale=2), nullable=True),
            sa.Column("tarjeta", sa.NUMERIC(precision=12, scale=2), nullable=True),
            sa.Column("pago_movil", sa.NUMERIC(precision=12, scale=2), nullable=True),
            sa.Column("bio_pago", sa.NUMERIC(precision=12, scale=2), nullable=True),
            sa.Column("sobrante_faltante_bs", sa.NUMERIC(precision=12, scale=2), nullable=True),
            sa.Column("observaciones", sa.VARCHAR(length=500), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        )
        op.create_index(op.f("ix_caja_estado"), "caja", ["estado"], unique=False)

    if "venta" in tablas:
        columnas_venta = {columna["name"] for columna in inspector.get_columns("venta")}
        if "caja_id" not in columnas_venta:
            op.add_column(
                "venta",
                sa.Column("caja_id", sa.INTEGER(), nullable=True),
            )


# Downgrade schema.
def downgrade() -> None:
    """Downgrade schema."""
    inspector = Inspector.from_engine(engine)
    tablas = inspector.get_table_names()

    if "venta" in tablas:
        columnas_venta = {columna["name"] for columna in inspector.get_columns("venta")}
        if "caja_id" in columnas_venta:
            with op.batch_alter_table("venta") as batch_op:
                batch_op.drop_column("caja_id")

    if "caja" in tablas:
        op.drop_index(op.f("ix_caja_estado"), table_name="caja")
        op.drop_table("caja")
