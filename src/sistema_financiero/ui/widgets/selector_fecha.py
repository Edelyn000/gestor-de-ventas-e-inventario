from datetime import date, datetime

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QDateEdit, QHBoxLayout, QLabel, QWidget

from ...utils.fecha import rango_dia_utc


# SelectorFecha: Selector de fecha de un solo dia.
class SelectorFecha(QWidget):
    """Selector de rango de fechas (desde / hasta) con calendario emergente."""

    # Crea dos campos de fecha con etiquetas y rango por defecto.
    def __init__(
        self,
        etiqueta_desde: str = "Desde:",
        etiqueta_hasta: str = "Hasta:",
        dias_por_defecto: int = 30,
    ) -> None:
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel(etiqueta_desde))
        self.desde = QDateEdit()
        self.desde.setCalendarPopup(True)
        self.desde.setDate(QDate.currentDate().addDays(-dias_por_defecto))
        layout.addWidget(self.desde)

        layout.addWidget(QLabel(etiqueta_hasta))
        self.hasta = QDateEdit()
        self.hasta.setCalendarPopup(True)
        self.hasta.setDate(QDate.currentDate())
        layout.addWidget(self.hasta)

    # Devuelve la fecha inicial elegida como date.
    def fecha_desde(self) -> date:
        qd = self.desde.date()
        return date(qd.year(), qd.month(), qd.day())

    # Devuelve la fecha final elegida como date.
    def fecha_hasta(self) -> date:
        qd = self.hasta.date()
        return date(qd.year(), qd.month(), qd.day())

    # Convierte el rango elegido a limites UTC del dia local.
    def rango_datetime(self) -> tuple[datetime, datetime]:
        desde = self.fecha_desde()
        hasta = self.fecha_hasta()
        return rango_dia_utc(desde)[0], rango_dia_utc(hasta)[1]

