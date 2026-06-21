# ============================================================
# ARCHIVO: ui/productos_pagina.py  (PAGINA DE GESTION DE PRODUCTOS)
# ============================================================
# Widget independiente para la pagina de Productos (CRUD completo).
#
# QUE MUESTRA:
#   1. Barra superior: buscador + botones (Agregar, Editar, Eliminar, Refrescar).
#   2. Tabla con todos los productos.
#   3. Doble clic en una fila → emite senial para editar.
#
# SENIALES (para que MainWindow maneje):
#   - producto_agregar: el usuario quiere crear un producto.
#   - producto_editar(id): el usuario quiere editar un producto.
#   - producto_eliminar(id): el usuario quiere eliminar un producto.
#
# QUE SE PUEDE MODIFICAR:
#   - Estilos, colores, fuentes, tamanos.
#   - Columnas y anchos en __init__ (la tupla columnas).
#   - Textos del buscador y botones.
#   - La logica de _buscar_producto().
#
# QUE NO SE DEBE TOCAR:
#   - Nombre de la clase (ProductosPagina).
#   - Firma del __init__ (controlador_productos: ProductoController).
#   - Las 3 seniales (pyqtSignal): MainWindow las conecta.
#   - Metodo cargar() (MainWindow lo llama al refrescar).
#   - Metodos _emitir_editar y _emitir_eliminar (conectados a botones y doble clic).
# ============================================================
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.producto_controller import ProductoController
from ..utils import formatear_bs, formatear_usd


class ProductosPagina(QWidget):
    """Pagina de gestion de productos con tabla y botones."""

    # Seniales que este widget emite para que MainWindow las maneje.
    # pyqtSignal: tipo especial de PyQt6 para crear eventos.
    producto_agregar = pyqtSignal()
    producto_editar = pyqtSignal(int)  # Recibe el id del producto.
    producto_eliminar = pyqtSignal(int)  # Recibe el id del producto.

    def __init__(self, controlador_productos: ProductoController) -> None:
        super().__init__()

        self.controlador_productos = controlador_productos

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        # Titulo.
        lbl_titulo = QLabel("Productos")
        fuente = QFont()
        fuente.setPointSize(24)
        fuente.setBold(True)
        lbl_titulo.setFont(fuente)
        layout.addWidget(lbl_titulo)

        # Barra de herramientas.
        barra = QHBoxLayout()

        self.txt_buscar_producto = QLineEdit()
        self.txt_buscar_producto.setPlaceholderText("Buscar producto por nombre o categoria...")
        self.txt_buscar_producto.textChanged.connect(self._buscar_producto)
        barra.addWidget(self.txt_buscar_producto, 1)

        btn_refrescar = QPushButton("Refrescar")
        btn_refrescar.clicked.connect(self.cargar)
        barra.addWidget(btn_refrescar)

        btn_agregar = QPushButton("Agregar")
        btn_agregar.clicked.connect(self.producto_agregar.emit)
        barra.addWidget(btn_agregar)

        btn_editar = QPushButton("Editar")
        btn_editar.clicked.connect(self._emitir_editar)
        barra.addWidget(btn_editar)

        btn_eliminar = QPushButton("Eliminar")
        btn_eliminar.clicked.connect(self._emitir_eliminar)
        barra.addWidget(btn_eliminar)

        layout.addLayout(barra)
        layout.addSpacing(10)

        # Tabla de productos.
        self.tabla_productos = QTableWidget()
        columnas = [
            ("ID", 50),
            ("Nombre", 200),
            ("Categoria", 120),
            ("Precio Bs", 100),
            ("Precio USD", 100),
            ("Stock", 70),
            ("Stock Min", 70),
            ("Unidad", 80),
        ]
        self.tabla_productos.setColumnCount(len(columnas))
        self.tabla_productos.setHorizontalHeaderLabels([c[0] for c in columnas])
        for i, (_, ancho) in enumerate(columnas):
            self.tabla_productos.setColumnWidth(i, ancho)
        self.tabla_productos.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla_productos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla_productos.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla_productos.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]

        # Doble clic → emitir senial de editar.
        self.tabla_productos.cellDoubleClicked.connect(self._emitir_editar)

        layout.addWidget(self.tabla_productos, 1)

        self.cargar()

    def _obtener_fila_seleccionada(self) -> tuple[int, int | None]:
        """Devuelve (fila, idproducto) de la fila seleccionada."""
        fila = self.tabla_productos.currentRow()
        if fila < 0:
            return -1, None
        item_id = self.tabla_productos.item(fila, 0)
        if item_id is None:
            return -1, None
        return fila, int(item_id.text())

    def _emitir_editar(self) -> None:
        """Emite la senial producto_editar con el ID de la fila seleccionada."""
        _fila, idproducto = self._obtener_fila_seleccionada()
        if idproducto is not None:
            self.producto_editar.emit(idproducto)

    def _emitir_eliminar(self) -> None:
        """Emite la senial producto_eliminar con el ID de la fila seleccionada."""
        _fila, idproducto = self._obtener_fila_seleccionada()
        if idproducto is not None:
            self.producto_eliminar.emit(idproducto)

    def cargar(self) -> None:
        """Carga todos los productos desde la BD a la tabla."""
        # ADVERTENCIA: listar_todos() cierra la sesión. producto tiene relaciones
        # lazy (movimientos, detalles_venta). Usa solo columnas directas.
        productos = self.controlador_productos.listar_todos()

        self.tabla_productos.setRowCount(len(productos))
        for fila, producto in enumerate(productos):
            self.tabla_productos.setItem(fila, 0, QTableWidgetItem(str(producto.idproducto)))
            item_nombre = QTableWidgetItem(producto.nombre_producto)
            self.tabla_productos.setItem(fila, 1, item_nombre)
            categoria = producto.categoria if producto.categoria else "-"
            self.tabla_productos.setItem(fila, 2, QTableWidgetItem(categoria))
            self.tabla_productos.setItem(
                fila, 3, QTableWidgetItem(formatear_bs(producto.precio_venta_bs))
            )
            self.tabla_productos.setItem(
                fila, 4, QTableWidgetItem(formatear_usd(producto.precio_venta_usd))
            )
            self.tabla_productos.setItem(fila, 5, QTableWidgetItem(str(producto.stock_actual)))
            self.tabla_productos.setItem(fila, 6, QTableWidgetItem(str(producto.stock_minimo)))
            self.tabla_productos.setItem(fila, 7, QTableWidgetItem(producto.unidad))

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
            categoria = producto.categoria if producto.categoria else "-"
            self.tabla_productos.setItem(fila, 2, QTableWidgetItem(categoria))
            self.tabla_productos.setItem(
                fila, 3, QTableWidgetItem(formatear_bs(producto.precio_venta_bs))
            )
            self.tabla_productos.setItem(
                fila, 4, QTableWidgetItem(formatear_usd(producto.precio_venta_usd))
            )
            self.tabla_productos.setItem(fila, 5, QTableWidgetItem(str(producto.stock_actual)))
            self.tabla_productos.setItem(fila, 6, QTableWidgetItem(str(producto.stock_minimo)))
            self.tabla_productos.setItem(fila, 7, QTableWidgetItem(producto.unidad))
