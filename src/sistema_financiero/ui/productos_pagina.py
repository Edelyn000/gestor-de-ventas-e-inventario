# ============================================================
# ARCHIVO: ui/productos_pagina.py  (PAGINA DE GESTION DE PRODUCTOS)
# ============================================================
# Widget independiente para la pagina de Productos (CRUD completo).
#
# QUE MUESTRA (pestanas, decision del usuario 2026-09-21):
#   1. Pestana "Catalogo": barra superior (buscador + botones Agregar,
#      Editar, Eliminar, Refrescar) + tabla con todos los productos.
#   2. Pestana "Movimientos": InventarioPagina embebida (entradas, salidas
#      y ajustes de stock) — la pagina "Inventario" del menu se unio aqui.
#   3. Doble clic en una fila → emite senial para editar.
#
# SENIALES (para que VentanaPrincipal maneje):
#   - producto_agregar: el usuario quiere crear un producto.
#   - producto_editar(id): el usuario quiere editar un producto.
#   - producto_eliminar(id): el usuario quiere eliminar un producto.
#
# --- NO TOCAR: nombre de la clase (ProductosPagina), las 3 seniales
#     (pyqtSignal), metodo cargar(), _emitir_editar, _emitir_eliminar.
# --- MODIFICABLE: estilos, colores, fuentes, tamanos, columnas y anchos,
#     textos del buscador y botones, logica de _buscar_producto().
# ============================================================
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.inventario_service import InventarioService
from ..core.producto_controller import ProductoController
from ..utils import formatear_bs, formatear_stock, formatear_usd
from .inventario_pagina import InventarioPagina
from .widgets import CampoBusqueda, TablaProductos, TituloPagina


# ============ PAGINA DE PRODUCTOS ============
class ProductosPagina(QWidget):
    """Pagina de gestion de productos (Catalogo) + movimientos (Inventario)."""

    # --- NO TOCAR: seniales que conecta VentanaPrincipal.
    producto_agregar = pyqtSignal()
    producto_editar = pyqtSignal(int)
    producto_eliminar = pyqtSignal(int)

    def __init__(
        self,
        controlador_productos: ProductoController,
        controlador_inventario: InventarioService | None = None,
    ) -> None:
        super().__init__()

        self.controlador_productos = controlador_productos
        self.controlador_inventario = controlador_inventario
        # Se rellena abajo si controlador_inventario no es None.
        self.pagina_inventario: InventarioPagina | None = None

        # --- MODIFICABLE: layout, margenes.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        # [Titulo]
        # --- MODIFICABLE: texto del titulo (tarjeta con barra lateral).
        layout.addWidget(TituloPagina("Productos"))

        # [Pestanas: Catalogo (CRUD) + Movimientos (inventario)]
        self.pestanas = QTabWidget()
        layout.addWidget(self.pestanas, 1)

        # ----------------------------------------------------------
        # Pestana 1: Catalogo de productos
        # ----------------------------------------------------------
        pestana_catalogo = QWidget()
        catalogo_layout = QVBoxLayout(pestana_catalogo)
        catalogo_layout.setContentsMargins(0, 15, 0, 0)

        # [Barra de herramientas: buscador + botones]
        # --- MODIFICABLE: textos, placeholders, estilos de botones.
        barra = QHBoxLayout()

        self.txt_buscar_producto = CampoBusqueda(
            placeholder="Buscar producto por nombre o categoria...",
        )
        self.txt_buscar_producto.textChanged.connect(self._buscar_producto)
        barra.addWidget(self.txt_buscar_producto, 1)

        btn_refrescar = QPushButton("Refrescar")
        btn_refrescar.clicked.connect(self.cargar)
        barra.addWidget(btn_refrescar)

        btn_agregar = QPushButton("Agregar")
        # --- NO TOCAR: emite senial para VentanaPrincipal.
        btn_agregar.setProperty("rol", "primario")
        btn_agregar.clicked.connect(self.producto_agregar.emit)
        barra.addWidget(btn_agregar)

        btn_editar = QPushButton("Editar")
        btn_editar.setProperty("rol", "secundario")
        btn_editar.clicked.connect(self._emitir_editar)
        barra.addWidget(btn_editar)

        btn_eliminar = QPushButton("Eliminar")
        btn_eliminar.setProperty("rol", "peligro")
        btn_eliminar.clicked.connect(self._emitir_eliminar)
        barra.addWidget(btn_eliminar)

        catalogo_layout.addLayout(barra)
        catalogo_layout.addSpacing(10)

        # [Tabla de productos]
        # --- MODIFICABLE: columnas y anchos.
        columnas = [
            ("ID", 50),
            ("Nombre", 200),
            ("Categoria", 120),
            ("Precio Bs", 100),
            ("Precio USD", 100),
            ("Stock", 70),
            ("Stock Min", 70),
            ("Unidad", 60),
            ("Tipo Venta", 80),
        ]
        self.tabla_productos = TablaProductos(columnas)

        # --- NO TOCAR: doble clic emite senial de editar.
        self.tabla_productos.cellDoubleClicked.connect(self._emitir_editar)

        catalogo_layout.addWidget(self.tabla_productos, 1)

        self.pestanas.addTab(pestana_catalogo, "Catálogo")

        # ----------------------------------------------------------
        # Pestana 2: Movimientos de inventario (embebida)
        # ----------------------------------------------------------
        if controlador_inventario is not None:
            self.pagina_inventario = InventarioPagina(
                controlador_inventario=controlador_inventario,
                controlador_productos=controlador_productos,
                mostrar_titulo=False,
            )
            self.pestanas.addTab(self.pagina_inventario, "Movimientos")
            # Al entrar a la pestana de movimientos, refrescar combo + historial
            # (evita ver datos viejos tras operaciones en el catalogo).
            self.pestanas.currentChanged.connect(self._al_cambiar_pestana)

        # --- NO TOCAR: carga inicial de datos.
        self.cargar()

    # --- Refresca la pestana visible cuando el usuario cambia de pestaña.
    def _al_cambiar_pestana(self, indice: int) -> None:
        if indice == 1 and self.pagina_inventario is not None:
            self.pagina_inventario.refrescar_pestana()

    # --- NO TOCAR: metodos de emision de seniales (VentanaPrincipal las maneja).
    def _obtener_fila_seleccionada(self) -> tuple[int, int | None]:
        fila = self.tabla_productos.currentRow()
        if fila < 0:
            return -1, None
        item_id = self.tabla_productos.item(fila, 0)
        if item_id is None:
            return -1, None
        return fila, int(item_id.text())

    def _emitir_editar(self) -> None:
        _fila, idproducto = self._obtener_fila_seleccionada()
        if idproducto is not None:
            self.producto_editar.emit(idproducto)

    def _emitir_eliminar(self) -> None:
        _fila, idproducto = self._obtener_fila_seleccionada()
        if idproducto is not None:
            self.producto_eliminar.emit(idproducto)

    # --- NO TOCAR: logica de carga de productos desde la BD.
    # --- MODIFICABLE: formato de los datos en la tabla.
    def cargar(self) -> None:
        """Carga todos los productos desde la BD a la tabla."""
        # ADVERTENCIA: listar_todos() cierra la sesión. Solo columnas directas.
        productos = self.controlador_productos.listar_todos()

        self.tabla_productos.setRowCount(len(productos))
        for fila, producto in enumerate(productos):
            self.tabla_productos.setItem(fila, 0, QTableWidgetItem(str(producto.idproducto)))
            item_nombre = QTableWidgetItem(producto.nombre_producto)
            self.tabla_productos.setItem(fila, 1, item_nombre)
            categoria = producto.categoria or "-"
            self.tabla_productos.setItem(fila, 2, QTableWidgetItem(categoria))
            self.tabla_productos.setItem(
                fila,
                3,
                QTableWidgetItem(formatear_bs(producto.precio_venta_bs)),
            )
            self.tabla_productos.setItem(
                fila,
                4,
                QTableWidgetItem(formatear_usd(producto.precio_venta_usd)),
            )
            stock_act = formatear_stock(producto.stock_actual)
            stock_min = formatear_stock(producto.stock_minimo)
            self.tabla_productos.setItem(fila, 5, QTableWidgetItem(stock_act))
            self.tabla_productos.setItem(fila, 6, QTableWidgetItem(stock_min))
            self.tabla_productos.setItem(fila, 7, QTableWidgetItem(producto.unidad))
            self.tabla_productos.setItem(
                fila,
                8,
                QTableWidgetItem(producto.tipo_venta or "UNIDAD"),
            )

        # Mantener el combo de movimientos sincronizado con el catalogo.
        if self.pagina_inventario is not None:
            self.pagina_inventario.refrescar_combo()

    # --- MODIFICABLE: logica de filtrado de productos (texto de busqueda).
    def _buscar_producto(self, texto: str) -> None:
        """Filtra la tabla de productos mientras el usuario escribe."""
        texto = texto.strip()
        if not texto:
            self.cargar()
            return

        # ADVERTENCIA: buscar() cierra la sesión. Misma regla: solo columnas directas.
        productos = self.controlador_productos.buscar(texto)
        self.tabla_productos.setRowCount(len(productos))
        for fila, producto in enumerate(productos):
            self.tabla_productos.setItem(fila, 0, QTableWidgetItem(str(producto.idproducto)))
            self.tabla_productos.setItem(fila, 1, QTableWidgetItem(producto.nombre_producto))
            categoria = producto.categoria or "-"
            self.tabla_productos.setItem(fila, 2, QTableWidgetItem(categoria))
            self.tabla_productos.setItem(
                fila,
                3,
                QTableWidgetItem(formatear_bs(producto.precio_venta_bs)),
            )
            self.tabla_productos.setItem(
                fila,
                4,
                QTableWidgetItem(formatear_usd(producto.precio_venta_usd)),
            )
            s_act = formatear_stock(producto.stock_actual)
            s_min = formatear_stock(producto.stock_minimo)
            self.tabla_productos.setItem(fila, 5, QTableWidgetItem(s_act))
            self.tabla_productos.setItem(fila, 6, QTableWidgetItem(s_min))
            self.tabla_productos.setItem(fila, 7, QTableWidgetItem(producto.unidad))
            self.tabla_productos.setItem(
                fila,
                8,
                QTableWidgetItem(producto.tipo_venta or "UNIDAD"),
            )
