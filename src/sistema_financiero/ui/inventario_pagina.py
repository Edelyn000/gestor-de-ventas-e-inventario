# ============================================================
# ARCHIVO: ui/inventario_pagina.py  (PAGINA DE INVENTARIO)
# ============================================================
# Widget independiente para el control de inventario (movimientos
# de entrada, salida y ajuste de stock).
#
# QUE MUESTRA:
#   1. Combo para seleccionar producto (o "Todos los productos").
#   2. Botones: Entrada (verde), Salida (rojo), Ajuste (naranja), Refrescar.
#   3. Tabla con historial de movimientos del producto seleccionado.
#
# DIALOGO INTERNO:
#   _mostrar_dialogo_movimiento() crea un QDialog con producto, cantidad,
#   motivo y observaciones. Todo autogestionado (no usa seniales).
#
# QUE SE PUEDE MODIFICAR:
#   - Estilos de botones, colores, fuentes.
#   - Columnas y anchos de la tabla.
#   - Items del combo de motivos en _crear_formulario_movimiento().
#   - Textos y etiquetas.
#
# QUE NO SE DEBE TOCAR:
#   - Nombre de la clase (InventarioPagina).
#   - Firma del __init__ (controlador_inventario, controlador_productos).
#   - Metodos _cargar_productos_en_combo y _refrescar_tabla_movimientos
#     (llamados al inicio y tras cada operacion).
# ============================================================
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.inventario_service import InventarioService
from ..core.producto_controller import ProductoController


class InventarioPagina(QWidget):
    def __init__(
        self,
        controlador_inventario: InventarioService,
        controlador_productos: ProductoController,
    ) -> None:
        super().__init__()

        self.controlador_inventario = controlador_inventario
        self.controlador_productos = controlador_productos

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        lbl_titulo = QLabel("Inventario")
        fuente = QFont()
        fuente.setPointSize(24)
        fuente.setBold(True)
        lbl_titulo.setFont(fuente)
        layout.addWidget(lbl_titulo)

        barra = QHBoxLayout()
        barra.setSpacing(10)

        self.cmb_producto_inventario = QComboBox()
        self.cmb_producto_inventario.setMinimumWidth(250)
        self.cmb_producto_inventario.currentIndexChanged.connect(self._refrescar_tabla_movimientos)
        barra.addWidget(QLabel("Producto:"))
        barra.addWidget(self.cmb_producto_inventario)
        barra.addSpacing(20)

        btn_entrada = QPushButton("Entrada")
        btn_entrada.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white;"
            " padding: 8px 16px; border-radius: 5px; font-weight: bold; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        btn_entrada.clicked.connect(lambda: self._mostrar_dialogo_movimiento("ENTRADA"))
        barra.addWidget(btn_entrada)

        btn_salida = QPushButton("Salida")
        btn_salida.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white;"
            " padding: 8px 16px; border-radius: 5px; font-weight: bold; }"
            "QPushButton:hover { background-color: #da190b; }"
        )
        btn_salida.clicked.connect(lambda: self._mostrar_dialogo_movimiento("SALIDA"))
        barra.addWidget(btn_salida)

        btn_ajuste = QPushButton("Ajuste")
        btn_ajuste.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white;"
            " padding: 8px 16px; border-radius: 5px; font-weight: bold; }"
            "QPushButton:hover { background-color: #e68a00; }"
        )
        btn_ajuste.clicked.connect(lambda: self._mostrar_dialogo_movimiento("AJUSTE"))
        barra.addWidget(btn_ajuste)

        btn_refrescar = QPushButton("Refrescar")
        btn_refrescar.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white;"
            " padding: 8px 16px; border-radius: 5px; font-weight: bold; }"
            "QPushButton:hover { background-color: #0b7dda; }"
        )
        btn_refrescar.clicked.connect(self._refrescar_tabla_movimientos)
        barra.addWidget(btn_refrescar)

        barra.addStretch()
        layout.addLayout(barra)

        self.tabla_movimientos = QTableWidget()
        self.tabla_movimientos.setColumnCount(7)
        self.tabla_movimientos.setHorizontalHeaderLabels(
            ["ID", "Fecha", "Producto", "Tipo", "Cantidad", "Stock Anterior", "Stock Nuevo"]
        )
        self.tabla_movimientos.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
        self.tabla_movimientos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla_movimientos.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.tabla_movimientos)

        self._cargar_productos_en_combo()
        self._refrescar_tabla_movimientos()

    def _cargar_productos_en_combo(self) -> None:
        productos = self.controlador_productos.listar_todos()

        self.cmb_producto_inventario.clear()
        self.cmb_producto_inventario.addItem("Todos los productos", None)

        for prod in productos:
            texto = f"{prod.nombre_producto} (Stock: {prod.stock_actual})"
            self.cmb_producto_inventario.addItem(texto, prod.idproducto)

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
                mov.fecha_movimiento.strftime("%d/%m/%Y %H:%M") if mov.fecha_movimiento else ""
            )
            self.tabla_movimientos.setItem(fila, 1, QTableWidgetItem(fecha_str))
            nombre = mov.producto.nombre_producto if mov.producto else "-"
            self.tabla_movimientos.setItem(fila, 2, QTableWidgetItem(nombre))
            item_tipo = QTableWidgetItem(mov.tipo)
            if mov.tipo == "ENTRADA":
                item_tipo.setBackground(Qt.GlobalColor.green)
                item_tipo.setForeground(Qt.GlobalColor.white)
            elif mov.tipo == "SALIDA":
                item_tipo.setBackground(Qt.GlobalColor.red)
                item_tipo.setForeground(Qt.GlobalColor.white)
            else:
                item_tipo.setBackground(Qt.GlobalColor.darkYellow)
                item_tipo.setForeground(Qt.GlobalColor.white)
            self.tabla_movimientos.setItem(fila, 3, item_tipo)
            self.tabla_movimientos.setItem(fila, 4, QTableWidgetItem(str(mov.cantidad)))
            self.tabla_movimientos.setItem(fila, 5, QTableWidgetItem(str(mov.stock_anterior)))
            self.tabla_movimientos.setItem(fila, 6, QTableWidgetItem(str(mov.stock_nuevo)))

        self.tabla_movimientos.resizeColumnsToContents()

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
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botones.accepted.connect(dialogo.accept)
        botones.rejected.connect(dialogo.reject)
        layout.addWidget(botones)

        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        producto_id = cmb_producto.currentData()
        cantidad = spin_cantidad.value()
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
                producto_actual = self.controlador_productos.obtener_por_id(producto_id)
                stock_fisico = (
                    (producto_actual.stock_actual + cantidad) if producto_actual else cantidad
                )
                self.controlador_inventario.registrar_ajuste(
                    producto_id=producto_id,
                    stock_fisico=stock_fisico,
                    motivo=motivo,
                    observaciones=observaciones or None,
                )

            mensaje = f"{tipo} registrada correctamente."
            QMessageBox.information(dialogo, "Exito", mensaje)

            self._refrescar_tabla_movimientos()
            self._cargar_productos_en_combo()

        except ValueError as e:
            QMessageBox.warning(dialogo, "Error", str(e))

    def _crear_formulario_movimiento(
        self,
        layout: QVBoxLayout,
        tipo: str,
    ) -> tuple[QComboBox, QSpinBox, QComboBox, QLineEdit]:
        form = QFormLayout()

        cmb_producto = QComboBox()
        cmb_producto.setMinimumWidth(250)
        productos = self.controlador_productos.listar_todos()
        for prod in productos:
            texto = f"{prod.nombre_producto} (Stock: {prod.stock_actual})"
            cmb_producto.addItem(texto, prod.idproducto)
        form.addRow("Producto:", cmb_producto)

        spin_cantidad = QSpinBox()
        spin_cantidad.setRange(1, 999999)
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
