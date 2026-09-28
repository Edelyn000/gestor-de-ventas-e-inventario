from datetime import datetime
from decimal import Decimal
from typing import cast

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QColor
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
from ..models import Producto, TasaCambio, Venta, obtener_sesion
from ..utils import ahora, formatear_bs, formatear_stock
from ..utils import hoy as fecha_hoy
from ..utils.fecha import rango_dia_utc
from ..utils.logging_setup import registrar_excepcion
from .widgets import TablaProductos, TituloPagina

INTERVALO_BCV_SEGUNDOS = 600


# BcvFetchThread: Hilo de consulta de la tasa BCV en segundo plano.
class BcvFetchThread(QThread):
    tasa_obtenida = pyqtSignal(object)

    # Configura el hilo con el servicio de tasas a consultar.
    def __init__(self, servicio: TasaCambioService) -> None:
        super().__init__()
        self._servicio = servicio

    # Consulta la tasa BCV en segundo plano y emite el resultado.
    def run(self) -> None:
        try:
            tasa = self._servicio.obtener_desde_bcv()
        except Exception as e:  # pragma: no cover - red externa, cualquier fallo
            registrar_excepcion(e, "BcvFetchThread.run (consulta BCV)")
            tasa = None
        self.tasa_obtenida.emit(tasa)


# DashboardPagina: Resumen del dia con tarjetas y tasa BCV.
class DashboardPagina(QWidget):
    """Pagina de inicio con resumen y alertas de stock."""

    # Construye el dashboard y deja el fetch BCV inactivo.
    def __init__(self, controlador_tasas: TasaCambioService) -> None:
        super().__init__()
        self.controlador_tasas = controlador_tasas
        self._bcv_fetching = False
        self._bcv_thread: BcvFetchThread | None = None
        self._ultima_consulta_bcv: datetime | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        layout.addWidget(TituloPagina("Dashboard"))

        layout.addLayout(self._crear_tarjetas_resumen())

        lbl_stock = QLabel("Productos con Stock Bajo")
        lbl_stock.setProperty("rol", "seccion")
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

    # Crea las 4 tarjetas de resumen: Ventas Hoy, Stock Bajo, Sin Stock, Tasa BCV.
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

        acentos = {
            "ventas_hoy": "azul",
            "stock_bajo": "naranja",
            "sin_stock": "rojo",
            "tasa_bcv": "verde",
        }

        for clave, titulo, _icono in datos_tarjetas:
            tarjeta = QFrame()
            tarjeta.setProperty("rol", "tarjeta")
            tarjeta.setProperty("acento", acentos[clave])
            tarjeta.setMinimumHeight(100)

            layout_tarjeta = QVBoxLayout(tarjeta)
            layout_tarjeta.setContentsMargins(10, 10, 10, 10)
            layout_tarjeta.setSpacing(5)

            lbl_titulo_tarjeta = QLabel(titulo)
            lbl_titulo_tarjeta.setProperty("rol", "titulo_tarjeta")
            layout_tarjeta.addWidget(lbl_titulo_tarjeta)

            lbl_valor = QLabel("—")
            lbl_valor.setProperty("rol", "valor_tarjeta")
            layout_tarjeta.addWidget(lbl_valor)

            self._dashboard_labels[clave] = lbl_valor
            fila_tarjetas.addWidget(tarjeta)

        return fila_tarjetas

    # Refresca todos los datos del dashboard (tarjetas, grafico, tabla).
    def refrescar(self) -> None:
        """Refresca todos los datos del dashboard (tarjetas, grafico, tabla)."""
        desde_hoy, hasta_hoy = rango_dia_utc(fecha_hoy())

        with obtener_sesion() as session:
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

            tasa = self.controlador_tasas.tasa_activa()

            tasa_obsoleta = tasa is None or tasa.fecha < fecha_hoy()
            expiro_intervalo = (
                self._ultima_consulta_bcv is None
                or (ahora() - self._ultima_consulta_bcv).total_seconds() >= INTERVALO_BCV_SEGUNDOS
            )
            if not self._bcv_fetching and (tasa_obsoleta or expiro_intervalo):
                self._bcv_fetching = True
                self._ultima_consulta_bcv = ahora()
                self._dashboard_labels["tasa_bcv"].setText("Consultando...")
                self._iniciar_fetch_bcv()

        self._dashboard_labels["ventas_hoy"].setText(formatear_bs(total_ventas_hoy))
        self._dashboard_labels["stock_bajo"].setText(f"{stock_bajo} productos")
        self._dashboard_labels["sin_stock"].setText(f"{sin_stock} productos")
        if tasa:
            self._dashboard_labels["tasa_bcv"].setText(formatear_bs(tasa.tasa_venta))

        self._refrescar_tabla_stock_bajo()

    # Lanza el hilo que consulta el BCV y lo conecta con el refresco.
    def _iniciar_fetch_bcv(self) -> None:
        self._bcv_thread = BcvFetchThread(self.controlador_tasas)
        self._bcv_thread.tasa_obtenida.connect(self._bcv_fetch_completado)
        self._bcv_thread.finished.connect(self._bcv_thread.deleteLater)
        self._bcv_thread.start()

    # Marca el fin del fetch y muestra la tasa o el estado de error.
    def _bcv_fetch_completado(self, tasa: object) -> None:
        self._bcv_fetching = False
        if tasa is not None:
            tasa_cambio = cast(TasaCambio, tasa)
            self._dashboard_labels["tasa_bcv"].setText(
                formatear_bs(tasa_cambio.tasa_venta),
            )
        else:
            self._dashboard_labels["tasa_bcv"].setText("Sin tasa (error)")

    # Llena la tabla de productos con stock bajo/sin stock.
    def _refrescar_tabla_stock_bajo(self) -> None:
        """Llena la tabla de productos con stock bajo/sin stock."""
        with obtener_sesion() as session:
            todos = session.exec(select(Producto)).all()
            productos_alerta = [p for p in todos if p.stock_actual <= p.stock_minimo]

        self.tabla_stock_bajo.setRowCount(len(productos_alerta))
        for fila, prod in enumerate(productos_alerta):
            self.tabla_stock_bajo.setItem(fila, 0, QTableWidgetItem(prod.nombre_producto))
            self.tabla_stock_bajo.setItem(
                fila, 1, QTableWidgetItem(prod.categoria.nombre if prod.categoria else "")
            )
            stock_act = formatear_stock(prod.stock_actual)
            stock_min = formatear_stock(prod.stock_minimo)
            self.tabla_stock_bajo.setItem(fila, 2, QTableWidgetItem(stock_act))
            self.tabla_stock_bajo.setItem(fila, 3, QTableWidgetItem(stock_min))
            estado = "SIN STOCK" if prod.stock_actual == 0 else "STOCK BAJO"
            item_estado = QTableWidgetItem(estado)
            item_estado.setForeground(
                QColor("#dc2626") if estado == "SIN STOCK" else QColor("#d97706"),
            )
            self.tabla_stock_bajo.setItem(fila, 4, item_estado)

        self.tabla_stock_bajo.resizeColumnsToContents()

