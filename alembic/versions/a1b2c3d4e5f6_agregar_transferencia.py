"""agregar_transferencia Agrega la columna transferencia a venta, caja y reportediario."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op
from sistema_financiero.models.conexion import engine

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "e8e937a821f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# True si la columna ya existe (BD creada por create_db_and_tables).
def _columna_existe(tabla: str, columna: str) -> bool:
    """True si la columna ya existe (BD creada por create_db_and_tables)."""
    inspector = Inspector.from_engine(engine)
    if tabla not in inspector.get_table_names():
        return False
    nombres = {c["name"] for c in inspector.get_columns(tabla)}
    return columna in nombres


# Agrega la columna transferencia a las tres tablas.
def upgrade() -> None:
    """Agrega la columna transferencia a las tres tablas."""
    # venta usa Numeric(10,2) en sus metodos de pago; caja y reportes usan (12,2).
    for tabla, nullable, precision in (
        ("venta", False, 10),
        ("caja", True, 12),
        ("reportediario", False, 12),
    ):
        if not _columna_existe(tabla, "transferencia"):
            op.add_column(
                tabla,
                sa.Column(
                    "transferencia",
                    sa.NUMERIC(precision=precision, scale=2),
                    nullable=nullable,
                    server_default=sa.text("0.00") if not nullable else None,
                ),
            )


# Elimina la columna transferencia de las tres tablas.
def downgrade() -> None:
    """Elimina la columna transferencia de las tres tablas."""
    for tabla in ("reportediario", "caja", "venta"):
        if _columna_existe(tabla, "transferencia"):
            with op.batch_alter_table(tabla) as batch_op:
                batch_op.drop_column("transferencia")
