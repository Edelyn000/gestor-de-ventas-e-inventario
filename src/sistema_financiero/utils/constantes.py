# constantes.py: Constantes de moneda, unidades y metodos de pago.

from decimal import ROUND_HALF_UP, Decimal

METODO_PAGO_EFECTIVO_BS: str = "efectivo_bs"
METODO_PAGO_EFECTIVO_USD: str = "efectivo_usd"
METODO_PAGO_TARJETA: str = "tarjeta"
METODO_PAGO_PAGO_MOVIL: str = "pago_movil"
METODO_PAGO_BIO_PAGO: str = "bio_pago"
METODO_PAGO_TRANSFERENCIA: str = "transferencia"

METODOS_PAGO: list[str] = [
    METODO_PAGO_EFECTIVO_BS,
    METODO_PAGO_EFECTIVO_USD,
    METODO_PAGO_TARJETA,
    METODO_PAGO_PAGO_MOVIL,
    METODO_PAGO_BIO_PAGO,
    METODO_PAGO_TRANSFERENCIA,
]


MONEDA_BS: str = "BS"
MONEDA_USD: str = "USD"

METODOS_PAGO_USD: list[str] = [METODO_PAGO_EFECTIVO_USD]


ORIGEN_TASA_BCV: str = "BCV"
ORIGEN_TASA_MANUAL: str = "MANUAL"


TOLERANCIA_REDONDEO: Decimal = Decimal("0.01")


ROL_ADMINISTRADOR: str = "ADMINISTRADOR"
ROL_VENDEDOR: str = "VENDEDOR"


ESTADO_VENTA_COMPLETADA: str = "COMPLETADA"
ESTADO_VENTA_ANULADA: str = "ANULADA"


TIPO_MOVIMIENTO_ENTRADA: str = "ENTRADA"
TIPO_MOVIMIENTO_SALIDA: str = "SALIDA"
TIPO_MOVIMIENTO_AJUSTE: str = "AJUSTE"


MOTIVO_COMPRA: str = "COMPRA"
MOTIVO_VENTA: str = "VENTA"
MOTIVO_DEVOLUCION: str = "DEVOLUCION"
MOTIVO_DEVOLUCION_ANULACION: str = "DEVOLUCION POR ANULACION"
MOTIVO_MERMA: str = "MERMA"
MOTIVO_AJUSTE: str = "AJUSTE"
MOTIVO_INVENTARIO_FISICO: str = "INVENTARIO FISICO"


PREFIJO_FACTURA: str = "FAC"


LONGITUD_MINIMA_CONTRASENA: int = 4


RANGO_SPINBOX_MAX: int = 999999

RANGO_STOCK_MAX: float = 999999.99


TIPO_VENTA_UNIDAD: str = "UNIDAD"
TIPO_VENTA_PESO: str = "PESO"

TIPO_VENTA_GRAMOS_LEGADO: str = "GRAMOS"

TIPOS_VENTA: list[str] = [
    TIPO_VENTA_UNIDAD,
    TIPO_VENTA_PESO,
]

UNIDADES_VENTA: list[str] = [
    TIPO_VENTA_UNIDAD,
    "KILO",
]

UNIDADES_MEDIDA: frozenset[str] = frozenset({"KILO"})

_UNIDADES_PESO: frozenset[str] = frozenset(
    {"KG", "KGS", "KILO", "KILOS", "KILOGRAMO", "KILOGRAMOS"}
)

_UNIDADES_GRAMOS: frozenset[str] = frozenset({"GRAMO", "GRAMOS", "GR", "GRS"})

_VARIANTES_UNIDAD: dict[str, str] = {
    "UNIDAD": "UNIDAD",
    "KILO": "KILO",
    "KILOGRAMO": "KILO",
    "KILOGRAMOS": "KILO",
    "KILOS": "KILO",
    "KGS": "KILO",
    "KG": "KILO",
    "GRAMO": "KILO",
    "GRAMOS": "KILO",
    "GRS": "KILO",
    "GR": "KILO",
    "LITRO": "UNIDAD",
    "LITROS": "UNIDAD",
    "LTS": "UNIDAD",
    "LT": "UNIDAD",
    "PAQUETE": "UNIDAD",
    "CAJA": "UNIDAD",
}


def normalizar_unidad(unidad: str) -> str:
    """Normaliza una unidad a su forma canonica del combo (UNIDAD/KILO)."""
    clave = (unidad or "").strip().upper()
    if clave in _VARIANTES_UNIDAD:
        return _VARIANTES_UNIDAD[clave]
    return unidad or TIPO_VENTA_UNIDAD


def deducir_tipo_venta(unidad: str) -> str:
    """Deduce el tipo de venta de un producto a partir de su unidad de medida."""
    unidad_normal = (unidad or "").strip().upper()
    if unidad_normal in _UNIDADES_PESO or unidad_normal in _UNIDADES_GRAMOS:
        return TIPO_VENTA_PESO
    return TIPO_VENTA_UNIDAD


def es_medida(tipo_venta: str | None) -> bool:
    """True si el tipo de venta es por PESO (se captura Kg + g)."""
    return (tipo_venta or "").strip().upper() in (
        TIPO_VENTA_PESO,
        TIPO_VENTA_GRAMOS_LEGADO,
    )


GRAMOS_POR_KILO: int = 1000

MAX_GRAMOS_CAPTURA: int = 999

MAX_KILOS_CAPTURA: int = 999

PESO_KG_GRANO: Decimal = Decimal("0.001")

PASOS_PESO_RAPIDO: tuple[Decimal, ...] = (
    Decimal("1.000"),
    Decimal("0.500"),
    Decimal("0.250"),
    Decimal("0.100"),
)


def _a_decimal(valor: Decimal | int | float | str | None) -> Decimal:
    """Convierte a Decimal tolerando None/str/int/float (0.0 si no se puede)."""
    if valor is None:
        return Decimal("0")
    if isinstance(valor, Decimal):
        return valor
    try:
        return Decimal(str(valor).strip())
    except ArithmeticError, ValueError:
        return Decimal("0")


def a_kg(
    kilos: Decimal | int | float | str | None, gramos: Decimal | int | float | str | None
) -> Decimal:
    """Suma las casillas Kg y g del POS y devuelve KILOGRAMOS."""
    total = _a_decimal(kilos) + _a_decimal(gramos) / GRAMOS_POR_KILO
    peso = total.quantize(PESO_KG_GRANO, rounding=ROUND_HALF_UP)
    if peso < 0:
        return Decimal("0.000")
    return peso


def descomponer_kg(peso_kg: Decimal | int | float | None) -> tuple[int, int]:
    """Parte un peso en kg en las casillas (Kg, g) del POS. Inverso de a_kg()."""
    peso = _a_decimal(peso_kg).quantize(PESO_KG_GRANO, rounding=ROUND_HALF_UP)
    if peso <= 0:
        return (0, 0)
    gramos = int(peso * GRAMOS_POR_KILO)
    kilos, resto = divmod(gramos, GRAMOS_POR_KILO)
    return (kilos, resto)

