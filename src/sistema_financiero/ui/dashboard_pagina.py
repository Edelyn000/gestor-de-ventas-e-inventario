# ============================================================
# ARCHIVO: ui/dashboard_pagina.py  (PAGINA DE INICIO / DASHBOARD)
# ============================================================
# Widget principal de la pantalla de inicio. Muestra:
#   1. Tarjetas de resumen (Ventas Hoy, Stock Bajo, Sin Stock, Tasa BCV).
#   2. Tabla de productos con stock bajo/alerta.
#   3. Hilo separado (QThread) para consultar la tasa BCV sin congelar la UI.
#
# --- NO TOCAR: BcvFetchThread (hilo para consulta BCV asincrona).
# --- MODIFICABLE: estilos, colores, fuentes, textos de tarjetas y tabla.
# ============================================================
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

# --- NO TOCAR: importaciones de logica de negocio y modelos.
from ..core.tasa_cambio_service import TasaCambioService
from ..models import Producto, TasaCambio, Venta, obtener_sesion
from ..utils import ahora, formatear_bs, formatear_stock
from ..utils import hoy as fecha_hoy
from .widgets import TablaProductos, TituloPagina


# ============ HILO PARA CONSULTA BCV ASINCRONA ============
# --- NO TOCAR: logica del hilo (core del sistema).
class BcvFetchThread(QThread):
    tasa_obtenida = pyqtSignal(object)

    def __init__(self, servicio: TasaCambioService) -> None:
        super().__init__()
        self._servicio = servicio

    def run(self) -> None:
        tasa = self._servicio.obtener_desde_bcv()
        self.tasa_obtenida.emit(tasa)


# ============ PAGINA PRINCIPAL DEL DASHBOARD ============
class DashboardPagina(QWidget):
    """Pagina de inicio con resumen y alertas de stock."""

    # --- NO TOCAR: firma del constructor (recibe controlador de tasas).
    def __init__(self, controlador_tasas: TasaCambioService) -> None:
        super().__init__()
        # --- NO TOCAR: variables de estado del dashboard.
        self.controlador_tasas = controlador_tasas
        self._bcv_fetching = False
        self._bcv_thread: BcvFetchThread | None = None

        # --- MODIFICABLE: layout, margenes, espaciado.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # [Titulo del dashboard]
        # --- MODIFICABLE: texto del titulo (tarjeta con barra lateral).
        layout.addWidget(TituloPagina("Dashboard"))

        # [Tarjetas de resumen numerico]
        layout.addLayout(self._crear_tarjetas_resumen())

        # [Seccion de productos con stock bajo]
        # --- MODIFICABLE: texto, estilo de la etiqueta.
        lbl_stock = QLabel("Productos con Stock Bajo")
        lbl_stock.setProperty("rol", "seccion")
        layout.addWidget(lbl_stock)

        # --- MODIFICABLE: columnas, anchos de la tabla de stock bajo.
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

    # --- MODIFICABLE: contenido, estilos, colores y textos de las tarjetas.
    def _crear_tarjetas_resumen(self) -> QHBoxLayout:
        """Crea las 4 tarjetas de resumen: Ventas Hoy, Stock Bajo, Sin Stock, Tasa BCV."""
        fila_tarjetas = QHBoxLayout()
        fila_tarjetas.setSpacing(15)

        # [Definicion de las tarjetas: clave interna, etiqueta visible, icono]
        datos_tarjetas = [
            ("ventas_hoy", "Ventas Hoy", ""),
            ("stock_bajo", "Stock Bajo", ""),
            ("sin_stock", "Sin Stock", ""),
            ("tasa_bcv", "Tasa BCV", ""),
        ]

        self._dashboard_labels = {}

        # [Acento por tarjeta: guia visual del tipo de dato (ver ui/estilos.py)]
        acentos = {
            "ventas_hoy": "azul",
            "stock_bajo": "naranja",
            "sin_stock": "rojo",
            "tasa_bcv": "verde",
        }

        for clave, titulo, _icono in datos_tarjetas:
            tarjeta = QFrame()
            # --- MODIFICABLE: estilo de la tarjeta (borde, fondo) en ui/estilos.py.
            tarjeta.setProperty("rol", "tarjeta")
            tarjeta.setProperty("acento", acentos[clave])
            tarjeta.setMinimumHeight(100)

            layout_tarjeta = QVBoxLayout(tarjeta)
            layout_tarjeta.setContentsMargins(10, 10, 10, 10)
            layout_tarjeta.setSpacing(5)

            # --- MODIFICABLE: texto y color del titulo de la tarjeta.
            lbl_titulo_tarjeta = QLabel(titulo)
            lbl_titulo_tarjeta.setProperty("rol", "titulo_tarjeta")
            layout_tarjeta.addWidget(lbl_titulo_tarjeta)

            # --- MODIFICABLE: estilo del valor numerico.
            lbl_valor = QLabel("—")
            lbl_valor.setProperty("rol", "valor_tarjeta")
            layout_tarjeta.addWidget(lbl_valor)

            self._dashboard_labels[clave] = lbl_valor
            fila_tarjetas.addWidget(tarjeta)

        return fila_tarjetas

    # --- NO TOCAR: logica de actualizacion del dashboard (consulta BD, tasa BCV).
    def refrescar(self) -> None:
        """Refresca todos los datos del dashboard (tarjetas, grafico, tabla)."""
        hoy = ahora()
        desde_hoy = datetime(hoy.year, hoy.month, hoy.day, 0, 0, 0)
        hasta_hoy = datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59)

        # --- NO TOCAR: consulta de ventas del dia.
        with obtener_sesion() as session:
            ventas_hoy = session.exec(
                select(Venta).where(
                    Venta.fecha_venta >= desde_hoy,
                    Venta.fecha_venta <= hasta_hoy,
                    Venta.estado == "COMPLETADA",
                ),
            ).all()
            total_ventas_hoy: Decimal = sum((v.total_bs for v in ventas_hoy), start=Decimal())

            # [Calculo de productos con stock bajo y sin stock]
            productos = session.exec(select(Producto)).all()
            stock_bajo = sum(1 for p in productos if 0 < p.stock_actual <= p.stock_minimo)
            sin_stock = sum(1 for p in productos if p.stock_actual == 0)

            # --- NO TOCAR: obtencion de tasa activa (consulta a BD).
            # ADVERTENCIA: tasa_activa() cierra la sesión internamente.
            # tasa.tasa_venta y tasa.fecha son columnas directas (seguras).
            # NO accedas a relaciones lazy de TasaCambio (no tiene, pero igual).
            tasa = self.controlador_tasas.tasa_activa()

            # [Si no hay tasa hoy, inicia consulta asincrona al BCV]
            if (tasa is None or tasa.fecha < fecha_hoy()) and not self._bcv_fetching:
                self._bcv_fetching = True
                self._dashboard_labels["tasa_bcv"].setText("Consultando...")
                self._iniciar_fetch_bcv()

        # [Actualiza labels con los valores calculados]
        self._dashboard_labels["ventas_hoy"].setText(formatear_bs(total_ventas_hoy))
        self._dashboard_labels["stock_bajo"].setText(f"{stock_bajo} productos")
        self._dashboard_labels["sin_stock"].setText(f"{sin_stock} productos")
        if tasa:
            self._dashboard_labels["tasa_bcv"].setText(formatear_bs(tasa.tasa_venta))

        self._refrescar_tabla_stock_bajo()

    # --- NO TOCAR: logica de hilo asincrono para consulta BCV.
    def _iniciar_fetch_bcv(self) -> None:
        self._bcv_thread = BcvFetchThread(self.controlador_tasas)
        self._bcv_thread.tasa_obtenida.connect(self._bcv_fetch_completado)
        self._bcv_thread.finished.connect(self._bcv_thread.deleteLater)
        self._bcv_thread.start()

    # --- NO TOCAR: callback de actualizacion de tasa al recibir respuesta.
    def _bcv_fetch_completado(self, tasa: object) -> None:
        self._bcv_fetching = False
        if tasa is not None:
            tasa_cambio = cast(TasaCambio, tasa)
            self._dashboard_labels["tasa_bcv"].setText(
                formatear_bs(tasa_cambio.tasa_venta),
            )
        else:
            # --- MODIFICABLE: mensaje de error si falla la consulta.
            self._dashboard_labels["tasa_bcv"].setText("Sin tasa (error)")

    # --- NO TOCAR: logica de consulta a BD para productos con stock bajo.
    def _refrescar_tabla_stock_bajo(self) -> None:
        """Llena la tabla de productos con stock bajo/sin stock."""
        with obtener_sesion() as session:
            todos = session.exec(select(Producto)).all()
            productos_alerta = [p for p in todos if p.stock_actual <= p.stock_minimo]

        # --- MODIFICABLE: llenado de la tabla (formato de datos, columnas).
        self.tabla_stock_bajo.setRowCount(len(productos_alerta))
        for fila, prod in enumerate(productos_alerta):
            self.tabla_stock_bajo.setItem(fila, 0, QTableWidgetItem(prod.nombre_producto))
            self.tabla_stock_bajo.setItem(fila, 1, QTableWidgetItem(prod.categoria or ""))
            stock_act = formatear_stock(prod.stock_actual)
            stock_min = formatear_stock(prod.stock_minimo)
            self.tabla_stock_bajo.setItem(fila, 2, QTableWidgetItem(stock_act))
            self.tabla_stock_bajo.setItem(fila, 3, QTableWidgetItem(stock_min))
            estado = "SIN STOCK" if prod.stock_actual == 0 else "STOCK BAJO"
            item_estado = QTableWidgetItem(estado)
            # --- MODIFICABLE: color del estado (sin stock rojo, stock bajo naranja).
            item_estado.setForeground(
                QColor("#dc2626") if estado == "SIN STOCK" else QColor("#d97706"),
            )
            self.tabla_stock_bajo.setItem(fila, 4, item_estado)

        self.tabla_stock_bajo.resizeColumnsToContents()
