from datetime import date, datetime
from decimal import Decimal

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlmodel import select

from ..core.tasa_cambio_service import TasaCambioService
from ..models import Producto, Venta, get_session
from ..utils import formatear_bs


class DashboardPagina(QWidget):
    """Pagina de inicio con resumen, graficos y alertas de stock."""

    def __init__(self, controlador_tasas: TasaCambioService) -> None:
        super().__init__()
        self.controlador_tasas = controlador_tasas

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        lbl_titulo = QLabel("Dashboard")
        fuente_titulo = QFont()
        fuente_titulo.setPointSize(24)
        fuente_titulo.setBold(True)
        lbl_titulo.setFont(fuente_titulo)
        layout.addWidget(lbl_titulo)

        layout.addLayout(self._crear_tarjetas_resumen())

        lbl_stock = QLabel("Productos con Stock Bajo")
        lbl_stock.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(lbl_stock)

        self.tabla_stock_bajo = QTableWidget()
        self.tabla_stock_bajo.setColumnCount(5)
        self.tabla_stock_bajo.setHorizontalHeaderLabels(
            ["Producto", "Categoria", "Stock Actual", "Stock Minimo", "Estado"]
        )
        self.tabla_stock_bajo.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
        self.tabla_stock_bajo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla_stock_bajo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla_stock_bajo.setMaximumHeight(200)
        layout.addWidget(self.tabla_stock_bajo)

        layout.addStretch()

    def _crear_tarjetas_resumen(self) -> QHBoxLayout:
        """Crea las 4 tarjetas de resumen: Ventas Hoy, Stock Bajo, Sin Stock, Tasa BCV."""
        fila_tarjetas = QHBoxLayout()
        fila_tarjetas.setSpacing(15)

        datos_tarjetas = [
            ("ventas_hoy", "Ventas Hoy", ""),
            ("stock_bajo", "Stock Bajo", ""),
            ("sin_stock", "Sin Stock", ""),
            ("tasa_bcv", "Tasa BCV", ""),
        ]

        self._dashboard_labels = {}

        for clave, titulo, _icono in datos_tarjetas:
            tarjeta = QFrame()
            tarjeta.setStyleSheet(
                "QFrame { background-color: white; border-radius: 10px; padding: 15px; }"
            )
            tarjeta.setMinimumHeight(100)

            layout_tarjeta = QVBoxLayout(tarjeta)
            layout_tarjeta.setContentsMargins(10, 10, 10, 10)
            layout_tarjeta.setSpacing(5)

            lbl_titulo_tarjeta = QLabel(titulo)
            lbl_titulo_tarjeta.setStyleSheet("color: #666; font-size: 12px;")
            layout_tarjeta.addWidget(lbl_titulo_tarjeta)

            lbl_valor = QLabel("—")
            lbl_valor.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a1a2e;")
            layout_tarjeta.addWidget(lbl_valor)

            self._dashboard_labels[clave] = lbl_valor
            fila_tarjetas.addWidget(tarjeta)

        return fila_tarjetas

    def refrescar(self) -> None:
        """Refresca todos los datos del dashboard (tarjetas, grafico, tabla)."""
        hoy = datetime.now()
        desde_hoy = datetime(hoy.year, hoy.month, hoy.day, 0, 0, 0)
        hasta_hoy = datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59)

        with get_session() as session:
            ventas_hoy = session.exec(
                select(Venta).where(
                    Venta.fecha_venta >= desde_hoy,  # type: ignore[operator]
                    Venta.fecha_venta <= hasta_hoy,  # type: ignore[operator]
                    Venta.estado == "COMPLETADA",
                )
            ).all()
            total_ventas_hoy: Decimal = sum((v.total_bs for v in ventas_hoy), start=Decimal())

            productos = session.exec(select(Producto)).all()
            stock_bajo = sum(1 for p in productos if 0 < p.stock_actual <= p.stock_minimo)
            sin_stock = sum(1 for p in productos if p.stock_actual == 0)

            tasa = self.controlador_tasas.tasa_activa()

            if tasa is None or tasa.fecha < date.today():
                self.controlador_tasas.obtener_desde_bcv()
                tasa = self.controlador_tasas.tasa_activa()

        self._dashboard_labels["ventas_hoy"].setText(formatear_bs(total_ventas_hoy))
        self._dashboard_labels["stock_bajo"].setText(f"{stock_bajo} productos")
        self._dashboard_labels["sin_stock"].setText(f"{sin_stock} productos")
        self._dashboard_labels["tasa_bcv"].setText(
            formatear_bs(tasa.tasa_venta) if tasa else "Sin tasa"
        )

        self._refrescar_tabla_stock_bajo()

    def _refrescar_tabla_stock_bajo(self) -> None:
        """Llena la tabla de productos con stock bajo/sin stock."""
        with get_session() as session:
            todos = session.exec(select(Producto)).all()
            productos_alerta = [p for p in todos if p.stock_actual <= p.stock_minimo]

        self.tabla_stock_bajo.setRowCount(len(productos_alerta))
        for fila, prod in enumerate(productos_alerta):
            self.tabla_stock_bajo.setItem(fila, 0, QTableWidgetItem(prod.nombre_producto))
            self.tabla_stock_bajo.setItem(fila, 1, QTableWidgetItem(prod.categoria or ""))
            self.tabla_stock_bajo.setItem(fila, 2, QTableWidgetItem(str(prod.stock_actual)))
            self.tabla_stock_bajo.setItem(fila, 3, QTableWidgetItem(str(prod.stock_minimo)))
            estado = "SIN STOCK" if prod.stock_actual == 0 else "STOCK BAJO"
            item_estado = QTableWidgetItem(estado)
            self.tabla_stock_bajo.setItem(fila, 4, item_estado)

        self.tabla_stock_bajo.resizeColumnsToContents()
