from decimal import Decimal

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.inventario_service import InventarioService
from ..core.producto_controller import ProductoController
from ..models import Producto, Usuario
from ..utils import (
    es_medida,
    formatear_stock,
)
from ..utils.fecha import a_local
from ..utils.logging_setup import registrar_excepcion
from .widgets import SpinBoxStock, TablaProductos, TituloPagina


# InventarioPagina: Movimientos de stock por rol del usuario.
class InventarioPagina(QWidget):
    # Construye la pagina de movimientos con filtros y botones por rol.
    def __init__(
        self,
        controlador_inventario: InventarioService,
        controlador_productos: ProductoController,
        mostrar_titulo: bool = True,
        usuario_actual: Usuario | None = None,
    ) -> None:
        super().__init__()

        self.controlador_inventario = controlador_inventario
        self.controlador_productos = controlador_productos
        self.usuario_actual = usuario_actual

        layout = QVBoxLayout(self)
        if mostrar_titulo:
            layout.setContentsMargins(30, 30, 30, 30)
        else:
            layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(15)

        if mostrar_titulo:
            layout.addWidget(TituloPagina("Inventario"))

        barra = QHBoxLayout()
        barra.setSpacing(10)

        self.cmb_producto_inventario = QComboBox()
        self.cmb_producto_inventario.setMinimumWidth(250)
        self.cmb_producto_inventario.currentIndexChanged.connect(self._refrescar_tabla_movimientos)
        barra.addWidget(QLabel("Producto:"))
        barra.addWidget(self.cmb_producto_inventario)
        barra.addSpacing(20)

        self.btn_entrada = QPushButton("Entrada")
        self.btn_entrada.setProperty("rol", "accion")
        self.btn_entrada.clicked.connect(lambda: self._mostrar_dialogo_movimiento("ENTRADA"))
        barra.addWidget(self.btn_entrada)

        self.btn_salida = QPushButton("Salida")
        self.btn_salida.setProperty("rol", "peligro")
        self.btn_salida.clicked.connect(lambda: self._mostrar_dialogo_movimiento("SALIDA"))
        barra.addWidget(self.btn_salida)

        self.btn_ajuste = QPushButton("Ajuste")
        self.btn_ajuste.setProperty("rol", "alerta")
        self.btn_ajuste.clicked.connect(lambda: self._mostrar_dialogo_movimiento("AJUSTE"))
        barra.addWidget(self.btn_ajuste)

        btn_refrescar = QPushButton("Refrescar")
        btn_refrescar.setProperty("rol", "informacion")
        btn_refrescar.clicked.connect(self._refrescar_tabla_movimientos)
        barra.addWidget(btn_refrescar)

        barra.addStretch()
        layout.addLayout(barra)

        if self.usuario_actual is not None and self.usuario_actual.rol != "ADMINISTRADOR":
            self.btn_salida.hide()
            self.btn_ajuste.hide()

        columnas = [
            ("ID", 50),
            ("Fecha", 150),
            ("Producto", 200),
            ("Tipo", 80),
            ("Cantidad", 80),
            ("Stock Anterior", 100),
            ("Stock Nuevo", 100),
        ]
        self.tabla_movimientos = TablaProductos(columnas)
        layout.addWidget(self.tabla_movimientos)

        self._cargar_productos_en_combo()
        self._refrescar_tabla_movimientos()

    # Llena el combo de productos con la opcion Todos.
    def _cargar_productos_en_combo(self) -> None:
        productos = self.controlador_productos.listar_todos()

        self.cmb_producto_inventario.clear()
        self.cmb_producto_inventario.addItem("Todos los productos", None)

        for prod in productos:
            texto = f"{prod.nombre_producto} (Stock: {formatear_stock(prod.stock_actual)})"
            self.cmb_producto_inventario.addItem(texto, prod.idproducto)

    # Recarga los movimientos segun el filtro de producto.
    def _refrescar_tabla_movimientos(self) -> None:
        producto_id = self.cmb_producto_inventario.currentData()

        if producto_id is None:
            movimientos = self.controlador_inventario.movimientos_recientes(limite=500)
        else:
            movimientos = self.controlador_inventario.historial_por_producto(producto_id)

        self.tabla_movimientos.setRowCount(len(movimientos))
        for fila, mov in enumerate(movimientos):
            self.tabla_movimientos.setItem(fila, 0, QTableWidgetItem(str(mov.id or "")))
            fecha_str = (
                a_local(mov.fecha_movimiento).strftime("%d/%m/%Y %H:%M")
                if mov.fecha_movimiento
                else ""
            )
            self.tabla_movimientos.setItem(fila, 1, QTableWidgetItem(fecha_str))
            nombre = mov.producto.nombre_producto if mov.producto else "-"
            self.tabla_movimientos.setItem(fila, 2, QTableWidgetItem(nombre))
            item_tipo = QTableWidgetItem(mov.tipo)
            if mov.tipo == "ENTRADA":
                item_tipo.setForeground(QColor("#16a34a"))
            elif mov.tipo == "SALIDA":
                item_tipo.setForeground(QColor("#dc2626"))
            else:
                item_tipo.setForeground(QColor("#d97706"))
            self.tabla_movimientos.setItem(fila, 3, item_tipo)
            self.tabla_movimientos.setItem(fila, 4, QTableWidgetItem(formatear_stock(mov.cantidad)))
            self.tabla_movimientos.setItem(
                fila, 5, QTableWidgetItem(formatear_stock(mov.stock_anterior))
            )
            self.tabla_movimientos.setItem(
                fila, 6, QTableWidgetItem(formatear_stock(mov.stock_nuevo))
            )

        self.tabla_movimientos.resizeColumnsToContents()

    # Abre el dialogo para registrar entrada, salida o ajuste.
    def _mostrar_dialogo_movimiento(self, tipo: str) -> None:
        dialogo = QDialog(self)
        dialogo.setWindowTitle(f"Registrar {tipo}")
        dialogo.setFixedSize(400, 300)

        layout = QVBoxLayout(dialogo)
        layout.setContentsMargins(20, 20, 20, 20)

        cmb_producto, spin_cantidad, cmb_motivo, txt_observaciones = (
            self._crear_formulario_movimiento(layout, tipo)
        )

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        botones.accepted.connect(dialogo.accept)
        botones.rejected.connect(dialogo.reject)
        layout.addWidget(botones)

        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        producto_id = cmb_producto.currentData()
        cantidad = Decimal(str(spin_cantidad.value()))
        motivo = cmb_motivo.currentText()
        observaciones = txt_observaciones.text().strip()

        if producto_id is None:
            QMessageBox.warning(dialogo, "Error", "Debe seleccionar un producto.")
            return

        try:
            if tipo == "ENTRADA":
                self.controlador_inventario.registrar_entrada(
                    producto_id=producto_id,
                    cantidad=cantidad,
                    motivo=motivo,
                    observaciones=observaciones or None,
                )
            elif tipo == "SALIDA":
                self.controlador_inventario.registrar_salida(
                    producto_id=producto_id,
                    cantidad=cantidad,
                    motivo=motivo,
                    observaciones=observaciones or None,
                )
            else:
                self.controlador_inventario.registrar_ajuste(
                    producto_id=producto_id,
                    stock_fisico=cantidad,
                    motivo=motivo,
                    observaciones=observaciones or None,
                )

            mensaje = f"{tipo} registrada correctamente."
            QMessageBox.information(dialogo, "Exito", mensaje)

            self._refrescar_tabla_movimientos()
            self._cargar_productos_en_combo()

        except ValueError as e:
            QMessageBox.warning(dialogo, "Error", str(e))
        except Exception as e:
            registrar_excepcion(e, "_confirmar_movimiento")
            QMessageBox.critical(
                dialogo, "Error inesperado", f"No se pudo registrar el movimiento.\n{e}"
            )

    # Crea los campos del formulario del movimiento.
    def _crear_formulario_movimiento(
        self,
        layout: QVBoxLayout,
        tipo: str,
    ) -> tuple[QComboBox, SpinBoxStock, QComboBox, QLineEdit]:
        form = QFormLayout()

        cmb_producto = QComboBox()
        cmb_producto.setMinimumWidth(250)
        productos = self.controlador_productos.listar_todos()
        productos_por_id: dict[int, Producto] = {}
        for prod in productos:
            if prod.idproducto is not None:
                productos_por_id[prod.idproducto] = prod
            texto = f"{prod.nombre_producto} (Stock: {formatear_stock(prod.stock_actual)})"
            cmb_producto.addItem(texto, prod.idproducto)
        form.addRow("Producto:", cmb_producto)

        spin_cantidad = SpinBoxStock()

        # Enteros para UNIDAD; decimales (kg) para los productos por peso.
        def _ajustar_segun_producto() -> None:
            """Enteros para UNIDAD; decimales (kg) para los productos por peso."""
            prod = productos_por_id.get(cmb_producto.currentData())
            por_peso = bool(prod and es_medida(prod.tipo_venta))
            spin_cantidad.set_modo_entero(not por_peso)

        cmb_producto.currentIndexChanged.connect(_ajustar_segun_producto)
        _ajustar_segun_producto()

        if tipo == "AJUSTE":
            form.addRow("Stock Físico:", spin_cantidad)
        else:
            spin_cantidad.setValue(1)
            form.addRow("Cantidad:", spin_cantidad)

        cmb_motivo = QComboBox()
        if tipo == "ENTRADA":
            cmb_motivo.addItems(["COMPRA", "DEVOLUCION", "TRASLADO", "OTRO"])
        elif tipo == "SALIDA":
            cmb_motivo.addItems(["VENTA", "PERDIDA", "VENCIMIENTO", "TRASLADO", "OTRO"])
        else:
            cmb_motivo.addItems(["INVENTARIO", "ROBO", "EXTRA", "OTRO"])
        form.addRow("Motivo:", cmb_motivo)

        txt_observaciones = QLineEdit()
        txt_observaciones.setPlaceholderText("Observaciones (opcional)")
        form.addRow("Observaciones:", txt_observaciones)

        layout.addLayout(form)

        return cmb_producto, spin_cantidad, cmb_motivo, txt_observaciones

    # Recarga el combo de productos (tras crear/editar/eliminar uno).
    def refrescar_combo(self) -> None:
        """Recarga el combo de productos (tras crear/editar/eliminar uno)."""
        self._cargar_productos_en_combo()

    # Refresca combo y tabla de movimientos al mostrarse la pestana.
    def refrescar_pestana(self) -> None:
        """Refresca combo y tabla de movimientos al mostrarse la pestana."""
        self._cargar_productos_en_combo()
        self._refrescar_tabla_movimientos()

