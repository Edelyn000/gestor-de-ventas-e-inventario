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
# SENIALES (para que VentanaPrincipal maneje):
#   - producto_agregar: el usuario quiere crear un producto.
#   - producto_editar(id): el usuario quiere editar un producto.
#   - producto_eliminar(id): el usuario quiere eliminar un producto.
#
# --- NO TOCAR: nombre de la clase (ProductosPagina), firma del __init__,
#     las 3 seniales (pyqtSignal), metodo cargar(), _emitir_editar, _emitir_eliminar.
# --- MODIFICABLE: estilos, colores, fuentes, tamanos, columnas y anchos,
#     textos del buscador y botones, logica de _buscar_producto().
# ============================================================
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.producto_controller import ProductoController
from ..utils import formatear_bs, formatear_stock, formatear_usd
from .widgets import CampoBusqueda, TablaProductos


# ============ PAGINA DE PRODUCTOS ============
class ProductosPagina(QWidget):
    """Pagina de gestion de productos con tabla y botones."""

    # --- NO TOCAR: seniales que conecta VentanaPrincipal.
    producto_agregar = pyqtSignal()
    producto_editar = pyqtSignal(int)
    producto_eliminar = pyqtSignal(int)

    # --- NO TOCAR: firma del constructor (recibe controlador).
    def __init__(self, controlador_productos: ProductoController) -> None:
        super().__init__()

        self.controlador_productos = controlador_productos

        # --- MODIFICABLE: layout, margenes.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        # [Titulo]
        # --- MODIFICABLE: texto, fuente, tamaño.
        lbl_titulo = QLabel("Productos")
        fuente = QFont()
        fuente.setPointSize(24)
        fuente.setBold(True)
        lbl_titulo.setFont(fuente)
        layout.addWidget(lbl_titulo)

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

        layout.addWidget(self.tabla_productos, 1)

        # --- NO TOCAR: carga inicial de datos.
        self.cargar()

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
                fila, 3, QTableWidgetItem(formatear_bs(producto.precio_venta_bs)),
            )
            self.tabla_productos.setItem(
                fila, 4, QTableWidgetItem(formatear_usd(producto.precio_venta_usd)),
            )
            stock_act = formatear_stock(producto.stock_actual)
            stock_min = formatear_stock(producto.stock_minimo)
            self.tabla_productos.setItem(fila, 5, QTableWidgetItem(stock_act))
            self.tabla_productos.setItem(fila, 6, QTableWidgetItem(stock_min))
            self.tabla_productos.setItem(fila, 7, QTableWidgetItem(producto.unidad))
            self.tabla_productos.setItem(
                fila, 8, QTableWidgetItem(producto.tipo_venta or "UNIDAD"),
            )

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
                fila, 3, QTableWidgetItem(formatear_bs(producto.precio_venta_bs)),
            )
            self.tabla_productos.setItem(
                fila, 4, QTableWidgetItem(formatear_usd(producto.precio_venta_usd)),
            )
            s_act = formatear_stock(producto.stock_actual)
            s_min = formatear_stock(producto.stock_minimo)
            self.tabla_productos.setItem(fila, 5, QTableWidgetItem(s_act))
            self.tabla_productos.setItem(fila, 6, QTableWidgetItem(s_min))
            self.tabla_productos.setItem(fila, 7, QTableWidgetItem(producto.unidad))
