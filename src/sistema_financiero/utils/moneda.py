# ============================================================
# ARCHIVO: utils/moneda.py
# FORMATEO DE MONEDA VES/USD
#
# ¿POR QUE FUNCIONES DE FORMATEO?
#   - En lugar de escribir f"Bs. {valor:,.2f}" en 20 lugares,
#     llamas a formatear_bs(valor).
#   - Si el formato cambia (ej: "Bs." → "Bs.S"), solo
#     cambias UNA linea.
#
# ¿POR QUE USAR Decimal?
#   - Los float tienen errores de redondeo (0.1+0.2=0.300...4).
#   - En finanzas, la precision exacta NO es opcional.
#   - Decimal("10.00") es exactamente 10.00.
#
# ¿COMO SE USA?
#   from sistema_financiero.utils import formatear_bs
#   print(formatear_bs(Decimal("1234.50")))  # "1.234,50 Bs."
#
# CRITERIO DE FORMATO (por moneda):
#   - Bs. → formato espanol: punto de miles, coma decimal.
#           Ej: "1.234,56 Bs."
#   - USD → formato americano: coma de miles, punto decimal.
#           Ej: "1,234.56 $".
#   - El simbolo SIEMPRE va como sufijo, tras el monto.
# ============================================================

from decimal import Decimal

from PyQt6.QtCore import QLocale
from PyQt6.QtWidgets import QDoubleSpinBox

# ----------------------------------------------------------
# CONSTANTES DE MONEDA
# ----------------------------------------------------------

# DECIMAL_CERO: Decimal("0.00") para inicializar montos.
# En lugar de escribir Decimal("0.00") cada vez.
DECIMAL_CERO: Decimal = Decimal("0.00")

# DECIMAL_CENTIMO: Decimal("0.01") para redondear a 2 decimales.
# Se usa con .quantize() para eliminar decimales extra.
DECIMAL_CENTIMO: Decimal = Decimal("0.01")

# Simbolos monetarios para mostrar al usuario.
SIMBOLO_BS: str = "Bs."
SIMBOLO_USD: str = "$"
SIGLAS_USD: str = "USD"

# Sufijos con espacio para mostrar la moneda DETRAS del monto.
#   formatear_bs(Decimal("1234.50"))  → "1.234,50 Bs."
#   formatear_usd(Decimal("1234.50")) → "1,234.56 $"
SUFIJO_BS: str = " Bs."
SUFIJO_USD: str = " $"
SUFIJO_USD_TEXTO: str = " USD"

# Locales para QDoubleSpinBox: garantizan separadores correctos
# al escribir/leer montos (Bs. en espanol, USD en americano).
LOCALE_BS: QLocale = QLocale(QLocale.Language.Spanish, QLocale.Country.Venezuela)
LOCALE_USD: QLocale = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)


# ----------------------------------------------------------
# FUNCION INTERNA: _formatear_es()
# Formatea un numero con separadores en espanol (1.234,56).
# Se implementa intercambiando los separadores del formato
# base en-US de Python, sin depender del locale del sistema.
# ----------------------------------------------------------
def _formatear_es(valor: Decimal, decimales: int, miles: bool) -> str:
    """Formatea el numero con punto de miles y coma decimal."""
    if miles:
        # "1,234.56" → "1.234,56" (intercambio con marcador temporal).
        base = f"{valor:,.{decimales}f}"
        return base.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    # Sin separador de miles: "1000.00" → "1000,00".
    return f"{valor:.{decimales}f}".replace(".", ",")


# ----------------------------------------------------------
# FUNCION: formatear_bs()
# Formatea un monto en bolivares con formato espanol.
#
# Parametros:
#   valor       → Decimal con el monto a formatear.
#   decimales   → Cantidad de decimales (default 2).
#   miles       → Si True, usa separador de miles (1.234,56).
#
# Retorna: string formateado, ej: "1.234,56 Bs."
#
# Uso tipico:
#   etiqueta.setText(formatear_bs(total_venta))
#   → "1.500,00 Bs."
# ----------------------------------------------------------
def formatear_bs(valor: Decimal, decimales: int = 2, miles: bool = True) -> str:
    """Formatea un monto en Bs. Ej: 1.234,56 Bs."""
    return f"{_formatear_es(valor, decimales, miles)}{SUFIJO_BS}"


# ----------------------------------------------------------
# FUNCION: formatear_usd()
# Formatea un monto en dolares (formato americano) con $.
#
# Retorna: "1,234.56 $"
#
# Uso tipico:
#   etiqueta.setText(formatear_usd(total_usd))
# ----------------------------------------------------------
def formatear_usd(valor: Decimal, decimales: int = 2, miles: bool = True) -> str:
    """Formatea un monto en USD con $. Ej: 1,234.56 $"""
    if miles:
        return f"{valor:,.{decimales}f}{SUFIJO_USD}"
    return f"{valor:.{decimales}f}{SUFIJO_USD}"


# ----------------------------------------------------------
# FUNCION: formatear_usd_texto()
# Formatea con "USD" en lugar de "$".
# Se usa en reportes Excel donde "USD" se ve mas formal.
#
# Retorna: "1,234.56 USD"
# ----------------------------------------------------------
def formatear_usd_texto(valor: Decimal, decimales: int = 2, miles: bool = True) -> str:
    """Formatea un monto con USD texto. Ej: 1,234.56 USD"""
    if miles:
        return f"{valor:,.{decimales}f}{SUFIJO_USD_TEXTO}"
    return f"{valor:.{decimales}f}{SUFIJO_USD_TEXTO}"


# ----------------------------------------------------------
# FUNCION: redondear_moneda()
# Redondea un Decimal a 2 decimales (centimos).
#
# ¿POR QUE REDONDEAR?
#   - Los calculos pueden generar Decimales con muchos
#     decimales: 10.00 / 3 = 3.333333...
#   - En dinero, solo importan los centimos.
#   - .quantize() trunca o redondea segun el modo.
#
# Uso:
#   total = redondear_moneda(Decimal("10.00") / Decimal("3"))
#   → Decimal("3.33")
# ----------------------------------------------------------
def redondear_moneda(valor: Decimal) -> Decimal:
    """Redondea un Decimal a 2 decimales para montos monetarios."""
    return valor.quantize(DECIMAL_CENTIMO)


def formatear_stock(valor: Decimal) -> str:
    """Formatea stock con 3 decimales y coma decimal. Ej: 5,000, 0,500, 1,250"""
    return f"{valor:.3f}".replace(".", ",")


# ----------------------------------------------------------
# FUNCION: configurar_spinbox_bs()
# Configura un QDoubleSpinBox para montos en bolivares.
#
# ¿QUE HACE?
#   1. Rango de 0 a 999,999 (no se pueden montos negativos).
#   2. 2 decimales (centimos).
#   3. Sufijo " Bs." y separador de miles visible (1.234,56 Bs.).
#
# Parametros:
#   spin → QDoubleSpinBox a configurar.
#
# Uso tipico:
#   configurar_spinbox_bs(self.spin_efectivo_bs)
#
# ¿POR QUE UNA FUNCION?
#   - La UI de ventas tiene 5 spinboxes de pago.
#   - Configurarlos uno por uno seria 15 lineas repetidas.
#   - Con esta funcion: 5 llamadas de 1 linea cada una.
# ----------------------------------------------------------
def configurar_spinbox_bs(spin: QDoubleSpinBox) -> None:
    """Configura un QDoubleSpinBox para montos en Bs."""
    spin.setLocale(LOCALE_BS)
    spin.setDecimals(2)
    spin.setRange(0, RANGO_SPINBOX_MAX)
    spin.setGroupSeparatorShown(True)
    spin.setSuffix(SUFIJO_BS)


# ----------------------------------------------------------
# FUNCION: configurar_spinbox_usd()
# Configura un QDoubleSpinBox para montos en dolares.
#
# Igual que configurar_spinbox_bs() pero con " $" como sufijo
# y formato americano (1,234.56 $).
# ----------------------------------------------------------
def configurar_spinbox_usd(spin: QDoubleSpinBox) -> None:
    """Configura un QDoubleSpinBox para montos en USD."""
    spin.setLocale(LOCALE_USD)
    spin.setDecimals(2)
    spin.setRange(0, RANGO_SPINBOX_MAX)
    spin.setGroupSeparatorShown(True)
    spin.setSuffix(SUFIJO_USD)


# Import necesario para RANGO_SPINBOX_MAX.
from .constantes import RANGO_SPINBOX_MAX  # noqa: E402
