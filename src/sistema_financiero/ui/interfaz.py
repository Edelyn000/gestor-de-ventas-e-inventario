# ============================================================
# ARCHIVO: ui/interfaz.py  (VENTANA PRINCIPAL DE LA APLICACION)
# ============================================================
# VentanaPrincipal: QMainWindow que contiene la barra de
# navegacion lateral (QListWidget) y un QStackedWidget para
# cambiar entre paginas (Dashboard, Productos, Ventas, etc.).
#
# --- NO TOCAR: nombre de la clase (VentanaPrincipal), firma del
#     __init__, creacion de controladores, conexion de seniales,
#     metodos _agregar_producto, _editar_producto, _eliminar_producto,
#     _nueva_venta (orquestan la logica de la app).
# --- MODIFICABLE: estilos, colores, fuentes, textos del menu,
#     tamaño de la ventana, timer de refresco del dashboard.
# ============================================================
from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

# --- NO TOCAR: importaciones de controladores y paginas.
from ..core.inventario_service import InventarioService
from ..core.producto_controller import ProductoController
from ..core.reporte_service import ReporteService
from ..core.tasa_cambio_service import TasaCambioService
from ..core.venta_controller import VentaController
from ..models import Usuario
from .dashboard_pagina import DashboardPagina
from .formulario_producto import FormularioProducto
from .formulario_venta import FormularioVenta
from .inventario_pagina import InventarioPagina
from .productos_pagina import ProductosPagina
from .reportes_pagina import ReportesPagina
from .ventas_pagina import VentasPagina


# ============ VENTANA PRINCIPAL ============
class VentanaPrincipal(QMainWindow):
    # --- NO TOCAR: firma del constructor (recibe el usuario logueado).
    def __init__(self, usuario: Usuario) -> None:
        super().__init__()

        # --- NO TOCAR: almacenamiento del usuario actual.
        self.usuario_actual = usuario
        # --- MODIFICABLE: titulo y tamaño de la ventana principal.
        self.setWindowTitle(f"Sistema Financiero — {usuario.nombre_completo or usuario.usuario}")
        self.resize(1024, 680)

        # --- NO TOCAR: inicializacion de todos los controladores (core).
        self.controlador_productos = ProductoController()
        self.controlador_inventario = InventarioService()
        self.controlador_tasas = TasaCambioService()
        self.controlador_ventas = VentaController()
        self.controlador_reportes = ReporteService()

        # --- NO TOCAR: creacion de las paginas con sus controladores.
        self.pagina_dashboard: DashboardPagina = DashboardPagina(
            controlador_tasas=self.controlador_tasas,
        )
        self.pagina_productos: ProductosPagina = ProductosPagina(self.controlador_productos)
        self.pagina_ventas: VentasPagina = VentasPagina(
            controlador_ventas=self.controlador_ventas,
            controlador_productos=self.controlador_productos,
        )
        self.pagina_inventario: InventarioPagina = InventarioPagina(
            controlador_inventario=self.controlador_inventario,
            controlador_productos=self.controlador_productos,
        )
        self.pagina_reportes: ReportesPagina = ReportesPagina(
            controlador_reportes=self.controlador_reportes,
        )

        self._setup_ui()

        # --- MODIFICABLE: intervalo de refresco del dashboard (en ms).
        # Timer que refresca el dashboard cada 10 minutos (tasa BCV, ventas, stock).
        self._timer_dashboard = QTimer(self)
        self._timer_dashboard.timeout.connect(self._refrescar_dashboard)
        self._timer_dashboard.start(600_000)  # 600.000 ms = 10 minutos

    # --- MODIFICABLE: layout completo, estilos de la barra de navegacion y fuente.
    def _setup_ui(self) -> None:
        widget_central = QWidget()
        layout_principal = QHBoxLayout(widget_central)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)

        # --- MODIFICABLE: barra de navegacion lateral (ancho, fuente, estilo).
        self.barra_navegacion = QListWidget()
        self.barra_navegacion.setFixedWidth(200)
        fuente_barra = QFont()
        fuente_barra.setPointSize(11)
        self.barra_navegacion.setFont(fuente_barra)
        self.barra_navegacion.setStyleSheet("")
        self.barra_navegacion.setIconSize(QSize(0, 0))
        self.barra_navegacion.setSpacing(5)

        # --- MODIFICABLE: nombres de los items del menu.
        items_menu = ["Dashboard", "Productos", "Ventas", "Inventario", "Reportes"]
        for nombre_item in items_menu:
            item = QListWidgetItem(nombre_item)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.barra_navegacion.addItem(item)

        # --- NO TOCAR: conexion de la navegacion.
        self.barra_navegacion.currentRowChanged.connect(self._cambiar_pagina)
        layout_principal.addWidget(self.barra_navegacion)

        # --- MODIFICABLE: estilo del contenedor de paginas.
        self.paginas = QStackedWidget()
        self.paginas.setStyleSheet("")

        # --- NO TOCAR: creacion de paginas.
        self._crear_pagina_dashboard()
        self._crear_pagina_productos()
        self._crear_pagina_ventas()
        self._crear_pagina_inventario()
        self._crear_pagina_reportes()

        layout_principal.addWidget(self.paginas, 1)
        self.setCentralWidget(widget_central)

        # --- MODIFICABLE: texto de la barra de estado.
        barra_estado = QStatusBar()
        self.setStatusBar(barra_estado)
        barra_estado.showMessage(
            f"Usuario: {self.usuario_actual.usuario} | {self.usuario_actual.nombre_completo}",
        )

        self.barra_navegacion.setCurrentRow(0)

    # --- NO TOCAR: refresco del dashboard.
    def _refrescar_dashboard(self) -> None:
        self.pagina_dashboard.refrescar()

    # --- NO TOCAR: logica de cambio de pagina.
    def _cambiar_pagina(self, indice: int) -> None:
        self.paginas.setCurrentIndex(indice)
        if indice == 0:
            self.pagina_dashboard.refrescar()

    # ------------------------------------------------------------------
    # PAGINA: Dashboard
    # ------------------------------------------------------------------
    # --- NO TOCAR: agregar pagina al stack.
    def _crear_pagina_dashboard(self) -> None:
        self.paginas.addWidget(self.pagina_dashboard)

    # ------------------------------------------------------------------
    # PAGINA: Productos
    # ------------------------------------------------------------------
    # --- NO TOCAR: conexion de seniales de productos.
    def _crear_pagina_productos(self) -> None:
        self.pagina_productos.producto_agregar.connect(self._agregar_producto)
        self.pagina_productos.producto_editar.connect(self._editar_producto)
        self.pagina_productos.producto_eliminar.connect(self._eliminar_producto)
        self.paginas.addWidget(self.pagina_productos)

    # --- NO TOCAR: logica de crear/editar/eliminar producto (orquesta UI + controlador).
    def _agregar_producto(self) -> None:
        dialogo = FormularioProducto(
            self,
            controlador_productos=self.controlador_productos,
            controlador_tasas=self.controlador_tasas,
        )
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.pagina_productos.cargar()

    def _editar_producto(self, idproducto: int) -> None:
        producto = self.controlador_productos.obtener_por_id(idproducto)
        if producto is None:
            QMessageBox.warning(self, "Error", "El producto ya no existe en la BD.")
            return

        dialogo = FormularioProducto(
            self,
            producto=producto,
            controlador_productos=self.controlador_productos,
            controlador_tasas=self.controlador_tasas,
        )
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.pagina_productos.cargar()

    def _eliminar_producto(self, idproducto: int) -> None:
        producto = self.controlador_productos.obtener_por_id(idproducto)
        if producto is None:
            QMessageBox.warning(self, "Error", "El producto ya no existe.")
            return

        respuesta = QMessageBox.question(
            self,
            "Confirmar eliminacion",
            f"Seguro que deseas eliminar '{producto.nombre_producto}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if respuesta == QMessageBox.StandardButton.Yes:
            self.controlador_productos.eliminar(idproducto)
            self.pagina_productos.cargar()

    # ------------------------------------------------------------------
    # PAGINA: Ventas
    # ------------------------------------------------------------------
    # --- NO TOCAR: conexion de seniales de ventas.
    def _crear_pagina_ventas(self) -> None:
        self.pagina_ventas.nueva_venta.connect(self._nueva_venta)
        self.paginas.addWidget(self.pagina_ventas)

    # --- NO TOCAR: logica de nueva venta (orquesta UI + controlador).
    def _nueva_venta(self) -> None:
        dialogo = FormularioVenta(
            self,
            controlador_productos=self.controlador_productos,
            controlador_ventas=self.controlador_ventas,
            controlador_tasas=self.controlador_tasas,
        )
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.pagina_ventas.cargar()

    # ------------------------------------------------------------------
    # PAGINA: Inventario
    # ------------------------------------------------------------------
    # --- NO TOCAR: agregar pagina al stack.
    def _crear_pagina_inventario(self) -> None:
        self.paginas.addWidget(self.pagina_inventario)

    # ------------------------------------------------------------------
    # PAGINA: Reportes
    # ------------------------------------------------------------------
    # --- NO TOCAR: agregar pagina al stack.
    def _crear_pagina_reportes(self) -> None:
        self.paginas.addWidget(self.pagina_reportes)
