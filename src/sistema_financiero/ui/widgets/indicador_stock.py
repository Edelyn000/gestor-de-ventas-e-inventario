from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel


# IndicadorStock: Indicador visual del nivel de stock.
class IndicadorStock(QLabel):
    """QLabel coloreado que muestra el estado del stock."""

    COLOR_BAJO = QColor("#d97706")
    COLOR_SIN_STOCK = QColor("#dc2626")
    COLOR_OK = QColor("#16a34a")

    def __init__(self, stock_actual: int = 0, stock_minimo: int = 0) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.actualizar(stock_actual, stock_minimo)

    def actualizar(self, stock_actual: int, stock_minimo: int) -> None:
        if stock_actual == 0:
            self.setText("SIN STOCK")
            self.setStyleSheet(
                f"color: {self.COLOR_SIN_STOCK.name()}; font-weight: bold;",
            )
        elif stock_actual <= stock_minimo:
            self.setText("STOCK BAJO")
            self.setStyleSheet(
                f"color: {self.COLOR_BAJO.name()}; font-weight: bold;",
            )
        else:
            self.setText("OK")
            self.setStyleSheet(
                f"color: {self.COLOR_OK.name()}; font-weight: bold;",
            )

