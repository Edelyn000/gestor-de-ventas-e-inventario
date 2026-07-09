# ============ SELECTOR DE RANGO DE FECHAS REUTILIZABLE ============
# --- NO TOCAR: clase, metodos de conversion de fechas.
# --- MODIFICABLE: etiquetas, dias por defecto, margenes.
from datetime import date, datetime

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QDateEdit, QHBoxLayout, QLabel, QWidget


class SelectorFecha(QWidget):
    """Selector de rango de fechas (desde / hasta) con calendario emergente."""

    # --- MODIFICABLE: textos de etiquetas y periodo por defecto.
    def __init__(
        self,
        etiqueta_desde: str = "Desde:",
        etiqueta_hasta: str = "Hasta:",
        dias_por_defecto: int = 30,
    ) -> None:
        super().__init__()

        # --- MODIFICABLE: layout y configuracion de los QDateEdit.
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

    # --- NO TOCAR: metodos de extraccion de fechas.
    def fecha_desde(self) -> date:
        qd = self.desde.date()
        return date(qd.year(), qd.month(), qd.day())

    def fecha_hasta(self) -> date:
        qd = self.hasta.date()
        return date(qd.year(), qd.month(), qd.day())

    # --- NO TOCAR: conversion a datetime para consultas a BD.
    def rango_datetime(self) -> tuple[datetime, datetime]:
        desde = self.fecha_desde()
        hasta = self.fecha_hasta()
        return (
            datetime(desde.year, desde.month, desde.day, 0, 0, 0),
            datetime(hasta.year, hasta.month, hasta.day, 23, 59, 59),
        )
