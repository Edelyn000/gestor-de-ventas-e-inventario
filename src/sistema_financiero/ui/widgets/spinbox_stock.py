from decimal import Decimal
from typing import override

from PyQt6.QtWidgets import QDoubleSpinBox, QWidget

from sistema_financiero.utils import (
    LOCALE_BS,
    MAX_GRAMOS_CAPTURA,
    MAX_KILOS_CAPTURA,
    RANGO_STOCK_MAX,
    formatear_stock,
)


# SpinBoxStock: Spinbox de stock con formato local y modos entero o decimal.
class SpinBoxStock(QDoubleSpinBox):
    """QDoubleSpinBox para stock/cantidades con formato limpio por unidad."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._modo_entero = True
        self.setLocale(LOCALE_BS)
        self.setRange(0, RANGO_STOCK_MAX)
        self.setGroupSeparatorShown(True)
        self.set_modo_entero(True)

    def set_modo_entero(self, entero: bool) -> None:
        """Configura el spinbox para unidades enteras o decimales."""
        self._modo_entero = entero
        if entero:
            self.setDecimals(0)
            self.setSingleStep(1)
        else:
            self.setDecimals(3)
            self.setSingleStep(0.1)
        self.setValue(self.value())

    def set_modo_kg(self) -> None:
        """Casilla KILOS del ticket: DECIMALES de 0 a 999 (0.5 = 500 g)."""
        self._modo_entero = False
        self.setDecimals(3)
        self.setSingleStep(0.1)
        self.setRange(0, MAX_KILOS_CAPTURA)
        self.setGroupSeparatorShown(False)
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.setValue(self.value())

    def set_modo_gramos(self) -> None:
        """Casilla GRAMOS del ticket: enteros con paso 50, tope 999."""
        self._modo_entero = True
        self.setDecimals(0)
        self.setSingleStep(50)
        self.setRange(0, MAX_GRAMOS_CAPTURA)
        self.setGroupSeparatorShown(False)
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.setValue(self.value())

    @override
    def textFromValue(self, value: float) -> str:
        valor = Decimal(str(value))
        if self._modo_entero:
            return formatear_stock(valor.to_integral_value())
        return formatear_stock(valor)

