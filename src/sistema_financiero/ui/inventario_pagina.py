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
#   - Firma del __init__ (controlador_inventario, controlador_productos) —
#     se agrego al final un parametro OPCIONAL mostrar_titulo=True (los
#     llamadores con 2 argumentos no cambian).
#   - Metodos _cargar_productos_en_combo y _refrescar_tabla_movimientos
#     (llamados al inicio y tras cada operacion).
# ============================================================
from decimal import Decimal

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
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
from ..utils import formatear_stock
from ..utils.logging_setup import registrar_excepcion
from .widgets import TablaProductos, TituloPagina


class InventarioPagina(QWidget):
    # --- NO TOCAR: firma del constructor (controladores).
    def __init__(
        self,
        controlador_inventario: InventarioService,
        controlador_productos: ProductoController,
        mostrar_titulo: bool = True,
    ) -> None:
        super().__init__()

        # --- NO TOCAR: almacenamiento de controladores.
        self.controlador_inventario = controlador_inventario
        self.controlador_productos = controlador_productos

        # --- MODIFICABLE: layout, margenes, espaciado.
        layout = QVBoxLayout(self)
        if mostrar_titulo:
            layout.setContentsMargins(30, 30, 30, 30)
        else:
            # Al embeberse como pestana de la pagina de Productos, la pagina
            # contenedora ya aporta margenes y el titulo (evita doble margen).
            layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(15)

        # [Titulo de la pagina]
        # --- MODIFICABLE: texto del titulo (tarjeta con barra lateral).
        if mostrar_titulo:
            layout.addWidget(TituloPagina("Inventario"))

        # [Barra de herramientas: combo + botones]
        # --- MODIFICABLE: estilos de botones, colores, textos, fuente.
        barra = QHBoxLayout()
        barra.setSpacing(10)

        self.cmb_producto_inventario = QComboBox()
        self.cmb_producto_inventario.setMinimumWidth(250)
        # --- NO TOCAR: conexion al filtro de movimientos.
        self.cmb_producto_inventario.currentIndexChanged.connect(self._refrescar_tabla_movimientos)
        barra.addWidget(QLabel("Producto:"))
        barra.addWidget(self.cmb_producto_inventario)
        barra.addSpacing(20)

        # --- MODIFICABLE: textos de los botones de accion (colores en ui/estilos.py).
        btn_entrada = QPushButton("Entrada")
        btn_entrada.setProperty("rol", "accion")
        btn_entrada.clicked.connect(lambda: self._mostrar_dialogo_movimiento("ENTRADA"))
        barra.addWidget(btn_entrada)

        btn_salida = QPushButton("Salida")
        btn_salida.setProperty("rol", "peligro")
        btn_salida.clicked.connect(lambda: self._mostrar_dialogo_movimiento("SALIDA"))
        barra.addWidget(btn_salida)

        btn_ajuste = QPushButton("Ajuste")
        btn_ajuste.setProperty("rol", "alerta")
        btn_ajuste.clicked.connect(lambda: self._mostrar_dialogo_movimiento("AJUSTE"))
        barra.addWidget(btn_ajuste)

        btn_refrescar = QPushButton("Refrescar")
        btn_refrescar.setProperty("rol", "informacion")
        btn_refrescar.clicked.connect(self._refrescar_tabla_movimientos)
        barra.addWidget(btn_refrescar)

        barra.addStretch()
        layout.addLayout(barra)

        # --- MODIFICABLE: columnas y anchos de la tabla de movimientos.
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

        # --- NO TOCAR: carga inicial de datos.
        self._cargar_productos_en_combo()
        self._refrescar_tabla_movimientos()

    # --- MODIFICABLE: formato del texto de cada item en el combo.
    def _cargar_productos_en_combo(self) -> None:
        # --- NO TOCAR: llamada al controlador.
        productos = self.controlador_productos.listar_todos()

        self.cmb_producto_inventario.clear()
        self.cmb_producto_inventario.addItem("Todos los productos", None)

        for prod in productos:
            texto = f"{prod.nombre_producto} (Stock: {formatear_stock(prod.stock_actual)})"
            self.cmb_producto_inventario.addItem(texto, prod.idproducto)

    # --- NO TOCAR: logica de consulta a BD y llenado de tabla de movimientos.
    def _refrescar_tabla_movimientos(self) -> None:
        producto_id = self.cmb_producto_inventario.currentData()

        if producto_id is None:
            movimientos = self.controlador_inventario.movimientos_recientes(limite=500)
        else:
            movimientos = self.controlador_inventario.historial_por_producto(producto_id)

        # ADVERTENCIA: mov.producto es una relación lazy. Si el service no usa
        # selectinload(), falla con DetachedInstanceError. Usa solo columnas directas.
        # --- MODIFICABLE: formato de la tabla (fechas, colores de tipo).
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
            # --- MODIFICABLE: colores de los tipos de movimiento (solo texto,
            #     sin fondo: los fondos de color chillones quitaban legibilidad).
            if mov.tipo == "ENTRADA":
                item_tipo.setForeground(QColor("#16a34a"))
            elif mov.tipo == "SALIDA":
                item_tipo.setForeground(QColor("#dc2626"))
            else:
                item_tipo.setForeground(QColor("#d97706"))
            self.tabla_movimientos.setItem(fila, 3, item_tipo)
            self.tabla_movimientos.setItem(fila, 4, QTableWidgetItem(str(mov.cantidad)))
            self.tabla_movimientos.setItem(fila, 5, QTableWidgetItem(str(mov.stock_anterior)))
            self.tabla_movimientos.setItem(fila, 6, QTableWidgetItem(str(mov.stock_nuevo)))

        self.tabla_movimientos.resizeColumnsToContents()

    # --- NO TOCAR: logica del dialogo de movimiento (crea el dialogo y procesa).
    def _mostrar_dialogo_movimiento(self, tipo: str) -> None:
        # --- MODIFICABLE: titulo y tamaño del dialogo.
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

        # --- NO TOCAR: obtencion de datos del formulario.
        producto_id = cmb_producto.currentData()
        cantidad = Decimal(str(spin_cantidad.value()))
        motivo = cmb_motivo.currentText()
        observaciones = txt_observaciones.text().strip()

        if producto_id is None:
            QMessageBox.warning(dialogo, "Error", "Debe seleccionar un producto.")
            return

        try:
            # --- NO TOCAR: llamadas al controlador de inventario.
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

            # --- MODIFICABLE: mensaje de exito.
            mensaje = f"{tipo} registrada correctamente."
            QMessageBox.information(dialogo, "Exito", mensaje)

            # --- NO TOCAR: refresco de datos tras la operacion.
            self._refrescar_tabla_movimientos()
            self._cargar_productos_en_combo()

        except ValueError as e:
            QMessageBox.warning(dialogo, "Error", str(e))
        except Exception as e:
            registrar_excepcion(e, "_confirmar_movimiento")
            QMessageBox.critical(
                dialogo, "Error inesperado", f"No se pudo registrar el movimiento.\n{e}"
            )

    # --- MODIFICABLE: campos del formulario (etiquetas, items del combo de motivos,
    #     placeholders, rangos de cantidad).
    def _crear_formulario_movimiento(
        self,
        layout: QVBoxLayout,
        tipo: str,
    ) -> tuple[QComboBox, QDoubleSpinBox, QComboBox, QLineEdit]:
        form = QFormLayout()

        cmb_producto = QComboBox()
        cmb_producto.setMinimumWidth(250)
        productos = self.controlador_productos.listar_todos()
        for prod in productos:
            texto = f"{prod.nombre_producto} (Stock: {formatear_stock(prod.stock_actual)})"
            cmb_producto.addItem(texto, prod.idproducto)
        form.addRow("Producto:", cmb_producto)

        spin_cantidad = QDoubleSpinBox()
        spin_cantidad.setDecimals(3)
        if tipo == "AJUSTE":
            spin_cantidad.setRange(0, 999999)
            form.addRow("Stock Físico:", spin_cantidad)
        else:
            spin_cantidad.setRange(0.001, 999999)
            spin_cantidad.setValue(1)
            form.addRow("Cantidad:", spin_cantidad)

        # --- MODIFICABLE: items del combo de motivos segun tipo.
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

    # --- MODIFICABLE: metodos publicos de refresco (usados cuando la pagina
    #     se embebe como pestana "Movimientos" de ProductosPagina).
    def refrescar_combo(self) -> None:
        """Recarga el combo de productos (tras crear/editar/eliminar uno)."""
        self._cargar_productos_en_combo()

    def refrescar_pestana(self) -> None:
        """Refresca combo y tabla de movimientos al mostrarse la pestana."""
        self._cargar_productos_en_combo()
        self._refrescar_tabla_movimientos()
