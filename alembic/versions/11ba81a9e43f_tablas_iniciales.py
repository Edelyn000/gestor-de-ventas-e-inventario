"""tablas_iniciales

Revision ID: 11ba81a9e43f
Revises:
Create Date: 2026-06-17 08:40:37.548811

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import engine_from_config
from sqlalchemy.engine.reflection import Inspector

from sistema_financiero.models.conexion import engine

revision: str = "11ba81a9e43f"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = Inspector.from_engine(engine)
    tables = inspector.get_table_names()
    if tables:
        return

    op.create_table(
        "productos",
        sa.Column("idproducto", sa.INTEGER(), nullable=False),
        sa.Column("nombre_producto", sa.VARCHAR(length=200), nullable=False),
        sa.Column("categoria", sa.VARCHAR(length=100), nullable=True),
        sa.Column("precio_compra", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("precio_venta_bs", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("precio_venta_usd", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("stock_actual", sa.INTEGER(), nullable=False),
        sa.Column("stock_minimo", sa.INTEGER(), nullable=False),
        sa.Column("unidad", sa.VARCHAR(length=20), nullable=False),
        sa.Column("fecha_ingreso", sa.DATETIME(), nullable=True),
        sa.PrimaryKeyConstraint("idproducto"),
    )
    op.create_index(op.f("ix_productos_nombre_producto"), "productos", ["nombre_producto"], unique=False)
    op.create_index(op.f("ix_productos_categoria"), "productos", ["categoria"], unique=False)

    op.create_table(
        "tasas_cambio",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("fecha", sa.DATE(), nullable=False),
        sa.Column("tasa_venta", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("tasa_compra", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("activa", sa.BOOLEAN(), nullable=False),
        sa.Column("fecha_registro", sa.DATETIME(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tasas_cambio_fecha"), "tasas_cambio", ["fecha"], unique=True)

    op.create_table(
        "usuarios",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("usuario", sa.VARCHAR(length=50), nullable=False),
        sa.Column("contrasena", sa.VARCHAR(length=255), nullable=False),
        sa.Column("nombre_completo", sa.VARCHAR(length=200), nullable=True),
        sa.Column("activo", sa.BOOLEAN(), nullable=False),
        sa.Column("fecha_creacion", sa.DATETIME(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_usuarios_usuario"), "usuarios", ["usuario"], unique=True)

    op.create_table(
        "reportes_diarios",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("fecha", sa.DATE(), nullable=False),
        sa.Column("total_ventas_bs", sa.NUMERIC(precision=12, scale=2), nullable=False),
        sa.Column("total_ventas_usd", sa.NUMERIC(precision=12, scale=2), nullable=False),
        sa.Column("cantidad_ventas", sa.INTEGER(), nullable=False),
        sa.Column("cantidad_productos_vendidos", sa.INTEGER(), nullable=False),
        sa.Column("productos_stock_bajo", sa.INTEGER(), nullable=False),
        sa.Column("productos_sin_stock", sa.INTEGER(), nullable=False),
        sa.Column("efectivo_bs", sa.NUMERIC(precision=12, scale=2), nullable=False),
        sa.Column("efectivo_usd", sa.NUMERIC(precision=12, scale=2), nullable=False),
        sa.Column("tarjeta", sa.NUMERIC(precision=12, scale=2), nullable=False),
        sa.Column("pago_movil", sa.NUMERIC(precision=12, scale=2), nullable=False),
        sa.Column("bio_pago", sa.NUMERIC(precision=12, scale=2), nullable=False),
        sa.Column("fecha_generacion", sa.DATETIME(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reportes_diarios_fecha"), "reportes_diarios", ["fecha"], unique=True)

    op.create_table(
        "ventas",
        sa.Column("idventa", sa.INTEGER(), nullable=False),
        sa.Column("numero_factura", sa.VARCHAR(length=50), nullable=True),
        sa.Column("fecha_venta", sa.DATETIME(), nullable=True),
        sa.Column("total_bs", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("total_usd", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("tasa_cambio", sa.NUMERIC(precision=10, scale=2), nullable=True),
        sa.Column("efectivo_bs", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("efectivo_usd", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("tarjeta", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("pago_movil", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("bio_pago", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("estado", sa.VARCHAR(length=20), nullable=False),
        sa.PrimaryKeyConstraint("idventa"),
        sa.UniqueConstraint("numero_factura"),
    )

    op.create_table(
        "venta_detalles",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("venta_id", sa.INTEGER(), nullable=False),
        sa.Column("producto_id", sa.INTEGER(), nullable=False),
        sa.Column("cantidad", sa.INTEGER(), nullable=False),
        sa.Column("precio_unitario_bs", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("subtotal_bs", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.idproducto"]),
        sa.ForeignKeyConstraint(["venta_id"], ["ventas.idventa"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "movimientos_inventario",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("producto_id", sa.INTEGER(), nullable=False),
        sa.Column("tipo", sa.VARCHAR(length=20), nullable=False),
        sa.Column("motivo", sa.VARCHAR(length=50), nullable=False),
        sa.Column("cantidad", sa.INTEGER(), nullable=False),
        sa.Column("stock_anterior", sa.INTEGER(), nullable=False),
        sa.Column("stock_nuevo", sa.INTEGER(), nullable=False),
        sa.Column("referencia_id", sa.INTEGER(), nullable=True),
        sa.Column("observaciones", sa.VARCHAR(length=255), nullable=True),
        sa.Column("fecha_movimiento", sa.DATETIME(), nullable=True),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.idproducto"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("movimientos_inventario")
    op.drop_table("venta_detalles")
    op.drop_table("ventas")
    op.drop_table("reportes_diarios")
    op.drop_index(op.f("ix_usuarios_usuario"), table_name="usuarios")
    op.drop_table("usuarios")
    op.drop_index(op.f("ix_tasas_cambio_fecha"), table_name="tasas_cambio")
    op.drop_table("tasas_cambio")
    op.drop_index(op.f("ix_productos_categoria"), table_name="productos")
    op.drop_index(op.f("ix_productos_nombre_producto"), table_name="productos")
    op.drop_table("productos")
