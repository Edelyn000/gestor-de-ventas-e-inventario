"""rentabilidad_ventas

Agrega costo, utilidad bruta y margen de ganancia al reporte diario:

- `producto.precio_compra_usd` (NUMERIC(10,2), default 0): costo de compra
  en dolares, para poder medir rentabilidad en las dos monedas.
- `ventadetalle.precio_costo_unitario` / `..._usd` (NUMERIC(10,2),
  NULL): SNAPSHOT del costo en el instante de la venta. En las lineas
  anteriores el Bs se backfillea aproximado con el costo de compra
  vigente; el USD queda NULL porque de la epoca no se conoce.
- `reportediario`: costo_ventas_bs/usd, utilidad_bruta_bs/usd,
  margen_ganancia (NULL si no hubo ingresos) y
  productos_costo_no_confiable.
- `reporteventadetalle` (la tabla real, nombre derivado por SQLModel):
  ingreso_total_bs, costo_total_bs y margen_ganancia por producto.

Idempotente con Inspector (patron de las migraciones previas).

Backfill (deliberadamente PARCIAL):
- `ventadetalle.precio_costo_unitario` se rellena con el
  `producto.precio_compra` de HOY (aproximado: el costo real de aquella
  venta no se conoce). Es lo que hace que los reportes FUTUROS tengan
  cifras de costo desde el primer dia.
- `ventadetalle.precio_costo_unitario_usd` NO se rellena: el USD de
  compra de la epoca no se conoce y copiar el de hoy seria inventar.
- La rentabilidad de los `reportediario` / `reporteventadetalle`
  historicos SOLO se calcula si el reporte PROBADAmente cuadra con sus
  ventas: su `total_ventas_bs` tiene que ser exactamente la suma de las
  ventas COMPLETADAS del dia local. Asi se rellenan 2026-09-27 (90.900,30)
  y 2026-09-28 (122.723,83), que cuadran al centimo, y se dejan en
  "no calculada" (costo 0.00, margen NULL) el 2026-09-24 (declara 1 venta
  por 21.793,66 pero ese dia VET tiene 5), el 2026-09-11 y el 2026-09-22
  (declaran 0 y existen ventas). Calcular el COGS sobre una base que no
  cuadra produciria perdidas y margenes inventados (-217% el 24). Se
  recalcula con datos correctos al regenerar el reporte del dia.
- `productos_costo_no_confiable` si se rellena: es un dato real de los
  productos de HOY, no una cuenta historica.

Nota: la tabla real del detalle es `reporteventadetalle` (nombre que
SQLModel deriva de la clase `ReporteVentaDetalle`), no
`reporte_venta_detalle`: la migracion f1e2d3c4b5a6 creo esa segunda,
vacia y sin usar. Esta migracion no la toca.

Nota: el backup pre-migracion de la BD real esta en
`%TEMP%/database.db.bak_rentabilidad`.

Revision ID: a2b3c4d5e6f7
Revises: f1e2d3c4b5a6
Create Date: 2026-09-29 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op
from sistema_financiero.models.conexion import engine

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "f1e2d3c4b5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRODUCTO = "producto"
_DETALLE_VENTA = "ventadetalle"
_REPORTE = "reportediario"
_DETALLE_REPORTE = "reporteventadetalle"

# Columnas de rentabilidad del reporte diario: (nombre, tipo, default).
_COLUMNAS_REPORTE = (
    ("costo_ventas_bs", "NUMERIC(12,2)", "0.00"),
    ("costo_ventas_usd", "NUMERIC(12,2)", "0.00"),
    ("utilidad_bruta_bs", "NUMERIC(12,2)", "0.00"),
    ("utilidad_bruta_usd", "NUMERIC(12,2)", "0.00"),
    ("margen_ganancia", "NUMERIC(7,2)", None),
    ("productos_costo_no_confiable", "INTEGER", "0"),
)

# Columnas de rentabilidad del detalle por producto.
_COLUMNAS_DETALLE_REPORTE = (
    ("ingreso_total_bs", "NUMERIC(12,2)", "0.00"),
    ("costo_total_bs", "NUMERIC(12,2)", "0.00"),
    ("margen_ganancia", "NUMERIC(7,2)", None),
)


# Convierte el tipo textual de la constante a un tipo de SQLAlchemy.
def _tipo(sql: str) -> sa.types.TypeEngine[Any]:
    """Convierte 'NUMERIC(12,2)' / 'INTEGER' al tipo de SQLAlchemy."""
    if sql == "INTEGER":
        return sa.Integer()
    precision, escala = sql.removeprefix("NUMERIC(").removesuffix(")").split(",")
    return sa.Numeric(int(precision), int(escala))


# Agrega las columnas nuevas de rentabilidad y backfillea los snapshots.
def upgrade() -> None:
    """Agrega las columnas de rentabilidad y backfillea los snapshots."""
    inspector = Inspector.from_engine(engine)

    # 1) producto.precio_compra_usd.
    if "precio_compra_usd" not in [c["name"] for c in inspector.get_columns(_PRODUCTO)]:
        with op.batch_alter_table(_PRODUCTO) as batch:
            batch.add_column(
                sa.Column(
                    "precio_compra_usd",
                    sa.Numeric(10, 2),
                    nullable=False,
                    server_default=sa.text("0.00"),
                ),
            )

    # 2) Snapshot del costo en cada linea de venta (nullable a proposito:
    #    las lineas legacy no tienen costo historico conocido).
    columnas_detalle = [c["name"] for c in inspector.get_columns(_DETALLE_VENTA)]
    with op.batch_alter_table(_DETALLE_VENTA) as batch:
        if "precio_costo_unitario" not in columnas_detalle:
            batch.add_column(
                sa.Column("precio_costo_unitario", sa.Numeric(10, 2), nullable=True),
            )
        if "precio_costo_unitario_usd" not in columnas_detalle:
            batch.add_column(
                sa.Column("precio_costo_unitario_usd", sa.Numeric(10, 2), nullable=True)
            )

    # 3) Rentabilidad del reporte diario.
    inspector = Inspector.from_engine(engine)
    columnas_reporte = [c["name"] for c in inspector.get_columns(_REPORTE)]
    with op.batch_alter_table(_REPORTE) as batch:
        for nombre, tipo, default in _COLUMNAS_REPORTE:
            if nombre in columnas_reporte:
                continue
            batch.add_column(
                sa.Column(
                    nombre,
                    _tipo(tipo),
                    nullable=default is None,
                    server_default=None if default is None else sa.text(default),
                ),
            )

    # 4) Rentabilidad por producto en el detalle del reporte. La tabla solo
    #    existe si create_db_and_tables() ya corrio (SQLModel la deriva como
    #    `reporteventadetalle`); si no, no hay nada que ampliar.
    inspector = Inspector.from_engine(engine)
    if inspector.has_table(_DETALLE_REPORTE):
        columnas_detalle_reporte = [c["name"] for c in inspector.get_columns(_DETALLE_REPORTE)]
        with op.batch_alter_table(_DETALLE_REPORTE) as batch:
            for nombre, tipo, default in _COLUMNAS_DETALLE_REPORTE:
                if nombre in columnas_detalle_reporte:
                    continue
                batch.add_column(
                    sa.Column(
                        nombre,
                        _tipo(tipo),
                        nullable=default is None,
                        server_default=None if default is None else sa.text(default),
                    ),
                )

    _backfill()


# Rellena los snapshots aproximados y marca los costos no confiables.
def _backfill() -> None:
    """Backfillea snapshots en Bs y la rentabilidad de los reportes alineados.

    El costo en USD nunca se backfillea (el USD de compra de la epoca no se
    conoce). La rentabilidad de un reporte SOLO se calcula si su
    total_ventas_bs coincide al centimo con la suma de las ventas COMPLETADAS
    de ese dia local; si no, queda costo 0.00 + margen NULL = "no calculada".
    """
    # Snapshot aproximado en Bs: el costo de compra vigente del producto.
    op.execute(
        sa.text(
            "UPDATE ventadetalle SET precio_costo_unitario = ("
            "SELECT p.precio_compra FROM producto p "
            "WHERE p.idproducto = ventadetalle.producto_id) "
            "WHERE precio_costo_unitario IS NULL",
        ),
    )
    # El costo en USD NO se backfillea: el USD de compra de la epoca no se
    # conoce y copiar el de hoy seria inventar el dato historico.

    # Productos cuyo costo actual no permite un margen creible. Misma regla
    # que core.rentabilidad.costo_no_confiable: costo <= 0, costo >= precio
    # de venta, o costo por debajo del 1% del precio de venta.
    op.execute(
        sa.text(
            "UPDATE reportediario SET productos_costo_no_confiable = ("
            "  SELECT COUNT(*) FROM producto p WHERE p.precio_compra <= 0"
            "    OR (p.precio_venta_bs > 0 AND p.precio_compra >= p.precio_venta_bs)"
            "    OR (p.precio_venta_bs > 0 AND p.precio_compra < p.precio_venta_bs * 0.01)"
            ")",
        ),
    )

    # Ventanas del dia local (VET = UTC-4) en UTC, igual que rango_dia_utc():
    # el dia D va de las 04:00 UTC del dia D a las 04:00 UTC del D+1. Solo
    # ventas COMPLETADA, igual que ReporteService.generar_reporte.
    #
    # La rentabilidad historica SOLO se calcula si el reporte PROBADAmente
    # cuadra con sus ventas: la suma del dia tiene que ser exactamente
    # total_ventas_bs. Cuando no cuadra (2026-09-24 declara 1 venta por
    # 21.793,66 y ese dia VET hay 5; 2026-09-11 y 2026-09-22 declaran 0 y
    # existen ventas) se deja costo 0.00 + margen NULL = "no calculada".
    # Asi se rellenan 2026-09-27 y 2026-09-28, que cuadran al centimo.
    el_dia = (
        "  v.estado = 'COMPLETADA' "
        "  AND datetime(v.fecha_venta) >= datetime(r.fecha, '+4 hours') "
        "  AND datetime(v.fecha_venta) < datetime(date(r.fecha, '+1 day'), '+4 hours')"
    )
    cuadra = (
        "  ROUND(COALESCE((SELECT SUM(v2.total_bs) FROM venta v2 "
        "WHERE v2.estado = 'COMPLETADA' "
        "AND datetime(v2.fecha_venta) >= datetime(r.fecha, '+4 hours') "
        "AND datetime(v2.fecha_venta) < datetime(date(r.fecha, '+1 day'), '+4 hours')"
        "), 0), 2) = ROUND(COALESCE(r.total_ventas_bs, 0), 2)"
    )

    # Costo del reporte: suma de (snapshot x cantidad) de las lineas del dia.
    op.execute(
        sa.text(
            "UPDATE reportediario AS r SET costo_ventas_bs = COALESCE(("
            "  SELECT ROUND(SUM(d.precio_costo_unitario * d.cantidad), 2)"
            "  FROM ventadetalle d JOIN venta v ON v.idventa = d.venta_id"
            f" WHERE {el_dia}"
            "), 0.00) "
            f"WHERE {cuadra}",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE reportediario AS r SET utilidad_bruta_bs = "
            "ROUND(COALESCE(total_ventas_bs, 0) - costo_ventas_bs, 2) "
            f"WHERE {cuadra}",
        ),
    )
    # El margen es NULL cuando no hubo ingresos (no se divide entre cero) y
    # tambien cuando el reporte no cuadra con sus ventas (no calculada).
    op.execute(
        sa.text(
            "UPDATE reportediario AS r SET margen_ganancia = CASE "
            "WHEN COALESCE(total_ventas_bs, 0) > 0 "
            "THEN ROUND(utilidad_bruta_bs * 100.0 / total_ventas_bs, 2) END "
            f"WHERE {cuadra}",
        ),
    )

    # Detalle por producto: ingreso y costo de las lineas de ESE producto en
    # ESE dia, solo cuando el reporte del dia cuadra con sus ventas. Todo se
    # correlaciona contra reporteventadetalle.reporte_id: el alias "r" del
    # UPDATE no existe dentro del subquery del SET.
    fecha_reporte = (
        "(SELECT rr.fecha FROM reportediario rr  WHERE rr.id = reporteventadetalle.reporte_id)"
    )
    el_dia_detalle = (
        "  v.estado = 'COMPLETADA' "
        f"  AND datetime(v.fecha_venta) >= datetime({fecha_reporte}, '+4 hours') "
        f"  AND datetime(v.fecha_venta) < datetime(date({fecha_reporte}, '+1 day'), '+4 hours')"
        "\n  AND (d.producto_id = reporteventadetalle.producto_id"
        "\n       OR (d.producto_id IS NULL"
        " AND reporteventadetalle.producto_id IS NULL))"
    )
    cuadra_reporte = (
        "  reporteventadetalle.reporte_id IN ("
        "    SELECT rr.id FROM reportediario rr"
        "    WHERE ROUND(COALESCE(("
        "      SELECT SUM(v2.total_bs) FROM venta v2"
        "      WHERE v2.estado = 'COMPLETADA'"
        "        AND datetime(v2.fecha_venta) >= datetime(rr.fecha, '+4 hours')"
        "        AND datetime(v2.fecha_venta) < datetime(date(rr.fecha, '+1 day'), '+4 hours')"
        "    ), 0), 2) = ROUND(COALESCE(rr.total_ventas_bs, 0), 2)"
        "  )"
    )
    op.execute(
        sa.text(
            "UPDATE reporteventadetalle SET ingreso_total_bs = COALESCE(("
            "  SELECT ROUND(SUM(d.subtotal_bs), 2)"
            "  FROM ventadetalle d JOIN venta v ON v.idventa = d.venta_id"
            f" WHERE {el_dia_detalle}"
            "), 0.00) "
            f"WHERE {cuadra_reporte}",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE reporteventadetalle SET costo_total_bs = COALESCE(("
            "  SELECT ROUND(SUM(COALESCE(d.precio_costo_unitario, 0) * d.cantidad), 2)"
            "  FROM ventadetalle d JOIN venta v ON v.idventa = d.venta_id"
            f" WHERE {el_dia_detalle}"
            "), 0.00) "
            f"WHERE {cuadra_reporte}",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE reporteventadetalle SET margen_ganancia = CASE "
            "WHEN ingreso_total_bs > 0 "
            "THEN ROUND((ingreso_total_bs - costo_total_bs) * 100.0 / ingreso_total_bs, 2) END "
            f"WHERE {cuadra_reporte}",
        ),
    )


# Revierte: elimina las columnas de rentabilidad y sus datos.
def downgrade() -> None:
    """Revierte: elimina las columnas de rentabilidad y sus datos."""
    inspector = Inspector.from_engine(engine)
    for tabla, columnas in (
        (_DETALLE_REPORTE, _COLUMNAS_DETALLE_REPORTE),
        (_REPORTE, _COLUMNAS_REPORTE),
    ):
        if not inspector.has_table(tabla):
            continue
        existentes = [c["name"] for c in inspector.get_columns(tabla)]
        with op.batch_alter_table(tabla) as batch:
            for nombre, _tipo_sql, _default in columnas:
                if nombre in existentes:
                    batch.drop_column(nombre)

    existentes_detalle = [
        c["name"] for c in Inspector.from_engine(engine).get_columns(_DETALLE_VENTA)
    ]
    with op.batch_alter_table(_DETALLE_VENTA) as batch:
        for nombre in ("precio_costo_unitario", "precio_costo_unitario_usd"):
            if nombre in existentes_detalle:
                batch.drop_column(nombre)

    existentes_producto = [c["name"] for c in Inspector.from_engine(engine).get_columns(_PRODUCTO)]
    with op.batch_alter_table(_PRODUCTO) as batch:
        if "precio_compra_usd" in existentes_producto:
            batch.drop_column("precio_compra_usd")
