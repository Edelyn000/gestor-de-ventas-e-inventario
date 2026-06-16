
from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from ..core.inventario_service import InventarioService
from ..core.producto_controller import ProductoController
from ..core.reporte_service import ReporteService
from ..core.tasa_cambio_service import TasaCambioService
from ..core.venta_controller import VentaController
from ..models import Usuario
from .dashboard_pagina import DashboardPagina
from .formulario_cambio_contrasena import FormularioCambioContrasena
from .formulario_producto import FormularioProducto
from .formulario_venta import FormularioVenta
from .inventario_pagina import InventarioPagina
from .productos_pagina import ProductosPagina
from .reportes_pagina import ReportesPagina
from .ventas_pagina import VentasPagina


class MainWindow(QMainWindow):
    def __init__(self, usuario: Usuario) -> None:
        super().__init__()

        self.usuario_actual = usuario
        self.setWindowTitle(f"Sistema Financiero — {usuario.nombre_completo or usuario.usuario}")
        self.resize(1024, 680)

        self.controlador_productos = ProductoController()
        self.controlador_inventario = InventarioService()
        self.controlador_tasas = TasaCambioService()
        self.controlador_ventas = VentaController()
        self.controlador_reportes = ReporteService()

        # Crear paginas ANTES de _setup_ui para que Pylance conozca los tipos.
        self.pagina_dashboard = DashboardPagina(controlador_tasas=self.controlador_tasas)
        self.pagina_productos = ProductosPagina(self.controlador_productos)
        self.pagina_ventas = VentasPagina(
            controlador_ventas=self.controlador_ventas,
            controlador_productos=self.controlador_productos,
        )
        self.pagina_inventario = InventarioPagina(
            controlador_inventario=self.controlador_inventario,
            controlador_productos=self.controlador_productos,
        )
        self.pagina_reportes = ReportesPagina(
            controlador_reportes=self.controlador_reportes,
        )

        self._setup_ui()

        # Timer que refresca el dashboard cada 10 minutos (tasa BCV, ventas, stock).
        # No molesta al usuario porque actualiza solo los widgets, no bloquea la UI.
        self._timer_dashboard = QTimer(self)
        self._timer_dashboard.timeout.connect(self._refrescar_dashboard)
        self._timer_dashboard.start(600_000)  # 600.000 ms = 10 minutos

    def _setup_ui(self) -> None:
        widget_central = QWidget()
        layout_principal = QHBoxLayout(widget_central)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)

        self.barra_navegacion = QListWidget()
        self.barra_navegacion.setFixedWidth(200)
        fuente_barra = QFont()
        fuente_barra.setPointSize(11)
        self.barra_navegacion.setFont(fuente_barra)
        self.barra_navegacion.setStyleSheet("background-color: #1a1a2e; color: white;")
        self.barra_navegacion.setIconSize(QSize(0, 0))
        self.barra_navegacion.setSpacing(5)

        items_menu = ["Dashboard", "Productos", "Ventas", "Inventario", "Reportes"]
        for nombre_item in items_menu:
            item = QListWidgetItem(nombre_item)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.barra_navegacion.addItem(item)

        self.barra_navegacion.currentRowChanged.connect(self._cambiar_pagina)
        layout_principal.addWidget(self.barra_navegacion)

        self.paginas = QStackedWidget()
        self.paginas.setStyleSheet("background-color: #f5f5f5;")

        self._crear_pagina_dashboard()
        self._crear_pagina_productos()
        self._crear_pagina_ventas()
        self._crear_pagina_inventario()
        self._crear_pagina_reportes()

        layout_principal.addWidget(self.paginas, 1)
        self.setCentralWidget(widget_central)

        barra_estado = QStatusBar()
        self.setStatusBar(barra_estado)
        barra_estado.showMessage(
            f"Usuario: {self.usuario_actual.usuario} | {self.usuario_actual.nombre_completo}"
        )

        # Boton para cambiar contrasena / usuario desde la barra de estado.
        btn_cambio = QPushButton("Cambiar Contraseña")
        btn_cambio.setStyleSheet("padding: 4px 10px;")
        btn_cambio.clicked.connect(self._abrir_cambio_contrasena)
        barra_estado.addPermanentWidget(btn_cambio)

        self.barra_navegacion.setCurrentRow(0)

    def _refrescar_dashboard(self) -> None:
        self.pagina_dashboard.refrescar()

    def _cambiar_pagina(self, indice: int) -> None:
        # Cambiar la pagina visible.
        self.paginas.setCurrentIndex(indice)
        # Refrescar datos del dashboard cada vez que el usuario navega a el.
        # Esto asegura que al abrir la app o volver al inicio, los numeros
        # y la tasa BCV esten actualizados.
        if indice == 0:
            self.pagina_dashboard.refrescar()

    def _abrir_cambio_contrasena(self) -> None:
        """Abre el dialogo para cambiar contrasena / usuario."""
        dialogo = FormularioCambioContrasena(self, usuario=self.usuario_actual)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            # Actualizar el titulo de la ventana si cambio el nombre.
            self.setWindowTitle(
                f"Sistema Financiero — "
                f"{self.usuario_actual.nombre_completo or self.usuario_actual.usuario}"
            )
            # Actualizar el mensaje de la barra de estado.
            self.statusBar().showMessage(  # type: ignore[union-attr]
                f"Usuario: {self.usuario_actual.usuario} | "
                f"{self.usuario_actual.nombre_completo}"
            )

    # ------------------------------------------------------------------
    # PAGINA: Dashboard
    # ------------------------------------------------------------------
    def _crear_pagina_dashboard(self) -> None:
        self.paginas.addWidget(self.pagina_dashboard)

    # ------------------------------------------------------------------
    # PAGINA: Productos
    # ------------------------------------------------------------------
    def _crear_pagina_productos(self) -> None:
        self.pagina_productos.producto_agregar.connect(self._agregar_producto)
        self.pagina_productos.producto_editar.connect(self._editar_producto)
        self.pagina_productos.producto_eliminar.connect(self._eliminar_producto)
        self.paginas.addWidget(self.pagina_productos)

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
    def _crear_pagina_ventas(self) -> None:
        self.pagina_ventas.nueva_venta.connect(self._nueva_venta)
        self.paginas.addWidget(self.pagina_ventas)

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
    def _crear_pagina_inventario(self) -> None:
        self.paginas.addWidget(self.pagina_inventario)

    # ------------------------------------------------------------------
    # PAGINA: Reportes
    # ------------------------------------------------------------------
    def _crear_pagina_reportes(self) -> None:
        self.paginas.addWidget(self.pagina_reportes)
