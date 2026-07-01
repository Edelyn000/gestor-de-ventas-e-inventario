from datetime import date, datetime
from decimal import Decimal

from sqlmodel import Field, Relationship, SQLModel

from sistema_financiero.utils.fecha import ahora


# ============================================================
# MODELO: Producto
# Representa un artículo del inventario del abasto.
# Almacena precios de compra/venta en VES y USD, ademas del
# stock actual y un minimo para alertas de reabastecimiento.
# Se relaciona con MovimientoInventario y VentaDetalle.
# ============================================================
class Producto(SQLModel, table=True):
    idproducto: int | None = Field(default=None, primary_key=True)
    nombre_producto: str = Field(max_length=200, index=True)
    categoria: str | None = Field(default=None, max_length=100, index=True)
    precio_compra: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    precio_venta_bs: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    precio_venta_usd: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    stock_actual: int = Field(default=0)
    stock_minimo: int = Field(default=5)
    unidad: str = Field(default="UNIDAD", max_length=20)
    fecha_ingreso: datetime | None = Field(default=None)

    movimientos: list[MovimientoInventario] = Relationship(back_populates="producto")
    detalles_venta: list[VentaDetalle] = Relationship(back_populates="producto")


# ============================================================
# MODELO: Venta
# Registra una venta completa con su numero de factura,
# totales en VES/USD, tasa de cambio aplicada, y los montos
# recibidos por cada metodo de pago (efectivo, tarjeta,
# pago movil, bio-pago). El estado puede ser COMPLETADA o
# ANULADA.
# ============================================================
class Venta(SQLModel, table=True):
    idventa: int | None = Field(default=None, primary_key=True)
    numero_factura: str | None = Field(default=None, max_length=50, unique=True)
    fecha_venta: datetime = Field(default=ahora)
    total_bs: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    total_usd: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    tasa_cambio: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    efectivo_bs: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    efectivo_usd: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    tarjeta: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    pago_movil: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    bio_pago: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    estado: str = Field(default="COMPLETADA", max_length=20)

    detalles: list[VentaDetalle] = Relationship(back_populates="venta")


# ============================================================
# MODELO: VentaDetalle
# Linea individual de una venta. Asocia un producto con la
# cantidad comprada, su precio unitario en VES y el subtotal.
# Sirve como tabla intermedia entre Venta y Producto (N:M).
# ============================================================
class VentaDetalle(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    venta_id: int = Field(foreign_key="venta.idventa")
    producto_id: int = Field(foreign_key="producto.idproducto")
    cantidad: int = Field(default=1)
    precio_unitario_bs: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    subtotal_bs: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)

    venta: Venta | None = Relationship(back_populates="detalles")
    producto: Producto | None = Relationship(back_populates="detalles_venta")


# ============================================================
# MODELO: MovimientoInventario
# Auditoria de stock: registra cada cambio de inventario con
# el tipo (ENTRADA/SALIDA/AJUSTE), motivo, cantidad, y los
# valores de stock anterior/nuevo para trazabilidad.
# ============================================================
class MovimientoInventario(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    producto_id: int = Field(foreign_key="producto.idproducto")
    tipo: str = Field(max_length=20)  # ENTRADA, SALIDA, AJUSTE
    motivo: str = Field(max_length=50)  # COMPRA, VENTA, DEVOLUCION, etc.
    cantidad: int = Field(default=0)
    stock_anterior: int = Field(default=0)
    stock_nuevo: int = Field(default=0)
    referencia_id: int | None = Field(default=None)  # ID de la Venta o Compra asociada
    observaciones: str | None = Field(default=None, max_length=255)
    fecha_movimiento: datetime | None = Field(default=None)

    producto: Producto | None = Relationship(back_populates="movimientos")


# ============================================================
# MODELO: TasaCambio
# Registro diario de la tasa de cambio del BCV (VES/USD).
# Solo una tasa puede estar activa por dia. Se usa al
# momento de registrar ventas para la conversion de moneda.
# ============================================================
class TasaCambio(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    fecha: date = Field(index=True, unique=True)
    tasa_venta: Decimal = Field(max_digits=10, decimal_places=2)
    tasa_compra: Decimal = Field(max_digits=10, decimal_places=2)
    activa: bool = Field(default=True)
    fecha_registro: datetime | None = Field(default=None)


# ============================================================
# MODELO: Usuario
# Representa un usuario del sistema con credenciales de
# acceso. La contrasena se almacena hasheada con bcrypt
# (NUNCA en texto plano). Solo los usuarios activos pueden
# iniciar sesion.
# ============================================================
class Usuario(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    usuario: str = Field(max_length=50, unique=True, index=True)
    contrasena: str = Field(max_length=255)
    nombre_completo: str | None = Field(default=None, max_length=200)
    activo: bool = Field(default=True)
    fecha_creacion: datetime | None = Field(default=None)


# ============================================================
# MODELO: ReporteDiario
# Cierre del dia: consolida todas las ventas del dia con
# totales por metodo de pago, cantidad de productos
# vendidos, y alertas de stock bajo/sin stock.
# Se genera automaticamente al final del dia.
# ============================================================
class ReporteDiario(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    fecha: date = Field(index=True, unique=True)
    total_ventas_bs: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    total_ventas_usd: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    cantidad_ventas: int = Field(default=0)
    cantidad_productos_vendidos: int = Field(default=0)
    productos_stock_bajo: int = Field(default=0)
    productos_sin_stock: int = Field(default=0)
    efectivo_bs: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    efectivo_usd: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    tarjeta: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    pago_movil: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    bio_pago: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    fecha_generacion: datetime | None = Field(default=None)
