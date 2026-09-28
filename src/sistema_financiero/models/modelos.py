from datetime import date, datetime
from decimal import Decimal
from typing import ClassVar

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from sistema_financiero.utils import MONEDA_BS, ORIGEN_TASA_BCV, TIPO_VENTA_UNIDAD
from sistema_financiero.utils.fecha import ahora


# Categoria: Categoria de producto con clave normalizada unica.
class Categoria(SQLModel, table=True):
    __tablename__: ClassVar[str] = "categoria"

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True),
    )
    nombre: str = Field(max_length=100)
    clave: str = Field(
        sa_column=Column(String(100), nullable=False, unique=True, index=True),
    )

    productos: list[Producto] = Relationship(back_populates="categoria")


# Producto: Producto con precios en USD, unidad y stock.
class Producto(SQLModel, table=True):
    idproducto: int | None = Field(default=None, primary_key=True)
    nombre_producto: str = Field(max_length=200, index=True)
    categoria_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("categoria.id"), nullable=True, index=True),
    )
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
    categoria: Categoria | None = Relationship(
        back_populates="productos",
        sa_relationship_kwargs={"lazy": "selectin"},
    )


# Venta: Venta con totales, estado, caja y pagos asociados.
class Venta(SQLModel, table=True, __tablename__="venta", __table_args__={"extend_existing": True}):
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
    transferencia: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    estado: str = Field(
        default="COMPLETADA",
        sa_column=Column(String(20), nullable=False, default="COMPLETADA"),
    )
    caja_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("caja.id"), nullable=True),
    )

    motivo_anulacion: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    anulado_por: str | None = Field(
        default=None,
        sa_column=Column(String(100), nullable=True),
    )

    detalles: list[VentaDetalle] = Relationship(back_populates="venta")
    pagos: list[PagoVenta] = Relationship(back_populates="venta")


# VentaDetalle: Linea de un producto dentro de una venta.
class VentaDetalle(SQLModel, table=True):
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


# PagoVenta: Pago de una venta por metodo y moneda.
class PagoVenta(SQLModel, table=True):
    __tablename__: ClassVar[str] = "venta_pago"

    idpago: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True),
    )
    venta_id: int = Field(
        sa_column=Column(
            ForeignKey("venta.idventa", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    metodo: str = Field(max_length=20, index=True)
    moneda: str = Field(default=MONEDA_BS, max_length=5)
    monto: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    monto_bs: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    tasa_cambio: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    referencia: str | None = Field(default=None, max_length=100)
    fecha_pago: datetime = Field(
        default_factory=ahora,
        sa_column=Column(DateTime, nullable=False, default=ahora),
    )

    venta: Venta | None = Relationship(back_populates="pagos")


# MovimientoInventario: Auditoria de entrada, salida o ajuste de stock.
class MovimientoInventario(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    producto_id: int = Field(
        sa_column=Column(ForeignKey("producto.idproducto", ondelete="CASCADE")),
    )
    tipo: str = Field(max_length=20)
    motivo: str = Field(max_length=50)
    cantidad: Decimal = Field(default=Decimal("0.000"), max_digits=10, decimal_places=3)
    stock_anterior: Decimal = Field(default=Decimal("0.000"), max_digits=10, decimal_places=3)
    stock_nuevo: Decimal = Field(default=Decimal("0.000"), max_digits=10, decimal_places=3)
    referencia_id: int | None = Field(default=None)
    observaciones: str | None = Field(default=None, max_length=255)
    fecha_movimiento: datetime | None = Field(default=None)

    producto: Producto | None = Relationship(back_populates="movimientos")


# TasaCambio: Tasa de cambio por dia y origen (BCV o manual).
class TasaCambio(SQLModel, table=True):
    __table_args__: ClassVar[tuple[object, ...]] = (
        UniqueConstraint("fecha", "origen", name="uq_tasacambio_fecha_origen"),
    )

    id: int | None = Field(default=None, primary_key=True)
    fecha: date = Field(index=True)
    origen: str = Field(default=ORIGEN_TASA_BCV, max_length=20, index=True)
    registrado_por: str | None = Field(default=None, max_length=100)
    tasa_venta: Decimal = Field(max_digits=10, decimal_places=2)
    tasa_compra: Decimal = Field(max_digits=10, decimal_places=2)
    activa: bool = Field(default=True)
    fecha_registro: datetime | None = Field(default=None)


# Usuario: Usuario del sistema con rol y contrasena hasheada.
class Usuario(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    usuario: str = Field(max_length=50, unique=True, index=True)
    contrasena: str = Field(max_length=255)
    nombre_completo: str | None = Field(default=None, max_length=200)
    rol: str = Field(default="VENDEDOR", max_length=20)
    activo: bool = Field(default=True)
    fecha_creacion: datetime | None = Field(default=None)


# ReporteDiario: Reporte diario con totales, unidades y peso vendidos.
class ReporteDiario(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    fecha: date = Field(index=True, unique=True)
    total_ventas_bs: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    total_ventas_usd: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    cantidad_ventas: int = Field(default=0)
    unidades_vendidas: int = Field(default=0)
    peso_vendido_kg: Decimal = Field(default=Decimal("0.000"), max_digits=12, decimal_places=3)
    productos_stock_bajo: int = Field(default=0)
    productos_sin_stock: int = Field(default=0)
    efectivo_bs: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    efectivo_usd: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    tarjeta: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    pago_movil: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    bio_pago: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    transferencia: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    fecha_generacion: datetime | None = Field(default=None)


# ReporteVentaDetalle: Detalle de un producto vendido en un reporte.
class ReporteVentaDetalle(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    reporte_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("reportediario.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    producto_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
    )
    nombre_producto: str = Field(max_length=100)
    tipo_venta: str = Field(default="UNIDAD", max_length=10)
    cantidad: Decimal = Field(default=Decimal("0.000"), max_digits=10, decimal_places=3)


# Caja: Caja del turno con apertura, cierre y arqueo.
class Caja(SQLModel, table=True, __tablename__="caja"):
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
    )
    fecha_cierre: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime, nullable=True),
    )
    monto_cierre_bs: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    estado: str = Field(
        default="ABIERTA",
        sa_column=Column(String(20), nullable=False, default="ABIERTA", index=True),
    )
    usuario_id: int = Field(
        sa_column=Column(Integer, ForeignKey("usuario.id"), nullable=False),
    )
    total_ventas_bs: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    total_ventas_usd: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    cantidad_ventas: int | None = Field(default=None)
    efectivo_bs: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    efectivo_usd: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    tarjeta: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    pago_movil: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    bio_pago: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    transferencia: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    sobrante_faltante_bs: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    observaciones: str | None = Field(default=None, max_length=500)

