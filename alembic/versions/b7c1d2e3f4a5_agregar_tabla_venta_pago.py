"""agregar_tabla_venta_pago

Crea la tabla venta_pago: desglose de los pagos de una venta
(multi-pago). Cada fila es UN pago con su metodo, moneda, monto
aplicado, equivalente en Bs. y referencia.

La tabla se crea con guards de Inspector para ser idempotente: la
BD de la app se crea con create_db_and_tables(), por lo que la tabla
puede existir ya antes de aplicar la migracion.

Revision ID: b7c1d2e3f4a5
Revises: a1b2c3d4e5f6
Create Date: 2026-09-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op
from sistema_financiero.models.conexion import engine

# revision identifiers, used by Alembic.
revision: str = "b7c1d2e3f4a5"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Crea la tabla venta_pago (idempotente).
def upgrade() -> None:
    """Crea la tabla venta_pago (idempotente)."""
    inspector = Inspector.from_engine(engine)
    if "venta_pago" in inspector.get_table_names():
        return

    op.create_table(
        "venta_pago",
        sa.Column("idpago", sa.INTEGER(), nullable=False),
        sa.Column("venta_id", sa.INTEGER(), nullable=False),
        sa.Column("metodo", sa.VARCHAR(length=20), nullable=False),
        sa.Column("moneda", sa.VARCHAR(length=5), nullable=False),
        sa.Column("monto", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("monto_bs", sa.NUMERIC(precision=12, scale=2), nullable=False),
        sa.Column("tasa_cambio", sa.NUMERIC(precision=10, scale=2), nullable=True),
        sa.Column("referencia", sa.VARCHAR(length=100), nullable=True),
        sa.Column("fecha_pago", sa.DATETIME(), nullable=False),
        sa.PrimaryKeyConstraint("idpago"),
        # Al anular/eliminar una venta, sus pagos se van con ella.
        sa.ForeignKeyConstraint(["venta_id"], ["venta.idventa"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_venta_pago_venta_id"), "venta_pago", ["venta_id"], unique=False)
    op.create_index(op.f("ix_venta_pago_metodo"), "venta_pago", ["metodo"], unique=False)


# Elimina la tabla venta_pago.
def downgrade() -> None:
    """Elimina la tabla venta_pago."""
    inspector = Inspector.from_engine(engine)
    if "venta_pago" not in inspector.get_table_names():
        return

    op.drop_index(op.f("ix_venta_pago_metodo"), table_name="venta_pago")
    op.drop_index(op.f("ix_venta_pago_venta_id"), table_name="venta_pago")
    op.drop_table("venta_pago")
