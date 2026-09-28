"""reporte_unidades_peso

Rediseno del conteo del reporte diario: la cantidad vendida se SEPARA
en unidades (piezas enteras) y peso en kg (PESO/GRAMOS), en vez de un
unico campo entero que TRUNCAVA las fracciones (0.500 kg de harina se
reportaba como 0).

- `ReporteDiario.unidades_vendidas` (INTEGER, default 0): piezas
  enteras vendidas en el dia.
- `ReporteDiario.peso_vendido_kg` (NUMERIC(12,3), default 0.000):
  kilogramos vendidos (0.100 = 100 g, escala interna del POS).
- Se elimina `cantidad_productos_vendidos`.
- Nueva tabla `reporte_venta_detalle`: una fila por producto vendido
  en el dia (snapshot: nombre + tipo_venta + cantidad agrupada). La FK
  a `reportediario.id` es CASCADE: al regenerar/borrar el reporte se
  borran sus lineas junto con el padre.

Idempotente con Inspector (patron de las migraciones previas). El
backfill copia el valor viejo (piezas contadas antes) a
unidades_vendidas; el peso historico parte de 0.000.

Nota: el backup pre-migracion de la BD real esta en
`%TEMP%\\opencode\\database.db.bak_reporte_unidades`.

Revision ID: f1e2d3c4b5a6
Revises: e0f9a8b7c6d5
Create Date: 2026-09-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op
from sistema_financiero.models.conexion import engine

# revision identifiers, used by Alembic.
revision: str = "f1e2d3c4b5a6"
down_revision: str | Sequence[str] | None = "e0f9a8b7c6d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLA = "reportediario"
_DETALLE = "reporte_venta_detalle"
_INDICE_DETALLE = "ix_reporte_venta_detalle_reporte_id"


# Separa unidades de peso, backfillea y crea la tabla de detalle.
def upgrade() -> None:
    """Separa unidades de peso, backfillea y crea la tabla de detalle."""
    inspector = Inspector.from_engine(engine)
    columnas = [c["name"] for c in inspector.get_columns(_TABLA)]

    # 1) Nuevas columnas (con server_default para las filas existentes).
    with op.batch_alter_table(_TABLA) as batch:
        if "unidades_vendidas" not in columnas:
            batch.add_column(
                sa.Column(
                    "unidades_vendidas",
                    sa.Integer(),
                    nullable=False,
                    server_default=sa.text("0"),
                ),
            )
        if "peso_vendido_kg" not in columnas:
            batch.add_column(
                sa.Column(
                    "peso_vendido_kg",
                    sa.Numeric(12, 3),
                    nullable=False,
                    server_default=sa.text("0.000"),
                ),
            )

    # 2) Backfill: el conteo viejo (piezas) migra a unidades_vendidas.
    op.execute(
        sa.text(
            "UPDATE reportediario SET unidades_vendidas = COALESCE(cantidad_productos_vendidos, 0)",
        ),
    )

    # 3) Eliminar la columna legada (SQLite: batch).
    inspector = Inspector.from_engine(engine)
    if "cantidad_productos_vendidos" in [c["name"] for c in inspector.get_columns(_TABLA)]:
        with op.batch_alter_table(_TABLA) as batch:
            batch.drop_column("cantidad_productos_vendidos")

    # 4) Tabla de detalle (una fila por producto vendido).
    if not inspector.has_table(_DETALLE):
        op.create_table(
            _DETALLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "reporte_id",
                sa.Integer(),
                sa.ForeignKey("reportediario.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("producto_id", sa.Integer(), nullable=True),
            sa.Column("nombre_producto", sa.VARCHAR(length=100), nullable=False),
            sa.Column(
                "tipo_venta",
                sa.VARCHAR(length=10),
                nullable=False,
                server_default=sa.text("'UNIDAD'"),
            ),
            sa.Column("cantidad", sa.Numeric(10, 3), nullable=False),
        )
        op.create_index(_INDICE_DETALLE, _DETALLE, ["reporte_id"])


# Revierte: restaura cantidad_productos_vendidos y elimina la tabla.
def downgrade() -> None:
    """Revierte: restaura cantidad_productos_vendidos y elimina la tabla."""
    inspector = Inspector.from_engine(engine)

    # 1) Eliminar la tabla de detalle (arrastra su indice).
    if inspector.has_table(_DETALLE):
        op.drop_table(_DETALLE)

    columnas = [c["name"] for c in inspector.get_columns(_TABLA)]

    # 2) Restaurar la columna legada y backfillear (solo piezas;
    with op.batch_alter_table(_TABLA) as batch:
        if "cantidad_productos_vendidos" not in columnas:
            batch.add_column(
                sa.Column(
                    "cantidad_productos_vendidos",
                    sa.Integer(),
                    nullable=False,
                    server_default=sa.text("0"),
                ),
            )
    op.execute(
        sa.text(
            "UPDATE reportediario SET cantidad_productos_vendidos = unidades_vendidas",
        ),
    )

    # 3) Eliminar las columnas nuevas.
    inspector = Inspector.from_engine(engine)
    columnas = [c["name"] for c in inspector.get_columns(_TABLA)]
    with op.batch_alter_table(_TABLA) as batch:
        if "unidades_vendidas" in columnas:
            batch.drop_column("unidades_vendidas")
        if "peso_vendido_kg" in columnas:
            batch.drop_column("peso_vendido_kg")
