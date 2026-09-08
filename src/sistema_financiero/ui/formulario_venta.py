# ============================================================
# ARCHIVO: ui/formulario_venta.py  (DIALOGO DE NUEVA VENTA)
# ============================================================
# Este dialogo guia al usuario paso a paso para crear una venta.
#
# Flujo:
#   1. SELECCIONAR PRODUCTOS:
#      - Elige un producto de un QComboBox.
#      - Indica la cantidad con un QDoubleSpinBox.
#      - Clic "Agregar" → se agrega a la tabla de productos de la venta.
#
#   2. REVISAR PRODUCTOS AGREGADOS:
#      - La tabla muestra: producto, cantidad, precio unitario, subtotal.
#      - Se puede eliminar un producto de la venta.
#      - El total se actualiza automaticamente.
#
#   3. METODO DE PAGO:
#      - Ingresar montos en efectivo Bs, efectivo USD, tarjeta, etc.
#      - El sistema valida que la suma de pagos cubra el total.
#
#   4. FINALIZAR:
#      - Clic "Finalizar Venta" → VentaController.crear() → descuenta stock.
#
# --- NO TOCAR: nombre de la clase (FormularioVenta), firma del __init__,
#     logica de crear venta (_finalizar_venta), controladores.
# --- MODIFICABLE: layout, estilos, textos, columnas de tabla, colores de botones.
# ============================================================
from decimal import Decimal
from typing import TypedDict

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.producto_controller import ProductoController
from ..core.tasa_cambio_service import TasaCambioService
from ..core.venta_controller import VentaController
from ..utils import (
    TIPO_VENTA_PESO,
    configurar_spinbox_bs,
    configurar_spinbox_usd,
    formatear_bs,
    formatear_stock,
)


# --- NO TOCAR: TypedDicts para tipado estricto de datos de venta.
class ProductoVenta(TypedDict):
    idproducto: int | None
    nombre: str
    cantidad: Decimal
    precio: Decimal
    subtotal: Decimal


class MetodoPago(TypedDict):
    efectivo_bs: Decimal
    efectivo_usd: Decimal
    tarjeta: Decimal
    pago_movil: Decimal
    bio_pago: Decimal


# ============ DIALOGO DE NUEVA VENTA ============
class FormularioVenta(QDialog):
    # --- NO TOCAR: firma del constructor (recibe controladores).
    def __init__(
        self,
        parent: QWidget | None = None,
        controlador_productos: ProductoController | None = None,
        controlador_ventas: VentaController | None = None,
        controlador_tasas: TasaCambioService | None = None,
    ) -> None:
        super().__init__(parent)

        # --- NO TOCAR: almacenamiento de controladores.
        self.controlador_productos = controlador_productos
        self.controlador_ventas = controlador_ventas
        self.controlador_tasas = controlador_tasas

        # --- MODIFICABLE: titulo y tamaño de la ventana.
        self.setWindowTitle("Nueva Venta")
        self.resize(700, 600)

        # --- NO TOCAR: estado interno de la venta.
        self.productos_venta: list[ProductoVenta] = []
        self.total_bs = Decimal("0.00")

        # --- NO TOCAR: construccion del UI y carga inicial.
        self._setup_ui()
        self._cargar_combo_productos()
        self._actualizar_tasa()

    # ------------------------------------------------------------------
    # _setup_ui: construye todos los widgets del dialogo
    # ------------------------------------------------------------------
    # --- MODIFICABLE COMPLETAMENTE: layout, grupos, campos, estilos.
    def _setup_ui(self) -> None:
        """Crea los widgets del dialogo de nueva venta."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        self._crear_seccion_seleccion_producto(layout)
        self._crear_seccion_tabla_y_total(layout)
        self._crear_seccion_pago(layout)
        layout.addSpacing(10)
        self._crear_botones(layout)

    # --- MODIFICABLE: grupo de seleccion de producto (textos, tamanos).
    def _crear_seccion_seleccion_producto(self, layout: QVBoxLayout) -> None:
        grupo_producto = QGroupBox("Agregar Producto")
        grupo_layout = QHBoxLayout(grupo_producto)

        self.combo_producto = QComboBox()
        self.combo_producto.setMinimumWidth(300)
        self.combo_producto.setPlaceholderText("Selecciona un producto...")
        # --- NO TOCAR: conexion al ajuste de cantidad segun producto.
        self.combo_producto.currentIndexChanged.connect(self._ajustar_spin_cantidad)
        grupo_layout.addWidget(self.combo_producto)

        self.spin_cantidad = QDoubleSpinBox()
        # --- MODIFICABLE: rango, decimales, step y valor por defecto.
        self.spin_cantidad.setRange(0, 9999)
        self.spin_cantidad.setDecimals(3)
        self.spin_cantidad.setSingleStep(1)
        self.spin_cantidad.setValue(1)
        grupo_layout.addWidget(QLabel("Cant:"))
        grupo_layout.addWidget(self.spin_cantidad)

        # --- MODIFICABLE: texto del boton Agregar.
        btn_agregar = QPushButton("Agregar")
        # --- NO TOCAR: conexion a _agregar_producto_venta.
        btn_agregar.clicked.connect(self._agregar_producto_venta)
        grupo_layout.addWidget(btn_agregar)

        layout.addWidget(grupo_producto)

    # --- MODIFICABLE: tabla de productos (columnas, anchos, estilos).
    def _crear_seccion_tabla_y_total(self, layout: QVBoxLayout) -> None:
        layout.addSpacing(10)
        layout.addWidget(QLabel("Productos de la venta:"))

        columnas: list[tuple[str, int]] = [
            ("Producto", 200),
            ("Cantidad", 60),
            ("P.Unit Bs", 100),
            ("Subtotal", 100),
            ("", 40),
        ]
        self.tabla_productos_venta = QTableWidget()
        self.tabla_productos_venta.setColumnCount(len(columnas))
        self.tabla_productos_venta.setHorizontalHeaderLabels([c[0] for c in columnas])
        for i, (_, ancho) in enumerate(columnas):
            self.tabla_productos_venta.setColumnWidth(i, ancho)
        self.tabla_productos_venta.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.tabla_productos_venta.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        layout.addWidget(self.tabla_productos_venta, 1)

        # --- MODIFICABLE: formato y estilo del label de total.
        self.lbl_total = QLabel(f"Total: {formatear_bs(Decimal('0.00'))}")
        self.lbl_total.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.lbl_total)

        # --- MODIFICABLE: estilo del label de tasa.
        self.lbl_tasa = QLabel("Tasa BCV: ---")
        self.lbl_tasa.setStyleSheet("color: #a6adc8;")
        layout.addWidget(self.lbl_tasa)

    # --- MODIFICABLE: campos de metodo de pago (etiquetas, metodos de pago disponibles).aqui estoy
    def _crear_seccion_pago(self, layout: QVBoxLayout) -> None:
        layout.addSpacing(10)
        grupo_pago = QGroupBox("Metodo de Pago")
        form_pago = QFormLayout(grupo_pago)

        self.spin_efectivo_bs = QDoubleSpinBox()
        configurar_spinbox_bs(self.spin_efectivo_bs)
        form_pago.addRow("Efectivo Bs:", self.spin_efectivo_bs)

        self.spin_efectivo_usd = QDoubleSpinBox()
        configurar_spinbox_usd(self.spin_efectivo_usd)
        form_pago.addRow("Efectivo USD:", self.spin_efectivo_usd)

        self.spin_tarjeta = QDoubleSpinBox()
        configurar_spinbox_bs(self.spin_tarjeta)
        form_pago.addRow("Tarjeta:", self.spin_tarjeta)

        self.spin_pago_movil = QDoubleSpinBox()
        configurar_spinbox_bs(self.spin_pago_movil)
        form_pago.addRow("Pago Movil:", self.spin_pago_movil)

        self.spin_bio_pago = QDoubleSpinBox()
        configurar_spinbox_bs(self.spin_bio_pago)
        form_pago.addRow("BioPago:", self.spin_bio_pago)

        layout.addWidget(grupo_pago)

    # --- MODIFICABLE: textos y estilos de botones (Cancelar, Finalizar Venta).
    def _crear_botones(self, layout: QVBoxLayout) -> None:
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)

        # --- MODIFICABLE: estilo y texto del boton de finalizar.
        btn_finalizar = QPushButton("Finalizar Venta")
        btn_finalizar.setStyleSheet(
            "background-color: #a6e3a1; color: #1e1e2e;"
            " font-weight: bold; padding: 10px 20px; border-radius: 4px;",
        )
        # --- NO TOCAR: conexion a _finalizar_venta.
        btn_finalizar.clicked.connect(self._finalizar_venta)
        btn_layout.addWidget(btn_finalizar)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # _cargar_combo_productos: llena el QComboBox con todos los productos
    # ------------------------------------------------------------------
    # --- MODIFICABLE: formato del texto de cada item en el combo.
    def _cargar_combo_productos(self) -> None:
        """Carga la lista de productos en el QComboBox."""
        if not self.controlador_productos:
            return

        # --- NO TOCAR: llamada al controlador para listar productos.
        productos = self.controlador_productos.listar_todos()
        self.combo_producto.clear()

        for p in productos:
            stock_str = formatear_stock(p.stock_actual)
            texto = f"{p.nombre_producto} (Stock: {stock_str}) [{p.tipo_venta or 'UNIDAD'}]"
            self.combo_producto.addItem(texto, p.idproducto)

    # ------------------------------------------------------------------
    # _actualizar_tasa: muestra la tasa de cambio activa en la UI
    # ------------------------------------------------------------------
    # --- MODIFICABLE: texto de la tasa. NO TOCAR la llamada a tasa_activa().
    def _actualizar_tasa(self) -> None:
        """Actualiza el label de la tasa de cambio."""
        if not self.controlador_tasas:
            return
        # ADVERTENCIA: tasa_activa() cierra la sesión. Solo columnas directas.
        tasa = self.controlador_tasas.tasa_activa()
        if tasa:
            texto = f"Tasa BCV: {formatear_bs(tasa.tasa_venta)} / USD  (activa: {tasa.fecha})"
            self.lbl_tasa.setText(texto)
        else:
            self.lbl_tasa.setText("Tasa BCV: No hay tasa activa registrada.")

    # --- MODIFICABLE: ajuste de step/decimales segun tipo de producto.
    def _ajustar_spin_cantidad(self) -> None:
        """Ajusta step y decimals del spin segun tipo_venta del producto seleccionado."""
        if not self.controlador_productos:
            return
        idproducto = self.combo_producto.currentData()
        if idproducto is None:
            return
        producto = self.controlador_productos.obtener_por_id(int(idproducto))
        if not producto:
            return
        if producto.tipo_venta == TIPO_VENTA_PESO:
            self.spin_cantidad.setSingleStep(0.1)
            self.spin_cantidad.setDecimals(3)
            self.spin_cantidad.setRange(0.001, 9999)
        else:
            self.spin_cantidad.setSingleStep(1)
            self.spin_cantidad.setDecimals(3)
            self.spin_cantidad.setRange(0.001, 9999)

    # ------------------------------------------------------------------
    # _agregar_producto_venta: agrega el producto seleccionado a la venta
    # ------------------------------------------------------------------
    # --- NO TOCAR: logica de validacion de stock y calculo de subtotal.
    def _agregar_producto_venta(self) -> None:
        """Agrega el producto seleccionado a la lista de la venta."""
        if self.controlador_productos is None or self.controlador_ventas is None:
            msg = "Controladores no inicializados"
            raise RuntimeError(msg)

        idproducto = self.combo_producto.currentData()
        if idproducto is None:
            QMessageBox.warning(self, "Agregar", "Selecciona un producto.")
            return

        cantidad = Decimal(str(self.spin_cantidad.value()))

        # --- NO TOCAR: obtencion del producto desde el controlador.
        producto = self.controlador_productos.obtener_por_id(int(idproducto))
        if not producto:
            QMessageBox.warning(self, "Error", "El producto no existe.")
            return

        # --- NO TOCAR: validacion de stock.
        if producto.stock_actual < cantidad:
            QMessageBox.warning(
                self,
                "Stock insuficiente",
                f"Stock disponible: {producto.stock_actual}. Solicitado: {cantidad}.",
            )
            return

        # --- NO TOCAR: calculo de subtotal.
        subtotal = producto.precio_venta_bs * Decimal(str(cantidad))

        # --- NO TOCAR: agregado a lista temporal y actualizacion de total.
        self.productos_venta.append(
            {
                "idproducto": producto.idproducto,
                "nombre": producto.nombre_producto,
                "cantidad": cantidad,
                "precio": producto.precio_venta_bs,
                "subtotal": subtotal,
            },
        )

        self.total_bs += subtotal
        self._refrescar_tabla_productos()
        self._actualizar_total()

    # ------------------------------------------------------------------
    # _refrescar_tabla_productos: actualiza la tabla con los productos agregados
    # ------------------------------------------------------------------
    # --- MODIFICABLE: formato de la tabla (como se muestran los datos, estilo boton X).
    def _refrescar_tabla_productos(self) -> None:
        """Refresca la tabla de productos de la venta."""
        self.tabla_productos_venta.setRowCount(len(self.productos_venta))

        for fila, item in enumerate(self.productos_venta):
            self.tabla_productos_venta.setItem(
                fila,
                0,
                QTableWidgetItem(item["nombre"]),
            )
            self.tabla_productos_venta.setItem(
                fila,
                1,
                QTableWidgetItem(str(item["cantidad"])),
            )
            precio = item["precio"]
            self.tabla_productos_venta.setItem(fila, 2, QTableWidgetItem(formatear_bs(precio)))
            subtotal = item["subtotal"]
            self.tabla_productos_venta.setItem(fila, 3, QTableWidgetItem(formatear_bs(subtotal)))

            # --- MODIFICABLE: estilo del boton eliminar (texto, color, forma).
            btn_eliminar = QPushButton("X")
            btn_eliminar.setStyleSheet("color: red; font-weight: bold;")
            btn_eliminar.clicked.connect(lambda _=False, f=fila: self._eliminar_producto_venta(f))
            self.tabla_productos_venta.setCellWidget(fila, 4, btn_eliminar)

    # ------------------------------------------------------------------
    # _actualizar_total: actualiza el QLabel del total y el total_usd
    # ------------------------------------------------------------------
    # --- MODIFICABLE: formato del texto del total.
    def _actualizar_total(self) -> None:
        """Actualiza el label del total de la venta."""
        self.lbl_total.setText(f"Total: {formatear_bs(self.total_bs)}")

    # ------------------------------------------------------------------
    # _eliminar_producto_venta: quita un producto de la lista temporal
    # ------------------------------------------------------------------
    # --- NO TOCAR: logica de eliminacion y actualizacion de totales.
    def _eliminar_producto_venta(self, fila: int) -> None:
        """Elimina un producto de la lista de la venta."""
        if 0 <= fila < len(self.productos_venta):
            subtotal = self.productos_venta[fila]["subtotal"]
            self.total_bs -= subtotal
            self.productos_venta.pop(fila)
            self._refrescar_tabla_productos()
            self._actualizar_total()

    # ------------------------------------------------------------------
    # _finalizar_venta: valida y guarda la venta en la BD
    # ------------------------------------------------------------------
    # --- NO TOCAR: logica de finalizacion de venta (llamada al controlador).
    def _finalizar_venta(self) -> None:
        """Valida los datos y finaliza la venta."""
        if not self.productos_venta:
            QMessageBox.warning(self, "Venta vacia", "Agrega al menos un producto a la venta.")
            return

        # --- NO TOCAR: refrescar tasa antes de crear (valor del momento).
        self._actualizar_tasa()

        # --- NO TOCAR: preparacion de datos para el controlador.
        productos: list[dict[str, object]] = [
            {
                "idproducto": int(str(item["idproducto"])),
                "cantidad": item["cantidad"],
            }
            for item in self.productos_venta
        ]

        metodo_pago: dict[str, object] = {
            "efectivo_bs": Decimal(str(self.spin_efectivo_bs.value())),
            "efectivo_usd": Decimal(str(self.spin_efectivo_usd.value())),
            "tarjeta": Decimal(str(self.spin_tarjeta.value())),
            "pago_movil": Decimal(str(self.spin_pago_movil.value())),
            "bio_pago": Decimal(str(self.spin_bio_pago.value())),
        }

        if self.controlador_ventas is None:
            msg = "Controlador de ventas no inicializado"
            raise RuntimeError(msg)
        try:
            # --- NO TOCAR: llamada al controlador para crear la venta.
            venta = self.controlador_ventas.crear(productos, metodo_pago)

            # --- MODIFICABLE: mensaje de exito (texto, formato).
            QMessageBox.information(
                self,
                "Venta exitosa",
                f"Venta registrada correctamente.\n"
                f"Factura: {venta.numero_factura}\n"
                f"Total: {formatear_bs(venta.total_bs)}",
            )

            self.accept()

        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
        except Exception:
            QMessageBox.critical(
                self,
                "Error inesperado",
                "No se pudo crear la venta.",
            )
            raise
