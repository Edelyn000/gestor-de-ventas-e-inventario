# ============================================================
# ARCHIVO: ui/formulario_venta.py  (DIALOGO DE NUEVA VENTA)
# ============================================================
# Este dialogo guia al usuario paso a paso para crear una venta.
# Antes estaba dentro de interflaz.py, lo extraemos a su propio
# archivo para mantener el codigo mas organizado.
#
# Flujo:
#   1. SELECCIONAR PRODUCTOS:
#      - Elige un producto de un QComboBox (desplegable con todos los productos).
#      - Indica la cantidad con un QSpinBox.
#      - Clic "Agregar" → se agrega a la tabla de productos de la venta.
#
#   2. REVISAR PRODUCTOS AGREGADOS:
#      - La tabla muestra: producto, cantidad, precio unitario, subtotal.
#      - Se puede eliminar un producto de la venta si me equivoco.
#      - El total se actualiza automaticamente.
#
#   3. METODO DE PAGO:
#      - Ingresar montos en efectivo Bs, efectivo USD, tarjeta, etc.
#      - El sistema valida que la suma de pagos cubra el total.
#
#   4. FINALIZAR:
#      - Clic "Finalizar Venta" → VentaController.crear() → descuenta stock.
#
# Layout visual:
#   ┌──────────────────────────────────────────────────┐
#   │  Producto: [QComboBox v]  Cant: [5] [Agregar]   │
#   ├──────────────────────────────────────────────────┤
#   │  Productos de la venta:                          │
#   │  ┌──────────┬──────┬────────┬──────────┬──────┐ │
#   │  │ Producto │ Cant │ P.Unit │ Subtotal │ Elim │ │
#   │  ├──────────┼──────┼────────┼──────────┼──────┤ │
#   │  │ Arroz    │  2   │ 1.50   │  3.00    │ [X]  │ │
#   │  │ Aceite   │  1   │ 2.50   │  2.50    │ [X]  │ │
#   │  └──────────┴──────┴────────┴──────────┴──────┘ │
#   │  TOTAL: Bs. 5.50                                 │
#   ├──────────────────────────────────────────────────┤
#   │  Metodo de Pago:                                 │
#   │  Efectivo Bs: [____] USD: [____]                 │
#   │  Tarjeta: [_____] PagoMovil: [___] BioPago:[__] │
#   ├──────────────────────────────────────────────────┤
#   │           [Cancelar]  [Finalizar Venta]          │
#   └──────────────────────────────────────────────────┘
# ============================================================
from decimal import Decimal
from typing import cast

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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.producto_controller import ProductoController
from ..core.tasa_cambio_service import TasaCambioService
from ..core.venta_controller import VentaController
from ..utils import configurar_spinbox_bs, configurar_spinbox_usd, formatear_bs


class FormularioVenta(QDialog):
    # __init__: recibe los controladores como parametros en lugar de obtenerlos
    # via self.parent(). Esto es MAS CLARO porque se ve explicitamente que
    # controladores usa y evita errores de tipado con PyQt6.
    def __init__(
        self,
        parent: QWidget | None = None,
        controlador_productos: ProductoController | None = None,
        controlador_ventas: VentaController | None = None,
        controlador_tasas: TasaCambioService | None = None,
    ) -> None:
        # Llamar al constructor de QDialog.
        super().__init__(parent)

        # Guardar los controladores para usarlos en los metodos.
        self.controlador_productos = controlador_productos
        self.controlador_ventas = controlador_ventas
        self.controlador_tasas = controlador_tasas

        # Configuracion basica de la ventana.
        self.setWindowTitle("Nueva Venta")
        self.resize(700, 600)  # Mas grande porque tiene muchos componentes.
        self.setStyleSheet("background-color: white;")

        # Lista temporal: aqui guardamos los productos que se van agregando
        #   antes de enviarlos al controlador.
        # Cada elemento es un dict con: idproducto, nombre, cantidad, precio, subtotal.
        self.productos_venta: list[dict[str, object]] = []

        # Total acumulado de la venta en bolivares.
        self.total_bs = Decimal("0.00")

        # Construir la interfaz grafica.
        self._setup_ui()

        # Cargar los productos en el QComboBox para que el usuario pueda elegirlos.
        self._cargar_combo_productos()

        # Actualizar la tasa de cambio mostrada.
        self._actualizar_tasa()

    # ------------------------------------------------------------------
    # _setup_ui: construye todos los widgets del dialogo
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:  # noqa: PLR0915
        """Crea los widgets del dialogo de nueva venta."""
        # Layout vertical principal.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # ----------------------------------------------------------
        # SECCION: SELECCIONAR PRODUCTO
        # ----------------------------------------------------------
        # QGroupBox: un cuadro con borde y titulo para agrupar widgets relacionados.
        grupo_producto = QGroupBox("Agregar Producto")
        # Layout horizontal para el grupo.
        grupo_layout = QHBoxLayout(grupo_producto)

        # QComboBox: lista desplegable para elegir un producto.
        # El usuario hace clic y ve todos los productos disponibles.
        self.combo_producto = QComboBox()
        self.combo_producto.setMinimumWidth(300)
        self.combo_producto.setPlaceholderText("Selecciona un producto...")
        grupo_layout.addWidget(self.combo_producto)

        # QSpinBox: cantidad del producto a vender (minimo 1).
        self.spin_cantidad = QSpinBox()
        self.spin_cantidad.setRange(1, 9999)
        self.spin_cantidad.setValue(1)
        grupo_layout.addWidget(QLabel("Cant:"))
        grupo_layout.addWidget(self.spin_cantidad)

        # Boton: Agregar producto a la lista de la venta.
        btn_agregar = QPushButton("Agregar")
        btn_agregar.clicked.connect(self._agregar_producto_venta)
        grupo_layout.addWidget(btn_agregar)

        layout.addWidget(grupo_producto)

        # ----------------------------------------------------------
        # SECCION: TABLA DE PRODUCTOS DE LA VENTA
        # ----------------------------------------------------------
        layout.addSpacing(10)
        layout.addWidget(QLabel("Productos de la venta:"))

        self.tabla_productos_venta = QTableWidget()
        columnas = [
            ("Producto", 200),
            ("Cantidad", 60),
            ("P.Unit Bs", 100),
            ("Subtotal", 100),
            ("", 40),
        ]
        self.tabla_productos_venta.setColumnCount(len(columnas))
        self.tabla_productos_venta.setHorizontalHeaderLabels([c[0] for c in columnas])
        for i, (_, ancho) in enumerate(columnas):
            self.tabla_productos_venta.setColumnWidth(i, ancho)
        self.tabla_productos_venta.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabla_productos_venta.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # layout.addWidget con factor 1 para que ocupe espacio vertical.
        layout.addWidget(self.tabla_productos_venta, 1)

        # ----------------------------------------------------------
        # TOTAL DE LA VENTA
        # ----------------------------------------------------------
        # QLabel que muestra el total actualizado en tiempo real.
        self.lbl_total = QLabel(f"Total: {formatear_bs(Decimal('0.00'))}")
        self.lbl_total.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.lbl_total)

        # Tasa de cambio activa (informativa).
        self.lbl_tasa = QLabel("Tasa BCV: ---")
        self.lbl_tasa.setStyleSheet("color: #666;")
        layout.addWidget(self.lbl_tasa)

        # ----------------------------------------------------------
        # SECCION: METODO DE PAGO
        # ----------------------------------------------------------
        layout.addSpacing(10)
        grupo_pago = QGroupBox("Metodo de Pago")
        form_pago = QFormLayout(grupo_pago)

        # Cada metodo de pago tiene su propio QDoubleSpinBox.
        # El usuario ingresa el monto recibido por cada metodo.

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

        # ----------------------------------------------------------
        # BOTONES DE ACCION
        # ----------------------------------------------------------
        layout.addSpacing(10)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)

        # Boton "Finalizar Venta": verde para indicar accion positiva.
        btn_finalizar = QPushButton("Finalizar Venta")
        btn_finalizar.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 10px 20px;"
        )
        btn_finalizar.clicked.connect(self._finalizar_venta)
        btn_layout.addWidget(btn_finalizar)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # _cargar_combo_productos: llena el QComboBox con todos los productos
    # ------------------------------------------------------------------
    def _cargar_combo_productos(self) -> None:
        """Carga la lista de productos en el QComboBox."""
        if not self.controlador_productos:
            return

        # Obtener todos los productos.
        productos = self.controlador_productos.listar_todos()

        # Limpiar el combo por si ya tenia datos.
        self.combo_producto.clear()

        # Agregar cada producto como un item.
        # setItemData: guardamos el ID del producto como "user data"
        #   para recuperarlo despues sin tener que parsear el texto.
        for p in productos:
            texto = f"{p.nombre_producto} (Stock: {p.stock_actual})"
            self.combo_producto.addItem(texto, p.idproducto)

    # ------------------------------------------------------------------
    # _actualizar_tasa: muestra la tasa de cambio activa en la UI
    # ------------------------------------------------------------------
    def _actualizar_tasa(self) -> None:
        """Actualiza el label de la tasa de cambio."""
        if not self.controlador_tasas:
            return
        tasa = self.controlador_tasas.tasa_activa()
        if tasa:
            texto = f"Tasa BCV: {formatear_bs(tasa.tasa_venta)} / USD  (activa: {tasa.fecha})"
            self.lbl_tasa.setText(texto)
        else:
            self.lbl_tasa.setText("Tasa BCV: No hay tasa activa registrada.")

    # ------------------------------------------------------------------
    # _agregar_producto_venta: agrega el producto seleccionado a la venta
    # ------------------------------------------------------------------
    def _agregar_producto_venta(self) -> None:
        """Agrega el producto seleccionado a la lista de la venta."""
        # Asegurar que los controladores no sean None (se pasan en el constructor).
        assert self.controlador_productos is not None
        assert self.controlador_ventas is not None

        # Obtener el ID del producto seleccionado en el combo.
        # .currentData() devuelve el "user data" que guardamos con addItem.
        idproducto = self.combo_producto.currentData()
        if idproducto is None:
            QMessageBox.warning(self, "Agregar", "Selecciona un producto.")
            return

        # Obtener la cantidad del QSpinBox.
        cantidad = self.spin_cantidad.value()

        # Obtener el producto completo para saber su precio y nombre.
        producto = self.controlador_productos.obtener_por_id(int(idproducto))
        if not producto:
            QMessageBox.warning(self, "Error", "El producto no existe.")
            return

        # Validar stock disponible.
        if producto.stock_actual < cantidad:
            QMessageBox.warning(
                self,
                "Stock insuficiente",
                f"Stock disponible: {producto.stock_actual}. Solicitado: {cantidad}.",
            )
            return

        # Calcular subtotal.
        subtotal = producto.precio_venta_bs * Decimal(str(cantidad))

        # Agregar a la lista temporal.
        self.productos_venta.append(
            {
                "idproducto": producto.idproducto,
                "nombre": producto.nombre_producto,
                "cantidad": cantidad,
                "precio": producto.precio_venta_bs,
                "subtotal": subtotal,
            }
        )

        # Actualizar el total acumulado.
        self.total_bs += subtotal

        # Refrescar la tabla y el label de total.
        self._refrescar_tabla_productos()
        self._actualizar_total()

    # ------------------------------------------------------------------
    # _refrescar_tabla_productos: actualiza la tabla con los productos agregados
    # ------------------------------------------------------------------
    def _refrescar_tabla_productos(self) -> None:
        """Refresca la tabla de productos de la venta."""
        self.tabla_productos_venta.setRowCount(len(self.productos_venta))

        for fila, item in enumerate(self.productos_venta):
            self.tabla_productos_venta.setItem(
                fila, 0, QTableWidgetItem(str(item.get("nombre", "")))
            )
            self.tabla_productos_venta.setItem(
                fila, 1, QTableWidgetItem(str(item.get("cantidad", 0)))
            )
            precio = cast(Decimal, item.get("precio", Decimal("0.00")))
            self.tabla_productos_venta.setItem(fila, 2, QTableWidgetItem(formatear_bs(precio)))
            subtotal = cast(Decimal, item.get("subtotal", Decimal("0.00")))
            self.tabla_productos_venta.setItem(fila, 3, QTableWidgetItem(formatear_bs(subtotal)))

            # Boton "X" para eliminar el producto de la venta.
            # QPushButton dentro de la tabla usando setCellWidget.
            # Esto permite poner cualquier widget dentro de una celda.
            btn_eliminar = QPushButton("X")
            btn_eliminar.setStyleSheet("color: red; font-weight: bold;")
            btn_eliminar.clicked.connect(lambda _=False, f=fila: self._eliminar_producto_venta(f))
            self.tabla_productos_venta.setCellWidget(fila, 4, btn_eliminar)

    # ------------------------------------------------------------------
    # _actualizar_total: actualiza el QLabel del total y el total_usd
    # ------------------------------------------------------------------
    def _actualizar_total(self) -> None:
        """Actualiza el label del total de la venta."""
        self.lbl_total.setText(f"Total: {formatear_bs(self.total_bs)}")

    # ------------------------------------------------------------------
    # _eliminar_producto_venta: quita un producto de la lista temporal
    # ------------------------------------------------------------------
    def _eliminar_producto_venta(self, fila: int) -> None:
        """Elimina un producto de la lista de la venta."""
        if 0 <= fila < len(self.productos_venta):
            subtotal = Decimal(str(self.productos_venta[fila].get("subtotal", "0.00")))
            self.total_bs -= subtotal
            self.productos_venta.pop(fila)
            self._refrescar_tabla_productos()
            self._actualizar_total()

    # ------------------------------------------------------------------
    # _finalizar_venta: valida y guarda la venta en la BD
    # ------------------------------------------------------------------
    def _finalizar_venta(self) -> None:
        """Valida los datos y finaliza la venta."""
        if not self.productos_venta:
            QMessageBox.warning(self, "Venta vacia", "Agrega al menos un producto a la venta.")
            return

        # Refrescar la tasa antes de finalizar por si cambio mientras
        # el formulario estaba abierto. La que se aplica es la del
        # momento de crear, no la que vio al abrir el dialogo.
        self._actualizar_tasa()

        productos: list[dict[str, object]] = []
        for item in self.productos_venta:
            productos.append(
                {
                    "idproducto": int(str(item.get("idproducto", 0))),
                    "cantidad": int(str(item.get("cantidad", 1))),
                }
            )

        metodo_pago: dict[str, object] = {
            "efectivo_bs": Decimal(str(self.spin_efectivo_bs.value())),
            "efectivo_usd": Decimal(str(self.spin_efectivo_usd.value())),
            "tarjeta": Decimal(str(self.spin_tarjeta.value())),
            "pago_movil": Decimal(str(self.spin_pago_movil.value())),
            "bio_pago": Decimal(str(self.spin_bio_pago.value())),
        }

        assert self.controlador_ventas is not None
        try:
            venta = self.controlador_ventas.crear(productos, metodo_pago)

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
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error inesperado",
                f"No se pudo crear la venta:\n{e}",
            )

