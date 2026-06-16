# ============================================================
# ARCHIVO: ui/ventas_pagina.py  (PAGINA DE VENTAS)
# ============================================================
# Widget independiente para el historial y gestion de ventas.
#
# QUE MUESTRA:
#   1. Botonera: Nueva Venta, Anular Venta, Refrescar.
#   2. Filtro de fechas (desde / hasta) para acotar el historial.
#   3. Tabla de ventas con doble clic para ver detalle.
#
# SENIALES (para MainWindow):
#   - nueva_venta: el usuario quiere registrar una venta.
#
# QUE SE PUEDE MODIFICAR:
#   - Estilos (colores, fuentes, tamaños) en _crear_barra_herramientas().
#   - Columnas y anchos en _crear_tabla_ventas().
#   - Textos, etiquetas, placeholders.
#   - Logica de filtro en cargar().
#
# QUE NO SE DEBE TOCAR:
#   - Nombre de la clase (VentasPagina).
#   - Firma del __init__ (controlador_ventas, controlador_productos).
#   - La senial nueva_venta (MainWindow la conecta).
# ============================================================
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.producto_controller import ProductoController
from ..core.venta_controller import VentaController
from ..utils import formatear_bs, formatear_usd


class VentasPagina(QWidget):
    nueva_venta = pyqtSignal()

    def __init__(
        self,
        controlador_ventas: VentaController,
        controlador_productos: ProductoController,
    ) -> None:
        super().__init__()

        self.controlador_ventas = controlador_ventas
        self.controlador_productos = controlador_productos

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        lbl_titulo = QLabel("Ventas")
        fuente = QFont()
        fuente.setPointSize(24)
        fuente.setBold(True)
        lbl_titulo.setFont(fuente)
        layout.addWidget(lbl_titulo)

        layout.addLayout(self._crear_barra_herramientas())
        layout.addSpacing(10)

        layout.addLayout(self._crear_filtro_fechas())
        layout.addSpacing(10)

        self.tabla_ventas = self._crear_tabla_ventas()
        layout.addWidget(self.tabla_ventas, 1)

        self.cargar()

    def _crear_barra_herramientas(self) -> QHBoxLayout:
        barra = QHBoxLayout()
        btn_nueva = QPushButton("+ Nueva Venta")
        btn_nueva.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 16px;"
        )
        btn_nueva.clicked.connect(self.nueva_venta.emit)
        barra.addWidget(btn_nueva)
        btn_anular = QPushButton("Anular Venta")
        btn_anular.setStyleSheet("background-color: #f44336; color: white; padding: 8px 16px;")
        btn_anular.clicked.connect(self._anular_venta)
        barra.addWidget(btn_anular)
        btn_refrescar = QPushButton("Refrescar")
        btn_refrescar.clicked.connect(self.cargar)
        barra.addWidget(btn_refrescar)
        barra.addStretch()
        return barra

    def _crear_filtro_fechas(self) -> QHBoxLayout:
        filtro = QHBoxLayout()
        filtro.addWidget(QLabel("Desde:"))
        self.fecha_desde = QDateEdit()
        self.fecha_desde.setCalendarPopup(True)
        self.fecha_desde.setDate(self.fecha_desde.date().addDays(-30))
        filtro.addWidget(self.fecha_desde)
        filtro.addWidget(QLabel("Hasta:"))
        self.fecha_hasta = QDateEdit()
        self.fecha_hasta.setCalendarPopup(True)
        self.fecha_hasta.setDate(self.fecha_hasta.date())
        filtro.addWidget(self.fecha_hasta)
        btn_filtrar = QPushButton("Filtrar")
        btn_filtrar.clicked.connect(self.cargar)
        filtro.addWidget(btn_filtrar)
        filtro.addStretch()
        return filtro

    def _crear_tabla_ventas(self) -> QTableWidget:
        tabla = QTableWidget()
        columnas = [
            ("ID", 50),
            ("Factura", 140),
            ("Fecha", 150),
            ("Total Bs", 100),
            ("Total USD", 100),
            ("Estado", 100),
        ]
        tabla.setColumnCount(len(columnas))
        tabla.setHorizontalHeaderLabels([c[0] for c in columnas])
        for i, (_, ancho) in enumerate(columnas):
            tabla.setColumnWidth(i, ancho)
        tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tabla.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
        tabla.cellDoubleClicked.connect(self._detalle_venta)
        return tabla

    def cargar(self) -> None:
        desde = datetime.combine(self.fecha_desde.date().toPyDate(), datetime.min.time())
        hasta = datetime.combine(self.fecha_hasta.date().toPyDate(), datetime.max.time())

        ventas = self.controlador_ventas.historial_por_fecha(desde, hasta)

        self.tabla_ventas.setRowCount(len(ventas))
        for fila, venta in enumerate(ventas):
            self.tabla_ventas.setItem(fila, 0, QTableWidgetItem(str(venta.idventa)))
            factura = venta.numero_factura or "-"
            self.tabla_ventas.setItem(fila, 1, QTableWidgetItem(factura))
            fv = venta.fecha_venta
            fecha_str = fv.strftime("%d/%m/%Y %H:%M") if fv else "-"
            self.tabla_ventas.setItem(fila, 2, QTableWidgetItem(fecha_str))
            self.tabla_ventas.setItem(fila, 3, QTableWidgetItem(formatear_bs(venta.total_bs)))
            self.tabla_ventas.setItem(fila, 4, QTableWidgetItem(formatear_usd(venta.total_usd)))
            item_estado = QTableWidgetItem(venta.estado)
            if venta.estado == "ANULADA":
                item_estado.setForeground(Qt.GlobalColor.red)
            else:
                item_estado.setForeground(Qt.GlobalColor.darkGreen)
            self.tabla_ventas.setItem(fila, 5, item_estado)

    def _anular_venta(self) -> None:
        fila = self.tabla_ventas.currentRow()
        if fila < 0:
            return

        item_id = self.tabla_ventas.item(fila, 0)
        if item_id is None:
            return
        idventa = int(item_id.text())

        venta = self.controlador_ventas.obtener_por_id(idventa)
        if venta is None:
            return

        if venta.estado == "ANULADA":
            return

        respuesta = QMessageBox.question(
            self,
            "Confirmar anulacion",
            f"Seguro que deseas anular la factura {venta.numero_factura}?\n"
            "El stock de los productos se devolvera automaticamente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if respuesta == QMessageBox.StandardButton.Yes:
            try:
                self.controlador_ventas.anular(idventa)
                QMessageBox.information(
                    self, "Exito", f"Venta {venta.numero_factura} anulada correctamente."
                )
                self.cargar()
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))

    def _detalle_venta(self) -> None:
        fila = self.tabla_ventas.currentRow()
        if fila < 0:
            return

        item_id = self.tabla_ventas.item(fila, 0)
        if item_id is None:
            return
        idventa = int(item_id.text())
        item_factura = self.tabla_ventas.item(fila, 1)
        factura = item_factura.text() if item_factura else "-"

        detalles = self.controlador_ventas.obtener_detalles(idventa)
        if not detalles:
            QMessageBox.information(self, "Detalle", "Esta venta no tiene productos registrados.")
            return

        lineas = [f"Factura: {factura}\n", "=" * 30]
        for det in detalles:
            producto = self.controlador_productos.obtener_por_id(det.producto_id)
            nombre = producto.nombre_producto if producto else f"ID {det.producto_id}"
            lineas.append(f"{det.cantidad}x {nombre} = {formatear_bs(det.subtotal_bs)}")
        lineas.append("=" * 30)

        QMessageBox.information(
            self,
            f"Detalle de Venta - {factura}",
            "\n".join(lineas),
        )
