from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

import pyqtgraph as pg
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlmodel import select

from ..core.tasa_cambio_service import TasaCambioService
from ..models import Producto, Venta, get_session
from ..utils import ahora, formatear_bs
from ..utils import hoy as fecha_hoy
from .widgets import TablaProductos


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

        graficos_layout = QHBoxLayout()
        graficos_layout.setSpacing(15)

        self.grafico_ventas = pg.PlotWidget()
        self.grafico_ventas.setTitle("Ventas Últimos 7 Días", size="12pt")
        self.grafico_ventas.setLabel("left", "Total Bs")
        self.grafico_ventas.setLabel("bottom", "Día")
        self.grafico_ventas.showGrid(x=True, y=True, alpha=0.3)
        self.grafico_ventas.setMinimumHeight(250)
        graficos_layout.addWidget(self.grafico_ventas)

        self.grafico_pagos = pg.PlotWidget()
        self.grafico_pagos.setTitle("Métodos de Pago - Hoy", size="12pt")
        self.grafico_pagos.setLabel("left", "Monto Bs")
        self.grafico_pagos.showGrid(x=True, y=True, alpha=0.3)
        self.grafico_pagos.setMinimumHeight(250)
        graficos_layout.addWidget(self.grafico_pagos)

        layout.addLayout(graficos_layout)

        lbl_stock = QLabel("Productos con Stock Bajo")
        lbl_stock.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(lbl_stock)

        columnas = [
            ("Producto", 150),
            ("Categoria", 100),
            ("Stock Actual", 80),
            ("Stock Minimo", 80),
            ("Estado", 100),
        ]
        self.tabla_stock_bajo = TablaProductos(columnas)
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
                "QFrame { background-color: white; border-radius: 10px; padding: 15px; }",
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
        hoy = ahora()
        desde_hoy = datetime(hoy.year, hoy.month, hoy.day, 0, 0, 0)
        hasta_hoy = datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59)

        with get_session() as session:
            ventas_hoy = session.exec(
                select(Venta).where(
                    Venta.fecha_venta >= desde_hoy,
                    Venta.fecha_venta <= hasta_hoy,
                    Venta.estado == "COMPLETADA",
                ),
            ).all()
            total_ventas_hoy: Decimal = sum((v.total_bs for v in ventas_hoy), start=Decimal())

            productos = session.exec(select(Producto)).all()
            stock_bajo = sum(1 for p in productos if 0 < p.stock_actual <= p.stock_minimo)
            sin_stock = sum(1 for p in productos if p.stock_actual == 0)

            # ADVERTENCIA: tasa_activa() cierra la sesión internamente.
            # tasa.tasa_venta y tasa.fecha son columnas directas (seguras).
            # NO accedas a relaciones lazy de TasaCambio (no tiene, pero igual).
            tasa = self.controlador_tasas.tasa_activa()

            if tasa is None or tasa.fecha < fecha_hoy():
                self.controlador_tasas.obtener_desde_bcv()
                tasa = self.controlador_tasas.tasa_activa()

        self._dashboard_labels["ventas_hoy"].setText(formatear_bs(total_ventas_hoy))
        self._dashboard_labels["stock_bajo"].setText(f"{stock_bajo} productos")
        self._dashboard_labels["sin_stock"].setText(f"{sin_stock} productos")
        self._dashboard_labels["tasa_bcv"].setText(
            formatear_bs(tasa.tasa_venta) if tasa else "Sin tasa",
        )

        self._refrescar_grafico_ventas()
        self._refrescar_grafico_pagos()
        self._refrescar_tabla_stock_bajo()

    def _refrescar_grafico_ventas(self) -> None:
        """Dibuja el grafico de linea: ventas totales de los ultimos 7 dias."""
        hoy = fecha_hoy()
        desde = datetime(hoy.year, hoy.month, hoy.day) - timedelta(days=6)
        hasta = datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59)

        with get_session() as session:
            ventas = session.exec(
                select(Venta).where(
                    Venta.fecha_venta >= desde,
                    Venta.fecha_venta <= hasta,
                    Venta.estado == "COMPLETADA",
                ),
            ).all()

        ventas_por_dia: defaultdict[date, Decimal] = defaultdict(Decimal)
        for v in ventas:
            dia = v.fecha_venta.date()
            ventas_por_dia[dia] += v.total_bs

        dias = [hoy - timedelta(days=i) for i in range(6, -1, -1)]
        valores = [float(ventas_por_dia.get(d, Decimal("0"))) for d in dias]

        self.grafico_ventas.clear()
        self.grafico_ventas.plot(
            list(range(7)),
            valores,
            pen=pg.mkPen(color=(41, 128, 185), width=2),
            symbol="o",
            symbolSize=8,
            symbolBrush=(41, 128, 185),
        )
        ticks = [[(i, d.strftime("%d/%m")) for i, d in enumerate(dias)]]
        self.grafico_ventas.getAxis("bottom").setTicks(ticks)

    def _refrescar_grafico_pagos(self) -> None:
        """Dibuja el grafico de barras: metodos de pago usados hoy."""
        hoy = ahora()
        desde = datetime(hoy.year, hoy.month, hoy.day, 0, 0, 0)
        hasta = datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59)

        with get_session() as session:
            ventas_hoy = session.exec(
                select(Venta).where(
                    Venta.fecha_venta >= desde,
                    Venta.fecha_venta <= hasta,
                    Venta.estado == "COMPLETADA",
                ),
            ).all()

        efectivo = sum(v.efectivo_bs for v in ventas_hoy)
        tarjeta = sum(v.tarjeta for v in ventas_hoy)
        pago_movil = sum(v.pago_movil for v in ventas_hoy)
        bio_pago = sum(v.bio_pago for v in ventas_hoy)

        categorias = ["Efectivo", "Tarjeta", "P.Móvil", "BioPago"]
        montos = [float(efectivo), float(tarjeta), float(pago_movil), float(bio_pago)]
        colores = [
            pg.mkColor(46, 204, 113),
            pg.mkColor(52, 152, 219),
            pg.mkColor(155, 89, 182),
            pg.mkColor(231, 76, 60),
        ]

        self.grafico_pagos.clear()
        barras = pg.BarGraphItem(
            x=range(len(categorias)),
            height=montos,
            width=0.6,
            brushes=colores,
        )
        self.grafico_pagos.addItem(barras)
        ticks = [[(i, cat) for i, cat in enumerate(categorias)]]
        self.grafico_pagos.getAxis("bottom").setTicks(ticks)
        self.grafico_pagos.setYRange(0, max(montos) * 1.15 if montos else 1)

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
