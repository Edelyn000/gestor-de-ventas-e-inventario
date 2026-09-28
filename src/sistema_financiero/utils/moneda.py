# moneda.py: Formateo de montos en bolivares y dolares.

from decimal import Decimal

from PyQt6.QtCore import QLocale
from PyQt6.QtWidgets import QDoubleSpinBox

DECIMAL_CERO: Decimal = Decimal("0.00")

DECIMAL_CENTIMO: Decimal = Decimal("0.01")

SIMBOLO_BS: str = "Bs."
SIMBOLO_USD: str = "$"
SIGLAS_USD: str = "USD"

SUFIJO_BS: str = " Bs."
SUFIJO_USD: str = " $"
SUFIJO_USD_TEXTO: str = " USD"

LOCALE_BS: QLocale = QLocale(QLocale.Language.Spanish, QLocale.Country.Venezuela)
LOCALE_USD: QLocale = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)


# Formatea el numero con punto de miles y coma decimal.
def _formatear_es(valor: Decimal, decimales: int, miles: bool) -> str:
    """Formatea el numero con punto de miles y coma decimal."""
    if miles:
        base = f"{valor:,.{decimales}f}"
        return base.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{valor:.{decimales}f}".replace(".", ",")


# Formatea un monto en Bs.
def formatear_bs(valor: Decimal, decimales: int = 2, miles: bool = True) -> str:
    """Formatea un monto en Bs. Ej: 1.234,56 Bs."""
    return f"{_formatear_es(valor, decimales, miles)}{SUFIJO_BS}"


# Formatea un monto en Bs.
def formatear_bs_sin_sufijo(valor: Decimal, decimales: int = 2, miles: bool = True) -> str:
    """Formatea un monto en Bs. sin el sufijo. Ej: 1.234,56"""
    return _formatear_es(valor, decimales, miles)


# Formatea un monto en USD con $.
def formatear_usd(valor: Decimal, decimales: int = 2, miles: bool = True) -> str:
    """Formatea un monto en USD con $. Ej: 1,234.56 $"""
    if miles:
        return f"{valor:,.{decimales}f}{SUFIJO_USD}"
    return f"{valor:.{decimales}f}{SUFIJO_USD}"


# Formatea un monto con USD texto.
def formatear_usd_texto(valor: Decimal, decimales: int = 2, miles: bool = True) -> str:
    """Formatea un monto con USD texto. Ej: 1,234.56 USD"""
    if miles:
        return f"{valor:,.{decimales}f}{SUFIJO_USD_TEXTO}"
    return f"{valor:.{decimales}f}{SUFIJO_USD_TEXTO}"


# Redondea un Decimal a 2 decimales para montos monetarios.
def redondear_moneda(valor: Decimal) -> Decimal:
    """Redondea un Decimal a 2 decimales para montos monetarios."""
    return valor.quantize(DECIMAL_CENTIMO)


# Formatea stock segun su valor, sin ceros de relleno.
def formatear_stock(valor: Decimal | int | float) -> str:
    """Formatea stock segun su valor, sin ceros de relleno."""
    if not isinstance(valor, Decimal):
        valor = Decimal(str(valor))
    if valor == valor.to_integral_value():
        return _formatear_es(valor, 0, miles=True)
    return _formatear_es(valor, 3, miles=True).rstrip("0").rstrip(",")


# Formatea un peso en kilogramos como texto legible humano.
def formatear_peso_kg(peso_kg: Decimal | int | float | None) -> str:
    """Formatea un peso en kilogramos como texto legible humano."""
    if peso_kg is None:
        return "−"
    if not isinstance(peso_kg, Decimal):
        peso_kg = Decimal(str(peso_kg))
    peso_kg = peso_kg.quantize(Decimal("0.001"))
    if peso_kg == Decimal("0.000"):
        return "—"
    gramos = int(peso_kg * Decimal("1000"))
    kg, g = divmod(gramos, 1000)
    if kg > 0 and g > 0:
        return f"{kg} kg y {g} g"
    if kg > 0:
        return f"{kg} kg"
    return f"{g} g"


# Configura un QDoubleSpinBox para montos en Bs.
def configurar_spinbox_bs(spin: QDoubleSpinBox) -> None:
    """Configura un QDoubleSpinBox para montos en Bs."""
    spin.setLocale(LOCALE_BS)
    spin.setDecimals(2)
    spin.setRange(0, RANGO_SPINBOX_MAX)
    spin.setGroupSeparatorShown(True)
    spin.setSuffix(SUFIJO_BS)


# Configura un QDoubleSpinBox para montos en USD.
def configurar_spinbox_usd(spin: QDoubleSpinBox) -> None:
    """Configura un QDoubleSpinBox para montos en USD."""
    spin.setLocale(LOCALE_USD)
    spin.setDecimals(2)
    spin.setRange(0, RANGO_SPINBOX_MAX)
    spin.setGroupSeparatorShown(True)
    spin.setSuffix(SUFIJO_USD)


from .constantes import RANGO_SPINBOX_MAX  # noqa: E402

