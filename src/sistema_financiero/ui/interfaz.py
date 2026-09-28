from typing import override

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)
from sqlmodel import Session

from ..core.caja_service import CajaService
from ..core.inventario_service import InventarioService
from ..core.producto_controller import ProductoController
from ..core.reporte_service import ReporteService
from ..core.tasa_cambio_service import TasaCambioService
from ..core.venta_controller import VentaController
from ..models import Usuario, engine
from ..utils import ROL_ADMINISTRADOR, formatear_bs
from ..utils.logging_setup import registrar_excepcion
from .dashboard_pagina import DashboardPagina
from .formulario_producto import FormularioProducto
from .formulario_venta import FormularioVenta
from .productos_pagina import ProductosPagina
from .reportes_pagina import ReportesPagina
from .usuarios_pagina import UsuariosPagina
from .ventas_pagina import VentasPagina


# VentanaPrincipal: Ventana principal con menu y paginas.
class VentanaPrincipal(QMainWindow):
    sesion_cerrada = pyqtSignal()

    # Construye la ventana principal con el menu segun el rol del usuario.
    def __init__(self, usuario: Usuario) -> None:
        super().__init__()

        self.usuario_actual = usuario
        self._cierre_autorizado = False
        self.setWindowTitle(
            f"Gestor de Ventas e Inventario — {usuario.nombre_completo or usuario.usuario}"
        )
        self.resize(1024, 680)

        self.controlador_productos = ProductoController()
        self.controlador_inventario = InventarioService()
        self.controlador_tasas = TasaCambioService()
        self.controlador_caja = CajaService(db_session=Session(engine))
        self.controlador_ventas = VentaController(caja_service=self.controlador_caja)
        self.controlador_reportes = ReporteService()

        self.pagina_dashboard: DashboardPagina = DashboardPagina(
            controlador_tasas=self.controlador_tasas,
        )
        self.pagina_productos: ProductosPagina = ProductosPagina(
            controlador_productos=self.controlador_productos,
            controlador_inventario=self.controlador_inventario,
            usuario_actual=usuario,
        )
        self.pagina_ventas: VentasPagina = VentasPagina(
            usuario_actual=usuario,
            controlador_ventas=self.controlador_ventas,
            controlador_productos=self.controlador_productos,
            caja_service=self.controlador_caja,
            reporte_service=self.controlador_reportes,
        )
        self.pagina_reportes: ReportesPagina = ReportesPagina(
            controlador_reportes=self.controlador_reportes,
        )
        self.pagina_usuarios: UsuariosPagina = UsuariosPagina(usuario_actual=usuario)

        if usuario.rol != ROL_ADMINISTRADOR:
            self._items_menu: list[str] = ["Ventas"]
        else:
            self._items_menu = ["Dashboard", "Ventas", "Inventarios", "Reportes", "Usuarios"]
        self._indice_ventas: int = self._items_menu.index("Ventas")

        self._setup_ui()

        self._timer_dashboard = QTimer(self)
        self._timer_dashboard.timeout.connect(self._refrescar_dashboard)
        if "Dashboard" in self._items_menu:
            self._timer_dashboard.start(600_000)

    # Arma la cabecera, la navegacion por rol y el stack de paginas.
    def _setup_ui(self) -> None:
        widget_central = QWidget()
        layout_principal = QVBoxLayout(widget_central)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)

        self.cabecera_aplicacion = self._crear_cabecera_aplicacion()
        layout_principal.addWidget(self.cabecera_aplicacion)

        layout_contenido = QHBoxLayout()
        layout_contenido.setContentsMargins(0, 0, 0, 0)
        layout_contenido.setSpacing(0)

        self.barra_navegacion = QListWidget()
        self.barra_navegacion.setFixedWidth(200)
        fuente_barra = QFont()
        fuente_barra.setPointSize(11)
        self.barra_navegacion.setFont(fuente_barra)
        self.barra_navegacion.setIconSize(QSize(0, 0))
        self.barra_navegacion.setSpacing(5)

        for nombre_item in self._items_menu:
            item = QListWidgetItem(nombre_item)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.barra_navegacion.addItem(item)

        self.barra_navegacion.currentRowChanged.connect(self._cambiar_pagina)
        layout_contenido.addWidget(self.barra_navegacion)

        self.paginas = QStackedWidget()

        creadores = {
            "Dashboard": self._crear_pagina_dashboard,
            "Ventas": self._crear_pagina_ventas,
            "Inventarios": self._crear_pagina_productos,
            "Reportes": self._crear_pagina_reportes,
            "Usuarios": self._crear_pagina_usuarios,
        }
        for nombre in self._items_menu:
            creadores[nombre]()

        layout_contenido.addWidget(self.paginas, 1)
        layout_principal.addLayout(layout_contenido, 1)
        self.setCentralWidget(widget_central)

        barra_estado = QStatusBar()
        self.setStatusBar(barra_estado)
        self._actualizar_indicador_caja()

        self.barra_navegacion.setCurrentRow(0)

    # Header azul oscuro (#1e3a8a) con el nombre del sistema y el usuario.
    def _crear_cabecera_aplicacion(self) -> QFrame:
        """Header azul oscuro (#1e3a8a) con el nombre del sistema y el usuario."""
        cabecera = QFrame()
        cabecera.setProperty("rol", "cabecera_aplicacion")
        cabecera.setFixedHeight(52)

        layout_cabecera = QHBoxLayout(cabecera)
        layout_cabecera.setContentsMargins(20, 0, 20, 0)
        layout_cabecera.setSpacing(8)

        lbl_sistema = QLabel("Gestor de Ventas e Inventario")
        lbl_sistema.setProperty("rol", "cabecera_aplicacion_titulo")
        layout_cabecera.addWidget(lbl_sistema)

        layout_cabecera.addStretch(1)

        lbl_usuario = QLabel(self.usuario_actual.nombre_completo or self.usuario_actual.usuario)
        lbl_usuario.setProperty("rol", "cabecera_aplicacion_usuario")
        layout_cabecera.addWidget(lbl_usuario)

        self.btn_cerrar_sesion = QPushButton("Cerrar Sesion")
        self.btn_cerrar_sesion.setProperty("rol", "cabecera_salir")
        self.btn_cerrar_sesion.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cerrar_sesion.clicked.connect(self._cerrar_sesion)
        layout_cabecera.addWidget(self.btn_cerrar_sesion)

        return cabecera

    # Muestra si la caja esta abierta o cerrada en la barra de estado.
    def _actualizar_indicador_caja(self) -> None:
        """Muestra si la caja esta abierta o cerrada en la barra de estado."""
        caja = self.controlador_caja.obtener_caja_abierta()
        barra = self.statusBar()
        if barra is None:
            return
        if caja:
            estado_caja = f"Caja ABIERTA | Fondo: {formatear_bs(caja.monto_apertura_bs)}"
        else:
            estado_caja = "Caja CERRADA — abra la caja para vender"
        barra.showMessage(
            f"Usuario: {self.usuario_actual.usuario} | "
            f"{self.usuario_actual.nombre_completo} | {estado_caja}",
        )

    # Refresca las tarjetas del dashboard.
    def _refrescar_dashboard(self) -> None:
        self.pagina_dashboard.refrescar()

    # Cambia de pagina y refresca el dashboard o el indicador de caja.
    def _cambiar_pagina(self, indice: int) -> None:
        self.paginas.setCurrentIndex(indice)
        if self.paginas.currentWidget() is self.pagina_dashboard:
            self.pagina_dashboard.refrescar()
        self._actualizar_indicador_caja()

    # Devuelve True si se autoriza cerrar la ventana.
    def _confirmar_cierre(self) -> bool:
        """Devuelve True si se autoriza cerrar la ventana."""
        try:
            caja = self.controlador_caja.obtener_caja_abierta()
        except Exception as e:
            registrar_excepcion(e, "_confirmar_cierre")
            return True

        if caja is None:
            return True

        respuesta = QMessageBox.question(
            self,
            "Caja abierta",
            "La caja del turno esta ABIERTA.\n"
            "Debes cerrar la caja (pagina Ventas) antes de salir.\n\n"
            "¿Salir de todas formas?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            self.barra_navegacion.setCurrentRow(self._indice_ventas)
            return False

        confirmacion = QMessageBox.question(
            self,
            "Confirmar salida",
            "La caja quedara ABIERTA sin cerrar.\n¿Desea salir de todas formas?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return confirmacion == QMessageBox.StandardButton.Yes

    # Confirma, emite sesion_cerrada y cierra la ventana.
    def _cerrar_sesion(self) -> None:
        if self._confirmar_cierre():
            self._cierre_autorizado = True
            self.sesion_cerrada.emit()
            self.close()

    # Acepta el cierre si esta autorizado o aplica la regla de caja abierta.
    @override
    def closeEvent(self, event: QCloseEvent | None) -> None:
        if event is None:
            return
        if self._cierre_autorizado:
            event.accept()
            return
        if self._confirmar_cierre():
            event.accept()
        else:
            event.ignore()

    # Agrega la pagina del dashboard al stack.
    def _crear_pagina_dashboard(self) -> None:
        self.paginas.addWidget(self.pagina_dashboard)

    # Conecta las senales del CRUD y agrega la pagina al stack.
    def _crear_pagina_productos(self) -> None:
        self.pagina_productos.producto_agregar.connect(self._agregar_producto)
        self.pagina_productos.producto_editar.connect(self._editar_producto)
        self.pagina_productos.producto_eliminar.connect(self._eliminar_producto)
        self.paginas.addWidget(self.pagina_productos)

    # Abre el formulario de producto y refresca si se guardo.
    def _agregar_producto(self) -> None:
        dialogo = FormularioProducto(
            self,
            controlador_productos=self.controlador_productos,
            controlador_tasas=self.controlador_tasas,
        )
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.pagina_productos.cargar()

    # Abre el formulario con el producto para editarlo.
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

    # Pide confirmacion y elimina el producto seleccionado.
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
            try:
                self.controlador_productos.eliminar(idproducto)
            except Exception as e:
                registrar_excepcion(e, "_eliminar_producto")
                QMessageBox.critical(
                    self,
                    "Error inesperado",
                    f"No se pudo eliminar el producto.\n{e}",
                )
                return
            self.pagina_productos.cargar()

    # Conecta nueva venta y el cambio de caja; agrega la pagina.
    def _crear_pagina_ventas(self) -> None:
        self.pagina_ventas.nueva_venta.connect(self._nueva_venta)
        self.pagina_ventas.estado_caja_cambio.connect(self._actualizar_indicador_caja)
        self.paginas.addWidget(self.pagina_ventas)

    # Abre el POS si hay caja abierta y refresca tras la venta.
    def _nueva_venta(self) -> None:
        if self.controlador_caja.obtener_caja_abierta() is None:
            QMessageBox.warning(
                self,
                "Caja cerrada",
                "No hay caja abierta.\n"
                "Abra la caja en la pagina de Ventas (panel 'Caja del Turno') "
                "antes de registrar ventas.",
            )
            return

        dialogo = FormularioVenta(
            self,
            controlador_productos=self.controlador_productos,
            controlador_ventas=self.controlador_ventas,
            controlador_tasas=self.controlador_tasas,
            controlador_caja=self.controlador_caja,
            nombre_cajero=self.usuario_actual.nombre_completo or self.usuario_actual.usuario,
        )
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            try:
                self.pagina_ventas.cargar()
                self._actualizar_indicador_caja()
            except Exception as e:
                registrar_excepcion(e, "_nueva_venta (refresco post-venta)")
                QMessageBox.warning(
                    self,
                    "Refresco",
                    "La venta se registro correctamente, pero no se pudo "
                    "actualizar la tabla.\nPulsa 'Refrescar' en la pagina de "
                    "Ventas para verla.",
                )

    # Agrega la pagina de reportes al stack.
    def _crear_pagina_reportes(self) -> None:
        self.paginas.addWidget(self.pagina_reportes)

    # Agrega la pagina de usuarios al stack.
    def _crear_pagina_usuarios(self) -> None:
        self.paginas.addWidget(self.pagina_usuarios)

