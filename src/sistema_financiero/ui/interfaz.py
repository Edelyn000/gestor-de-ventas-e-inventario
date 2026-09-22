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
from typing import override

from PyQt6.QtCore import QSize, Qt, QTimer
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
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

# --- NO TOCAR: importaciones de controladores y paginas.
from sqlmodel import Session

from ..core.caja_service import CajaService
from ..core.inventario_service import InventarioService
from ..core.producto_controller import ProductoController
from ..core.reporte_service import ReporteService
from ..core.tasa_cambio_service import TasaCambioService
from ..core.venta_controller import VentaController
from ..models import Usuario, engine
from ..utils import formatear_bs
from ..utils.logging_setup import registrar_excepcion
from .dashboard_pagina import DashboardPagina
from .formulario_producto import FormularioProducto
from .formulario_venta import FormularioVenta
from .productos_pagina import ProductosPagina
from .reportes_pagina import ReportesPagina
from .usuarios_pagina import UsuariosPagina
from .ventas_pagina import VentasPagina


# ============ VENTANA PRINCIPAL ============
class VentanaPrincipal(QMainWindow):
    # --- NO TOCAR: firma del constructor (recibe el usuario logueado).
    def __init__(self, usuario: Usuario) -> None:
        super().__init__()

        # --- NO TOCAR: almacenamiento del usuario actual.
        self.usuario_actual = usuario
        # --- MODIFICABLE: titulo y tamaño de la ventana principal.
        self.setWindowTitle(f"ABASTO PA' QUE JESUS — {usuario.nombre_completo or usuario.usuario}")
        self.resize(1024, 680)

        # --- NO TOCAR: inicializacion de todos los controladores (core).
        self.controlador_productos = ProductoController()
        self.controlador_inventario = InventarioService()
        self.controlador_tasas = TasaCambioService()
        # CajaService se crea ANTES que VentaController: la venta valida
        # el estado de caja contra esta MISMA instancia (una sola fuente
        # de verdad del estado de caja en toda la app).
        self.controlador_caja = CajaService(db_session=Session(engine))
        self.controlador_ventas = VentaController(caja_service=self.controlador_caja)
        self.controlador_reportes = ReporteService()

        # --- NO TOCAR: creacion de las paginas con sus controladores.
        self.pagina_dashboard: DashboardPagina = DashboardPagina(
            controlador_tasas=self.controlador_tasas,
        )
        # Productos contiene la pestana "Movimientos" (inventario unido aqui).
        self.pagina_productos: ProductosPagina = ProductosPagina(
            controlador_productos=self.controlador_productos,
            controlador_inventario=self.controlador_inventario,
        )
        # La caja esta UNIDA a ventas: el panel "Caja del Turno" vive en la
        # pagina de ventas (abrir/cerrar caja + lista de ventas en un solo
        # lugar). El backend conserva CajaService separado (buena practica),
        # pero la interfaz lo presenta como una sola seccion.
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

        self._setup_ui()

        # --- MODIFICABLE: intervalo de refresco del dashboard (en ms).
        # Timer que refresca el dashboard cada 10 minutos (tasa BCV, ventas, stock).
        self._timer_dashboard = QTimer(self)
        self._timer_dashboard.timeout.connect(self._refrescar_dashboard)
        self._timer_dashboard.start(600_000)  # 600.000 ms = 10 minutos

    # --- MODIFICABLE: layout completo, estilos de la barra de navegacion y fuente.
    def _setup_ui(self) -> None:
        widget_central = QWidget()
        # Layout vertical: barra superior (header) + contenido (navegacion + paginas).
        layout_principal = QVBoxLayout(widget_central)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)

        # --- MODIFICABLE: barra superior del sistema (header azul).
        self.cabecera_aplicacion = self._crear_cabecera_aplicacion()
        layout_principal.addWidget(self.cabecera_aplicacion)

        # Contenedor inferior: navegacion lateral + paginas.
        layout_contenido = QHBoxLayout()
        layout_contenido.setContentsMargins(0, 0, 0, 0)
        layout_contenido.setSpacing(0)

        # --- MODIFICABLE: barra de navegacion lateral (ancho, fuente, estilo).
        self.barra_navegacion = QListWidget()
        self.barra_navegacion.setFixedWidth(200)
        fuente_barra = QFont()
        fuente_barra.setPointSize(11)
        self.barra_navegacion.setFont(fuente_barra)
        self.barra_navegacion.setIconSize(QSize(0, 0))
        self.barra_navegacion.setSpacing(5)

        # --- MODIFICABLE: nombres de los items del menu.
        # "Inventario" se unio a "Productos" (pestana Movimientos).
        items_menu = ["Dashboard", "Ventas", "Productos", "Reportes"]
        if self.usuario_actual.rol == "ADMINISTRADOR":
            items_menu.append("Usuarios")
        for nombre_item in items_menu:
            item = QListWidgetItem(nombre_item)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.barra_navegacion.addItem(item)

        # --- NO TOCAR: conexion de la navegacion.
        self.barra_navegacion.currentRowChanged.connect(self._cambiar_pagina)
        layout_contenido.addWidget(self.barra_navegacion)

        # --- MODIFICABLE: estilo del contenedor de paginas.
        self.paginas = QStackedWidget()

        # --- NO TOCAR: creacion de paginas.
        # El orden de addWidget DEBE coincidir con items_menu.
        self._crear_pagina_dashboard()
        self._crear_pagina_ventas()
        self._crear_pagina_productos()
        self._crear_pagina_reportes()
        self._crear_pagina_usuarios()

        layout_contenido.addWidget(self.paginas, 1)
        layout_principal.addLayout(layout_contenido, 1)
        self.setCentralWidget(widget_central)

        # --- MODIFICABLE: texto de la barra de estado (usuario + estado de caja).
        barra_estado = QStatusBar()
        self.setStatusBar(barra_estado)
        self._actualizar_indicador_caja()

        self.barra_navegacion.setCurrentRow(0)

    # --- MODIFICABLE: barra superior del sistema (titulo + usuario logueado).
    def _crear_cabecera_aplicacion(self) -> QFrame:
        """Header azul oscuro (#1e3a8a) con el nombre del sistema y el usuario."""
        cabecera = QFrame()
        cabecera.setProperty("rol", "cabecera_aplicacion")
        cabecera.setFixedHeight(52)

        layout_cabecera = QHBoxLayout(cabecera)
        layout_cabecera.setContentsMargins(20, 0, 20, 0)
        layout_cabecera.setSpacing(8)

        lbl_sistema = QLabel("ABASTO PA' QUE JESUS")
        lbl_sistema.setProperty("rol", "cabecera_aplicacion_titulo")
        layout_cabecera.addWidget(lbl_sistema)

        layout_cabecera.addStretch(1)

        lbl_usuario = QLabel(self.usuario_actual.nombre_completo or self.usuario_actual.usuario)
        lbl_usuario.setProperty("rol", "cabecera_aplicacion_usuario")
        layout_cabecera.addWidget(lbl_usuario)

        return cabecera

    # --- NO TOCAR: indica el estado actual de la caja en la barra de estado.
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

    # --- NO TOCAR: refresco del dashboard.
    def _refrescar_dashboard(self) -> None:
        self.pagina_dashboard.refrescar()

    # --- NO TOCAR: logica de cambio de pagina.
    def _cambiar_pagina(self, indice: int) -> None:
        self.paginas.setCurrentIndex(indice)
        if indice == 0:
            self.pagina_dashboard.refrescar()
        # Refrescar el estado de caja de la barra de estado en cada navegacion.
        self._actualizar_indicador_caja()

    # --- NO TOCAR: regla de negocio de salida: con caja ABIERTA no se
    # puede salir sin avisar (se permite forzar con doble confirmacion).
    @override
    def closeEvent(self, event: QCloseEvent | None) -> None:
        if event is None:
            return
        try:
            caja = self.controlador_caja.obtener_caja_abierta()
        except Exception as e:
            # Si la consulta falla, NO bloquear la salida: evita quedar
            # atrapado en la app por un error interno.
            registrar_excepcion(e, "closeEvent")
            event.accept()
            return

        if caja is None:
            event.accept()
            return

        respuesta = QMessageBox.question(
            self,
            "Caja abierta",
            "La caja del turno esta ABIERTA.\n"
            "Debes cerrar la caja (pagina Ventas) antes de salir.\n\n"
            "¿Salir de todas formas?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            # Doble confirmacion: forzar la salida deja la caja abierta.
            confirmacion = QMessageBox.question(
                self,
                "Confirmar salida",
                "La caja quedara ABIERTA sin cerrar.\n¿Desea salir de todas formas?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirmacion == QMessageBox.StandardButton.Yes:
                event.accept()
                return
            event.ignore()
            return

        # No quiere forzar la salida: llevarlo a Ventas para cerrar la caja.
        self.barra_navegacion.setCurrentRow(1)
        event.ignore()

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

    # ------------------------------------------------------------------
    # PAGINA: Ventas
    # ------------------------------------------------------------------
    # --- NO TOCAR: conexion de seniales de ventas.
    def _crear_pagina_ventas(self) -> None:
        self.pagina_ventas.nueva_venta.connect(self._nueva_venta)
        # Caja unida a ventas: abrir/cerrar turno refresca la barra de estado.
        self.pagina_ventas.estado_caja_cambio.connect(self._actualizar_indicador_caja)
        self.paginas.addWidget(self.pagina_ventas)

    # --- NO TOCAR: logica de nueva venta (orquesta UI + controlador).
    def _nueva_venta(self) -> None:
        # Regla de negocio: sin caja ABIERTA no se pueden registrar ventas.
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
            self.pagina_ventas.cargar()
            self._actualizar_indicador_caja()

    # ------------------------------------------------------------------
    # PAGINA: Reportes
    # ------------------------------------------------------------------
    # --- NO TOCAR: agregar pagina al stack.
    def _crear_pagina_reportes(self) -> None:
        self.paginas.addWidget(self.pagina_reportes)

    # ------------------------------------------------------------------
    # PAGINA: Usuarios (solo admin)
    # ------------------------------------------------------------------
    def _crear_pagina_usuarios(self) -> None:
        self.paginas.addWidget(self.pagina_usuarios)
