from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlmodel import Field, Relationship

from sistema_financiero.db.base import Base
from sistema_financiero.utils import TIPO_VENTA_UNIDAD
from sistema_financiero.utils.fecha import ahora


# ============================================================
# MODELO: Producto
# Representa un artículo del inventario del abasto.
# Almacena precios de compra/venta en VES y USD, ademas del
# stock actual y un minimo para alertas de reabastecimiento.
# Se relaciona con MovimientoInventario y VentaDetalle.
#
# tipo_venta: UNIDAD (piezas), PESO (kg), GRAMOS (gramos).
#   UNIDAD → stock entero, cantidad entera en ventas.
#   PESO   → stock en kg (decimal), cantidad en kg en ventas.
#   GRAMOS → stock en kg (decimal), cantidad en gramos.
# ============================================================
class Producto(Base, table=True):  # type: ignore[call-arg,misc]
    idproducto: int | None = Field(default=None, primary_key=True)
    nombre_producto: str = Field(max_length=200, index=True)
    categoria: str | None = Field(default=None, max_length=100, index=True)
    tipo_venta: str = Field(default=TIPO_VENTA_UNIDAD, max_length=10)
    precio_compra: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    precio_venta_bs: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    precio_venta_usd: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    stock_actual: Decimal = Field(
        default=Decimal("0.000"),
        max_digits=10,
        decimal_places=3,
    )
    stock_minimo: Decimal = Field(
        default=Decimal("5.000"),
        max_digits=10,
        decimal_places=3,
    )
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
# Se asocia opcionalmente a una caja abierta.
# ============================================================
class Venta(Base, table=True, __tablename__="venta", __table_args__={"extend_existing": True}):  # type: ignore[call-arg,misc]
    idventa: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True),
    )
    numero_factura: str | None = Field(default=None, max_length=50, unique=True)
    fecha_venta: datetime = Field(
        default_factory=ahora,
        sa_column=Column(DateTime, nullable=False, default=ahora),
    )
    total_bs: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    total_usd: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    tasa_cambio: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    efectivo_bs: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    efectivo_usd: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    tarjeta: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    pago_movil: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    bio_pago: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    estado: str = Field(
        default="COMPLETADA",
        sa_column=Column(String(20), nullable=False, default="COMPLETADA"),
    )
    caja_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("caja.id"), nullable=True),
    )  # FK a la caja abierta (opcional)

    detalles: list[VentaDetalle] = Relationship(back_populates="venta")


# ============================================================
# MODELO: VentaDetalle
# Linea individual de una venta. Asocia un producto con la
# cantidad comprada, su precio unitario en VES y el subtotal.
# Sirve como tabla intermedia entre Venta y Producto (N:M).
# ============================================================
class VentaDetalle(Base, table=True):  # type: ignore[call-arg,misc]
    id: int | None = Field(default=None, primary_key=True)
    venta_id: int = Field(
        sa_column=Column(ForeignKey("venta.idventa", ondelete="CASCADE")),
    )
    producto_id: int = Field(
        sa_column=Column(ForeignKey("producto.idproducto", ondelete="CASCADE")),
    )
    cantidad: Decimal = Field(default=Decimal("1.000"), max_digits=10, decimal_places=3)
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
class MovimientoInventario(Base, table=True):  # type: ignore[call-arg,misc]
    id: int | None = Field(default=None, primary_key=True)
    producto_id: int = Field(
        sa_column=Column(ForeignKey("producto.idproducto", ondelete="CASCADE")),
    )
    tipo: str = Field(max_length=20)  # ENTRADA, SALIDA, AJUSTE
    motivo: str = Field(max_length=50)  # COMPRA, VENTA, DEVOLUCION, etc.
    cantidad: Decimal = Field(default=Decimal("0.000"), max_digits=10, decimal_places=3)
    stock_anterior: Decimal = Field(default=Decimal("0.000"), max_digits=10, decimal_places=3)
    stock_nuevo: Decimal = Field(default=Decimal("0.000"), max_digits=10, decimal_places=3)
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
class TasaCambio(Base, table=True):  # type: ignore[call-arg,misc]
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
class Usuario(Base, table=True):  # type: ignore[call-arg,misc]
    id: int | None = Field(default=None, primary_key=True)
    usuario: str = Field(max_length=50, unique=True, index=True)
    contrasena: str = Field(max_length=255)
    nombre_completo: str | None = Field(default=None, max_length=200)
    rol: str = Field(default="VENDEDOR", max_length=20)
    activo: bool = Field(default=True)
    fecha_creacion: datetime | None = Field(default=None)


# ============================================================
# MODELO: ReporteDiario
# Cierre del dia: consolida todas las ventas del dia con
# totales por metodo de pago, cantidad de productos
# vendidos, y alertas de stock bajo/sin stock.
# Se genera automaticamente al final del dia.
# ============================================================
class ReporteDiario(Base, table=True):  # type: ignore[call-arg,misc]
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


# ============================================================
# MODELO: Caja
# Registro de apertura y cierre de caja.
# Almacena el monto inicial, el conteo fisico al cierre,
# sobrantes/faltantes y el estado (ABIERTA/CERRADA).
# Una sola caja por momento de trabajo.
# ============================================================
class Caja(Base, table=True, __tablename__="caja"):  # type: ignore[call-arg,misc]
    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True),
    )
    fecha_apertura: datetime = Field(
        default_factory=ahora,
        sa_column=Column(DateTime, nullable=False, default=ahora),
    )
    monto_apertura_bs: Decimal = Field(
        default=Decimal("0.00"), max_digits=12, decimal_places=2
    )  # Siempre en bolívares
    fecha_cierre: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime, nullable=True),
    )
    monto_cierre_bs: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )  # Total en bolívares al cerrar
    estado: str = Field(
        default="ABIERTA",
        sa_column=Column(String(20), nullable=False, default="ABIERTA", index=True),
    )
    usuario_id: int = Field(
        sa_column=Column(Integer, ForeignKey("usuario.id"), nullable=False),
    )
    total_ventas_bs: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )  # Total ventas del turno en Bs.
    total_ventas_usd: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )  # Total ventas del turno en USD
    cantidad_ventas: int | None = Field(default=None)  # Cantidad de ventas en el turno
    efectivo_bs: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )  # Efectivo en bolívares recibido
    efectivo_usd: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )  # Efectivo en dólares recibido
    tarjeta: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )  # Tarjeta recibida
    pago_movil: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )  # Pago móvil recibido
    bio_pago: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )  # BioPago recibido
    sobrante_faltante_bs: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )  # Diferencia (físico - sistema)
    observaciones: str | None = Field(default=None, max_length=500)
