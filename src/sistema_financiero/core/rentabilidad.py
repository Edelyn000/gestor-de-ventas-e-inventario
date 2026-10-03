"""Calculos de rentabilidad del dia (COGS, utilidad bruta y margen)

Modulo PURO (sin BD ni Qt) para que las reglas de negocio se puedan
probar solas. El costo historico llega como SNAPSHOT desde
``VentaDetalle.precio_costo_unitario``: nunca se relee el precio actual
del producto, porque si el dueño cambia el costo despues, la venta
historica debe seguir mostrando lo que realmente costo.
"""

from decimal import ROUND_HALF_UP, Decimal

from ..models import Producto
from ..utils import DECIMAL_CERO

# Un costo menor al 1% del precio de venta viene de otra era monetaria.
UMBRAL_COSTO_SOSPECHOSO: Decimal = Decimal("0.01")

# Escala de los montos y del porcentaje de margen (2 decimales).
_ESCALA_MONEDA: Decimal = Decimal("0.01")
_ESCALA_PORCENTAJE: Decimal = Decimal("0.01")

# Texto mostrado cuando el margen no existe (reporte legado).
TEXTO_SIN_MARGEN: str = "—"

# Todo monto acepta Decimal y tolera int o float (SQLite y mocks).
Monto = Decimal | int | float


# Convierte a Decimal tolerando int, float, None o str.
def _decimal(valor: object) -> Decimal:
    if valor is None:
        return DECIMAL_CERO
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


# El costo de compra del producto no es creible.
def costo_no_confiable(producto: Producto) -> bool:
    """Se marca cuando no hay costo, el costo es mayor o igual al precio
    de venta (se venderia a perdida), o el costo es menos del 1% del
    precio de venta (dato de una era monetaria vieja).
    """
    costo = _decimal(producto.precio_compra)
    precio_venta = _decimal(producto.precio_venta_bs)
    if costo <= 0:
        return True
    if precio_venta <= 0:
        return False
    if costo >= precio_venta:
        return True
    return costo < precio_venta * UMBRAL_COSTO_SOSPECHOSO


# Utilidad bruta = ingresos - costo de las ventas.
def utilidad_bruta(ingresos: Monto, costo: Monto) -> Decimal:
    return (_decimal(ingresos) - _decimal(costo)).quantize(
        _ESCALA_MONEDA,
        rounding=ROUND_HALF_UP,
    )


# Margen de ganancia en porcentaje; None si los ingresos son cero.
def margen_ganancia(ingresos: Monto, utilidad: Monto) -> Decimal | None:
    base = _decimal(ingresos)
    if base <= 0:
        return None
    porcentaje = _decimal(utilidad) / base * Decimal("100")
    return porcentaje.quantize(_ESCALA_PORCENTAJE, rounding=ROUND_HALF_UP)


# Formatea el margen con 1 decimal y signo ("23.3 %" o "—").
def formatear_margen(margen: Monto | None) -> str:
    if margen is None:
        return TEXTO_SIN_MARGEN
    return f"{_decimal(margen):.1f} %"


# Costo y utilidad del reporte son creibles para mostrarlos.
def rentabilidad_calculada(
    total_ventas_bs: Decimal | None,
    margen_ganancia: Decimal | None,
) -> bool:
    """Un margen None con ingresos significa "rentabilidad no calculada": es
    el caso de los reportes historicos que la migracion no pudo alinear con
    las ventas de su dia. Con ingresos en cero no hay margen que calcular,
    pero costo y utilidad en cero si son correctos.
    """
    if _decimal(total_ventas_bs) <= 0:
        return True
    return margen_ganancia is not None


# Filtra los productos con costo de compra no confiable.
def productos_con_costo_no_confiable(productos: list[Producto]) -> list[Producto]:
    return [p for p in productos if costo_no_confiable(p)]
