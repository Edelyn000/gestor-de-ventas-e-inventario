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
from ..models import Usuario
from ..utils import formatear_bs, formatear_stock, formatear_usd
from .inventario_pagina import InventarioPagina
from .widgets import CampoBusqueda, TablaProductos, TituloPagina


# ProductosPagina: CRUD de productos con pestanas de catalogo y movimientos.
class ProductosPagina(QWidget):
    """Pagina de gestion de productos (Catalogo) + movimientos (Inventario)."""

    producto_agregar = pyqtSignal()
    producto_editar = pyqtSignal(int)
    producto_eliminar = pyqtSignal(int)

    # Construye la pagina de productos con pestanas y botones por rol.
    def __init__(
        self,
        controlador_productos: ProductoController,
        controlador_inventario: InventarioService | None = None,
        usuario_actual: Usuario | None = None,
    ) -> None:
        super().__init__()

        self.controlador_productos = controlador_productos
        self.controlador_inventario = controlador_inventario
        self.usuario_actual = usuario_actual
        self.pagina_inventario: InventarioPagina | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        layout.addWidget(TituloPagina("Productos"))

        self.pestanas = QTabWidget()
        layout.addWidget(self.pestanas, 1)

        pestana_catalogo = QWidget()
        catalogo_layout = QVBoxLayout(pestana_catalogo)
        catalogo_layout.setContentsMargins(0, 15, 0, 0)

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

        columnas = [
            ("ID", 50),
            ("Nombre", 200),
            ("Categoria", 120),
            ("Precio Bs", 100),
            ("Precio USD", 100),
            ("Stock", 70),
            ("Stock Min", 70),
            ("Unidad", 60),
        ]
        self.tabla_productos = TablaProductos(columnas)

        self.tabla_productos.cellDoubleClicked.connect(self._emitir_editar)

        catalogo_layout.addWidget(self.tabla_productos, 1)

        self.pestanas.addTab(pestana_catalogo, "Catálogo")

        if controlador_inventario is not None:
            self.pagina_inventario = InventarioPagina(
                controlador_inventario=controlador_inventario,
                controlador_productos=controlador_productos,
                mostrar_titulo=False,
                usuario_actual=usuario_actual,
            )
            self.pestanas.addTab(self.pagina_inventario, "Movimientos")
            self.pestanas.currentChanged.connect(self._al_cambiar_pestana)

        self.cargar()

    # Refresca el inventario al entrar en la pestana de movimientos.
    def _al_cambiar_pestana(self, indice: int) -> None:
        if indice == 1 and self.pagina_inventario is not None:
            self.pagina_inventario.refrescar_pestana()

    # Devuelve la fila actual y el id del producto seleccionado.
    def _obtener_fila_seleccionada(self) -> tuple[int, int | None]:
        fila = self.tabla_productos.currentRow()
        if fila < 0:
            return -1, None
        item_id = self.tabla_productos.item(fila, 0)
        if item_id is None:
            return -1, None
        return fila, int(item_id.text())

    # Emite la senal de editar con el producto de la fila.
    def _emitir_editar(self) -> None:
        _fila, idproducto = self._obtener_fila_seleccionada()
        if idproducto is not None:
            self.producto_editar.emit(idproducto)

    # Emite la senal de eliminar con el producto de la fila.
    def _emitir_eliminar(self) -> None:
        _fila, idproducto = self._obtener_fila_seleccionada()
        if idproducto is not None:
            self.producto_eliminar.emit(idproducto)

    # Carga todos los productos desde la BD a la tabla.
    def cargar(self) -> None:
        """Carga todos los productos desde la BD a la tabla."""
        productos = self.controlador_productos.listar_todos()

        self.tabla_productos.setRowCount(len(productos))
        for fila, producto in enumerate(productos):
            self.tabla_productos.setItem(fila, 0, QTableWidgetItem(str(producto.idproducto)))
            item_nombre = QTableWidgetItem(producto.nombre_producto)
            self.tabla_productos.setItem(fila, 1, item_nombre)
            categoria = producto.categoria.nombre if producto.categoria else "-"
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

        if self.pagina_inventario is not None:
            self.pagina_inventario.refrescar_combo()

    # Filtra la tabla de productos mientras el usuario escribe.
    def _buscar_producto(self, texto: str) -> None:
        """Filtra la tabla de productos mientras el usuario escribe."""
        texto = texto.strip()
        if not texto:
            self.cargar()
            return

        productos = self.controlador_productos.buscar(texto)
        self.tabla_productos.setRowCount(len(productos))
        for fila, producto in enumerate(productos):
            self.tabla_productos.setItem(fila, 0, QTableWidgetItem(str(producto.idproducto)))
            self.tabla_productos.setItem(fila, 1, QTableWidgetItem(producto.nombre_producto))
            categoria = producto.categoria.nombre if producto.categoria else "-"
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

