# ============================================================
# ARCHIVO: ui/formulario_producto.py  (DIALOGO CREAR/EDITAR PRODUCTO)
# ============================================================
# QDialog que se abre para AGREGAR o EDITAR un producto.
# Antes estaba dentro de interflaz.py, lo extraemos a su propio
# archivo para mantener el codigo mas organizado y facil de mantener.
#
# Tiene DOS modos de uso:
#   1. Crear: ProductoDialog(padre) → campos vacios, crea un producto nuevo.
#   2. Editar: ProductoDialog(padre, producto=existente) → campos
#      pre-cargados, guarda los cambios sobre el mismo producto.
#
# Como se distingue entre crear y editar?
#   - Si producto es None (o no se pasa) → modo CREAR.
#   - Si producto tiene un valor → modo EDITAR.
#
# Layout del dialogo:
#   ┌─────────────────────────────────────┐
#   │  Nombre:    [____________________]  │
#   │  Categoria: [____________________]  │
#   │  Precio Compra:  [___0.00____]      │
#   │  Precio Venta Bs:[___0.00____]      │
#   │  Precio Venta USD:[___0.00____]     │
#   │  Stock Actual:   [___0_____]        │
#   │  Stock Minimo:   [___5_____]        │
#   │  Unidad:  [UNIDAD________________]  │
#   │                                     │
#   │          [Cancelar]  [Guardar]      │
#   └─────────────────────────────────────┘
# ============================================================
from decimal import Decimal

from PyQt6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.producto_controller import ProductoController
from ..core.tasa_cambio_service import TasaCambioService
from ..models import Producto


class FormularioProducto(QDialog):
    # __init__: recibe el widget padre y opcionalmente un producto para editar.
    def __init__(
        self,
        parent: QWidget | None = None,
        producto: Producto | None = None,
        controlador_productos: ProductoController | None = None,
        controlador_tasas: TasaCambioService | None = None,
    ) -> None:
        super().__init__(parent)

        self.controlador_productos = controlador_productos
        self.controlador_tasas = controlador_tasas
        self._actualizando = False  # Evita bucle infinito Bs <> USD

        # Guardar el producto que se va a editar (None si es modo crear).
        self.producto = producto

        # Establecer el titulo segun el modo.
        if producto:
            self.setWindowTitle(f"Editar producto: {producto.nombre_producto}")
        else:
            self.setWindowTitle("Agregar producto")

        # Tamano fijo del dialogo.
        self.setFixedSize(420, 420)
        self.setStyleSheet("background-color: white;")

        # Crear los campos del formulario.
        self._setup_ui()

        # Si estamos en modo editar, llenar los campos con los datos actuales.
        if producto:
            self._cargar_datos(producto)

    # ------------------------------------------------------------------
    # _setup_ui: construye los campos del formulario
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:  # noqa: PLR0915
        """Crea todos los campos del formulario y los botones."""
        # Layout vertical principal.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # ----------------------------------------------------------
        # FORMULARIO (QFormLayout)
        # ----------------------------------------------------------
        # QFormLayout: organiza los campos en filas etiqueta + control.
        form = QFormLayout()

        # Campo: Nombre del producto (QLineEdit).
        self.txt_nombre = QLineEdit()
        self.txt_nombre.setPlaceholderText("Nombre del producto")
        form.addRow("Nombre:", self.txt_nombre)

        # Campo: Categoria (QLineEdit).
        self.txt_categoria = QLineEdit()
        self.txt_categoria.setPlaceholderText("Ej: LACTEOS, BEBIDAS, etc.")
        form.addRow("Categoria:", self.txt_categoria)

        # Campo: Precio de compra (QDoubleSpinBox).
        # QDoubleSpinBox: campo numerico con decimales (igual a un "input type=number").
        # setRange(0, 999999): valores permitidos entre 0 y casi 1 millon.
        # setDecimals(2): 2 decimales (centimos).
        # setPrefix("Bs. "): texto que aparece ANTES del numero.
        self.spin_precio_compra = QDoubleSpinBox()
        self.spin_precio_compra.setRange(0, 999999)
        self.spin_precio_compra.setDecimals(2)
        self.spin_precio_compra.setPrefix("Bs. ")
        form.addRow("Precio Compra:", self.spin_precio_compra)

        # Campo: Precio venta en bolivares.
        self.spin_precio_venta_bs = QDoubleSpinBox()
        self.spin_precio_venta_bs.setRange(0, 999999)
        self.spin_precio_venta_bs.setDecimals(2)
        self.spin_precio_venta_bs.setPrefix("Bs. ")
        form.addRow("Precio Venta Bs:", self.spin_precio_venta_bs)

        # Campo: Precio venta en dolares.
        self.spin_precio_venta_usd = QDoubleSpinBox()
        self.spin_precio_venta_usd.setRange(0, 999999)
        self.spin_precio_venta_usd.setDecimals(2)
        self.spin_precio_venta_usd.setPrefix("$ ")
        form.addRow("Precio Venta USD:", self.spin_precio_venta_usd)

        # Tasa de cambio activa (informativa) para la conversion automatica.
        self.lbl_tasa = QLabel("")
        self._actualizar_label_tasa()
        form.addRow("", self.lbl_tasa)

        # Sincronizacion automatica Bs <> USD usando la tasa activa.
        # Al cambiar Bs → se recalcula USD; al cambiar USD → se recalcula Bs.
        self.spin_precio_venta_bs.valueChanged.connect(self._actualizar_usd_desde_bs)
        self.spin_precio_venta_usd.valueChanged.connect(self._actualizar_bs_desde_usd)

        # Campo: Stock actual (QSpinBox, solo enteros).
        self.spin_stock_actual = QSpinBox()
        self.spin_stock_actual.setRange(0, 999999)
        form.addRow("Stock Actual:", self.spin_stock_actual)

        # Campo: Stock minimo (para alertas de reabastecimiento).
        self.spin_stock_minimo = QSpinBox()
        self.spin_stock_minimo.setRange(1, 999999)
        self.spin_stock_minimo.setValue(5)  # Valor por defecto.
        form.addRow("Stock Minimo:", self.spin_stock_minimo)

        # Campo: Unidad de medida.
        self.txt_unidad = QLineEdit()
        self.txt_unidad.setPlaceholderText("UNIDAD, KG, LTS, etc.")
        self.txt_unidad.setText("UNIDAD")  # Valor por defecto.
        form.addRow("Unidad:", self.txt_unidad)

        # Agregar el formulario al layout principal.
        layout.addLayout(form)

        # ----------------------------------------------------------
        # BOTONES (Aceptar / Cancelar)
        # ----------------------------------------------------------
        layout.addSpacing(20)

        # Layout horizontal para los botones.
        btn_layout = QHBoxLayout()
        # addStretch(): agrega espacio flexible ANTES de los botones,
        #   empujandolos hacia la derecha.
        btn_layout.addStretch()

        # Boton Cancelar: cierra el dialogo sin guardar.
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)

        # Boton Guardar: valida y guarda el producto.
        btn_guardar = QPushButton("Guardar")
        btn_guardar.clicked.connect(self._guardar)
        btn_layout.addWidget(btn_guardar)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # _cargar_datos: llena los campos con los valores de un producto existente
    # ------------------------------------------------------------------
    # Solo se usa en modo editar.
    # ------------------------------------------------------------------
    def _cargar_datos(self, producto: Producto) -> None:
        """Rellena los campos con los datos del producto a editar."""
        self._actualizando = True
        self.txt_nombre.setText(producto.nombre_producto)
        if producto.categoria:
            self.txt_categoria.setText(producto.categoria)
        self.spin_precio_compra.setValue(float(producto.precio_compra))
        self.spin_precio_venta_bs.setValue(float(producto.precio_venta_bs))
        self.spin_precio_venta_usd.setValue(float(producto.precio_venta_usd))
        self.spin_stock_actual.setValue(producto.stock_actual)
        self.spin_stock_minimo.setValue(producto.stock_minimo)
        self.txt_unidad.setText(producto.unidad)
        self._actualizando = False

    # ------------------------------------------------------------------
    # _actualizar_label_tasa: muestra la tasa activa en el formulario
    # ------------------------------------------------------------------
    def _actualizar_label_tasa(self) -> None:
        tasa = self.controlador_tasas.tasa_activa() if self.controlador_tasas else None
        if tasa:
            self.lbl_tasa.setText(
                f"Tasa: Bs. {tasa.tasa_venta} / USD  (al {tasa.fecha})"
            )
            self.lbl_tasa.setStyleSheet("color: #555; font-size: 11px;")
        else:
            self.lbl_tasa.setText("No hay tasa activa. Los precios no se sincronizaran.")
            self.lbl_tasa.setStyleSheet("color: #999; font-size: 11px;")

    # ------------------------------------------------------------------
    # _actualizar_usd_desde_bs: al cambiar Bs → calcular USD
    # ------------------------------------------------------------------
    def _actualizar_usd_desde_bs(self, valor_bs: float) -> None:
        if self._actualizando or not self.controlador_tasas:
            return
        tasa = self.controlador_tasas.tasa_activa()
        if tasa and tasa.tasa_venta > 0 and valor_bs > 0:
            self._actualizando = True
            usd = valor_bs / float(tasa.tasa_venta)
            self.spin_precio_venta_usd.setValue(round(usd, 2))
            self._actualizando = False

    # ------------------------------------------------------------------
    # _actualizar_bs_desde_usd: al cambiar USD → calcular Bs
    # ------------------------------------------------------------------
    def _actualizar_bs_desde_usd(self, valor_usd: float) -> None:
        if self._actualizando or not self.controlador_tasas:
            return
        tasa = self.controlador_tasas.tasa_activa()
        if tasa and tasa.tasa_venta > 0 and valor_usd > 0:
            self._actualizando = True
            bs = valor_usd * float(tasa.tasa_venta)
            self.spin_precio_venta_bs.setValue(round(bs, 2))
            self._actualizando = False

    # ------------------------------------------------------------------
    # _guardar: valida los campos y guarda el producto (crear o editar)
    # ------------------------------------------------------------------
    # Se ejecuta al hacer clic en "Guardar".
    # Si es modo crear: llama a controlador_productos.crear().
    # Si es modo editar: llama a controlador_productos.actualizar().
    # ------------------------------------------------------------------
    def _guardar(self) -> None:
        """Valida los campos y guarda el producto en la BD."""
        # ----------------------------------------------------------
        # PASO 1: Validar campos obligatorios
        # ----------------------------------------------------------
        nombre = self.txt_nombre.text().strip()
        if not nombre:
            # Mostrar advertencia y NO cerrar el dialogo.
            QMessageBox.warning(self, "Validacion", "El nombre es obligatorio.")
            self.txt_nombre.setFocus()  # Poner el cursor en el campo nombre.
            return

        # ----------------------------------------------------------
        # PASO 2: Obtener valores de los campos
        # ----------------------------------------------------------
        categoria = self.txt_categoria.text().strip() or None
        precio_compra = self.spin_precio_compra.value()
        precio_venta_bs = self.spin_precio_venta_bs.value()
        precio_venta_usd = self.spin_precio_venta_usd.value()
        stock_actual = self.spin_stock_actual.value()
        stock_minimo = self.spin_stock_minimo.value()
        unidad = self.txt_unidad.text().strip().upper() or "UNIDAD"

        # ----------------------------------------------------------
        # PASO 3: Guardar (crear o actualizar segun el modo)
        # ----------------------------------------------------------
        try:
            if self.producto:
                # MODO EDITAR: actualizar el producto existente.
                # Llamamos a actualizar() del controlador con los campos a modificar.
                self.producto.nombre_producto = nombre
                self.producto.categoria = categoria
                self.producto.precio_compra = Decimal(str(precio_compra))
                self.producto.precio_venta_bs = Decimal(str(precio_venta_bs))
                self.producto.precio_venta_usd = Decimal(str(precio_venta_usd))
                self.producto.stock_actual = stock_actual
                self.producto.stock_minimo = stock_minimo
                self.producto.unidad = unidad

                # Obtener el ID del producto (nunca es None porque el producto existe).
                producto_id = self.producto.idproducto
                assert producto_id is not None

                # Usar el controlador que recibimos en el constructor.
                # Antes usabamos self.parent().controlador_productos, pero eso
                # fallaba porque parent() devuelve QObject y PyQt6 no reconoce
                # los atributos personalizados de MainWindow.
                if not self.controlador_productos:
                    QMessageBox.critical(
                        self,
                        "Error",
                        "Controlador de productos no disponible. Contacte al administrador.",
                    )
                    return
                self.controlador_productos.actualizar(
                    producto_id,
                    nombre_producto=nombre,
                    categoria=categoria,
                    precio_compra=Decimal(str(precio_compra)),
                    precio_venta_bs=Decimal(str(precio_venta_bs)),
                    precio_venta_usd=Decimal(str(precio_venta_usd)),
                    stock_actual=stock_actual,
                    stock_minimo=stock_minimo,
                    unidad=unidad,
                )
            else:
                # MODO CREAR: crear un nuevo producto.
                # Construimos un objeto Producto con los datos del formulario.
                nuevo = Producto(
                    nombre_producto=nombre,
                    categoria=categoria,
                    precio_compra=Decimal(str(precio_compra)),
                    precio_venta_bs=Decimal(str(precio_venta_bs)),
                    precio_venta_usd=Decimal(str(precio_venta_usd)),
                    stock_actual=stock_actual,
                    stock_minimo=stock_minimo,
                    unidad=unidad,
                )
                if not self.controlador_productos:
                    QMessageBox.critical(
                        self,
                        "Error",
                        "Controlador de productos no disponible. Contacte al administrador.",
                    )
                    return
                self.controlador_productos.crear(nuevo)

            # Si todo salio bien, cerrar el dialogo con exito.
            self.accept()

        except ValueError as e:
            # ValueError es lanzado por el controlador si hay datos invalidos.
            QMessageBox.warning(self, "Error de validacion", str(e))
        except Exception as e:
            # Cualquier otro error inesperado.
            QMessageBox.critical(self, "Error inesperado", f"No se pudo guardar el producto:\n{e}")

