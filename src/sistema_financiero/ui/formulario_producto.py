# ============================================================
# ARCHIVO: ui/formulario_producto.py  (DIALOGO CREAR/EDITAR PRODUCTO)
# ============================================================
# QDialog que se abre para AGREGAR o EDITAR un producto.
#
# Tiene DOS modos de uso:
#   1. Crear: FormularioProducto(padre) → campos vacios, crea un producto nuevo.
#   2. Editar: FormularioProducto(padre, producto=existente) → campos
#      pre-cargados, guarda los cambios sobre el mismo producto.
#
# Como se distingue entre crear y editar?
#   - Si producto es None (o no se pasa) → modo CREAR.
#   - Si producto tiene un valor → modo EDITAR.
#
# --- NO TOCAR: nombre de la clase (FormularioProducto), firma del __init__,
#     logica de validacion y guardado (_guardar).
# --- MODIFICABLE: layout, estilos, colores, textos, tamaños de campos,
#     placeholders, valores por defecto.
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
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# --- NO TOCAR: importaciones de logica de negocio.
from ..core.producto_controller import ProductoController
from ..core.tasa_cambio_service import TasaCambioService
from ..models import Producto
from ..utils import (
    TIPO_VENTA_PESO,
    TIPO_VENTA_UNIDAD,
    TIPOS_VENTA,
    configurar_spinbox_bs,
    configurar_spinbox_usd,
    formatear_bs,
)
from ..utils.logging_setup import registrar_excepcion


# ============ DIALOGO CREAR/EDITAR PRODUCTO ============
class FormularioProducto(QDialog):
    # --- NO TOCAR: firma del constructor (recibe controladores y producto opcional).
    def __init__(
        self,
        parent: QWidget | None = None,
        producto: Producto | None = None,
        controlador_productos: ProductoController | None = None,
        controlador_tasas: TasaCambioService | None = None,
    ) -> None:
        super().__init__(parent)

        # --- NO TOCAR: almacenamiento de controladores.
        self.controlador_productos = controlador_productos
        self.controlador_tasas = controlador_tasas
        self._actualizando = False  # Evita bucle infinito Bs <> USD

        # Guardar el producto que se va a editar (None si es modo crear).
        self.producto = producto

        # --- MODIFICABLE: titulo de la ventana segun modo.
        if producto:
            self.setWindowTitle(f"Editar producto: {producto.nombre_producto}")
        else:
            self.setWindowTitle("Agregar producto")

        # --- MODIFICABLE: tamaño fijo del dialogo.
        self.setFixedSize(420, 460)

        # --- NO TOCAR: construccion del UI y carga de datos.
        self._setup_ui()

        # Si estamos en modo editar, llenar los campos con los datos actuales.
        if producto:
            self._cargar_datos(producto)

    # ------------------------------------------------------------------
    # _setup_ui: construye los campos del formulario
    # ------------------------------------------------------------------
    # --- MODIFICABLE COMPLETAMENTE: layout, campos, estilos, textos, tamanos.
    def _setup_ui(self) -> None:
        """Crea todos los campos del formulario y los botones."""
        layout = QVBoxLayout(self)
        # --- MODIFICABLE: margenes del layout.
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addLayout(self._crear_formulario())
        layout.addSpacing(20)
        layout.addLayout(self._crear_botones())

    # --- MODIFICABLE: todos los campos del formulario (etiquetas, placeholders, rangos).
    def _crear_formulario(self) -> QFormLayout:
        """Crea los campos del formulario de producto."""
        form = QFormLayout()

        self.txt_nombre = QLineEdit()
        self.txt_nombre.setPlaceholderText("Nombre del producto")
        form.addRow("Nombre:", self.txt_nombre)

        self.txt_categoria = QLineEdit()
        self.txt_categoria.setPlaceholderText("Ej: LACTEOS, BEBIDAS, etc.")
        form.addRow("Categoria:", self.txt_categoria)

        self.spin_precio_compra = QDoubleSpinBox()
        configurar_spinbox_bs(self.spin_precio_compra)
        form.addRow("Precio Compra:", self.spin_precio_compra)

        self.spin_precio_venta_bs = QDoubleSpinBox()
        configurar_spinbox_bs(self.spin_precio_venta_bs)
        form.addRow("Precio Venta Bs:", self.spin_precio_venta_bs)

        self.spin_precio_venta_usd = QDoubleSpinBox()
        configurar_spinbox_usd(self.spin_precio_venta_usd)
        form.addRow("Precio Venta USD:", self.spin_precio_venta_usd)

        self.lbl_tasa = QLabel("")
        self._actualizar_label_tasa()
        form.addRow("", self.lbl_tasa)

        # --- NO TOCAR: conexiones de sincronizacion Bs <> USD (core).
        self.spin_precio_venta_bs.valueChanged.connect(self._actualizar_usd_desde_bs)
        self.spin_precio_venta_usd.valueChanged.connect(self._actualizar_bs_desde_usd)

        self.cmb_tipo_venta = QComboBox()
        self.cmb_tipo_venta.addItems(TIPOS_VENTA)
        # --- NO TOCAR: conexion al ajuste de step segun tipo de venta.
        self.cmb_tipo_venta.currentTextChanged.connect(self._cambio_tipo_venta)
        form.addRow("Tipo Venta:", self.cmb_tipo_venta)

        self.spin_stock_actual = QDoubleSpinBox()
        # --- MODIFICABLE: rango, decimales, step y valor por defecto.
        self.spin_stock_actual.setRange(0, 999999)
        self.spin_stock_actual.setDecimals(3)
        self.spin_stock_actual.setSingleStep(1)
        self.spin_stock_actual.setValue(0)
        form.addRow("Stock Actual:", self.spin_stock_actual)

        self.spin_stock_minimo = QDoubleSpinBox()
        self.spin_stock_minimo.setRange(0.001, 999999)
        self.spin_stock_minimo.setDecimals(3)
        self.spin_stock_minimo.setSingleStep(1)
        self.spin_stock_minimo.setValue(5)
        form.addRow("Stock Minimo:", self.spin_stock_minimo)

        self.txt_unidad = QLineEdit()
        self.txt_unidad.setPlaceholderText("UNIDAD, KG, LTS, etc.")
        self.txt_unidad.setText("UNIDAD")
        form.addRow("Unidad:", self.txt_unidad)

        return form

    # --- MODIFICABLE: texto de botones, estilos.
    def _crear_botones(self) -> QHBoxLayout:
        """Crea los botones Cancelar y Guardar."""
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)

        btn_guardar = QPushButton("Guardar")
        btn_guardar.setProperty("rol", "primario")
        # --- NO TOCAR: _guardar conecta con el controlador.
        btn_guardar.clicked.connect(self._guardar)
        btn_layout.addWidget(btn_guardar)

        return btn_layout

    # --- MODIFICABLE: logica de ajuste de step segun tipo de venta.
    def _cambio_tipo_venta(self, tipo: str) -> None:
        """Ajusta el step de los spinboxes de stock segun el tipo de venta."""
        if tipo == TIPO_VENTA_PESO:
            self.spin_stock_actual.setSingleStep(0.1)
            self.spin_stock_minimo.setSingleStep(0.1)
        else:
            self.spin_stock_actual.setSingleStep(1)
            self.spin_stock_minimo.setSingleStep(1)

    # ------------------------------------------------------------------
    # _cargar_datos: llena los campos con los valores de un producto existente
    # ------------------------------------------------------------------
    # Solo se usa en modo editar.
    # --- MODIFICABLE: mapeo de campos del producto a widgets del formulario.
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
        self.spin_stock_actual.setValue(float(producto.stock_actual))
        self.spin_stock_minimo.setValue(float(producto.stock_minimo))
        self.txt_unidad.setText(producto.unidad)
        self.cmb_tipo_venta.setCurrentText(producto.tipo_venta or TIPO_VENTA_UNIDAD)
        self._actualizando = False

    # ------------------------------------------------------------------
    # _actualizar_label_tasa: muestra la tasa activa en el formulario
    # ------------------------------------------------------------------
    # --- MODIFICABLE: texto y estilo del label de tasa. NO TOCAR la llamada a tasa_activa().
    def _actualizar_label_tasa(self) -> None:
        # ADVERTENCIA: tasa_activa() cierra la sesión. tasa.tasa_venta y tasa.fecha
        # son columnas directas (seguras). TasaCambio no tiene relaciones lazy.
        tasa = self.controlador_tasas.tasa_activa() if self.controlador_tasas else None
        if tasa:
            # --- MODIFICABLE: formato del texto de tasa.
            self.lbl_tasa.setText(
                f"Tasa: {formatear_bs(tasa.tasa_venta)} / USD  (al {tasa.fecha})",
            )
            self.lbl_tasa.setStyleSheet("color: #6b7280; font-size: 11px;")
        else:
            # --- MODIFICABLE: mensaje cuando no hay tasa activa.
            self.lbl_tasa.setText("No hay tasa activa. Los precios no se sincronizaran.")
            self.lbl_tasa.setStyleSheet("color: #6b7280; font-size: 11px;")

    # ------------------------------------------------------------------
    # _actualizar_usd_desde_bs: al cambiar Bs → calcular USD
    # ------------------------------------------------------------------
    # --- NO TOCAR: logica de conversion Bs a USD (usa tasa de cambio activa).
    def _actualizar_usd_desde_bs(self, valor_bs: float) -> None:
        if self._actualizando or not self.controlador_tasas:
            return
        # ADVERTENCIA: tasa_activa() cierra la sesión. Solo columnas directas.
        tasa = self.controlador_tasas.tasa_activa()
        if valor_bs <= 0:
            # Sin precio en Bs: el equivalente en USD se limpia (0).
            self._actualizando = True
            self.spin_precio_venta_usd.setValue(0.0)
            self._actualizando = False
            return
        if tasa and tasa.tasa_venta > 0:
            self._actualizando = True
            usd = valor_bs / float(tasa.tasa_venta)
            self.spin_precio_venta_usd.setValue(round(usd, 2))
            self._actualizando = False

    # ------------------------------------------------------------------
    # _actualizar_bs_desde_usd: al cambiar USD → calcular Bs
    # ------------------------------------------------------------------
    # --- NO TOCAR: logica de conversion USD a Bs (usa tasa de cambio activa).
    def _actualizar_bs_desde_usd(self, valor_usd: float) -> None:
        if self._actualizando or not self.controlador_tasas:
            return
        # ADVERTENCIA: tasa_activa() cierra la sesión. Solo columnas directas.
        tasa = self.controlador_tasas.tasa_activa()
        if valor_usd <= 0:
            # Sin precio en USD: el equivalente en Bs se limpia (0).
            self._actualizando = True
            self.spin_precio_venta_bs.setValue(0.0)
            self._actualizando = False
            return
        if tasa and tasa.tasa_venta > 0:
            self._actualizando = True
            bs = valor_usd * float(tasa.tasa_venta)
            self.spin_precio_venta_bs.setValue(round(bs, 2))
            self._actualizando = False

    # ------------------------------------------------------------------
    # _guardar: valida los campos y guarda el producto (crear o editar)
    # ------------------------------------------------------------------
    # --- NO TOCAR: logica de validacion y guardado en BD (core del sistema).
    # Se ejecuta al hacer clic en "Guardar".
    # Si es modo crear: llama a controlador_productos.crear().
    # Si es modo editar: llama a controlador_productos.actualizar().
    # ------------------------------------------------------------------
    def _guardar(self) -> None:
        """Valida los campos y guarda el producto en la BD."""
        # ----------------------------------------------------------
        # PASO 1: Validar campos obligatorios
        # ----------------------------------------------------------
        # --- MODIFICABLE: mensajes de validacion, campos requeridos.
        nombre = self.txt_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Validacion", "El nombre es obligatorio.")
            self.txt_nombre.setFocus()
            return

        # ----------------------------------------------------------
        # PASO 2: Obtener valores de los campos
        # ----------------------------------------------------------
        # --- MODIFICABLE: mapeo de widgets a variables.
        categoria = self.txt_categoria.text().strip() or None
        precio_compra = self.spin_precio_compra.value()
        precio_venta_bs = self.spin_precio_venta_bs.value()
        precio_venta_usd = self.spin_precio_venta_usd.value()
        stock_actual = Decimal(str(self.spin_stock_actual.value()))
        stock_minimo = Decimal(str(self.spin_stock_minimo.value()))
        unidad = self.txt_unidad.text().strip().upper() or "UNIDAD"
        tipo_venta = self.cmb_tipo_venta.currentText()

        # ----------------------------------------------------------
        # PASO 3: Guardar (crear o actualizar segun el modo)
        # ----------------------------------------------------------
        # --- NO TOCAR: bloque try/except con llamadas al controlador.
        try:
            if self.producto:
                # MODO EDITAR: actualizar el producto existente.
                producto_id = self.producto.idproducto
                if producto_id is None:
                    msg = "ID de producto no disponible después de guardar"
                    raise RuntimeError(msg)

                # --- NO TOCAR: llamada al controlador para actualizar.
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
                    tipo_venta=tipo_venta,
                )
            else:
                # MODO CREAR: crear un nuevo producto.
                # --- NO TOCAR: llamada al controlador para crear.
                nuevo = Producto(
                    nombre_producto=nombre,
                    categoria=categoria,
                    precio_compra=Decimal(str(precio_compra)),
                    precio_venta_bs=Decimal(str(precio_venta_bs)),
                    precio_venta_usd=Decimal(str(precio_venta_usd)),
                    stock_actual=stock_actual,
                    stock_minimo=stock_minimo,
                    unidad=unidad,
                    tipo_venta=tipo_venta,
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
            QMessageBox.warning(self, "Error de validacion", str(e))
        except Exception as e:
            registrar_excepcion(e, "FormularioProducto._guardar")
            QMessageBox.critical(
                self,
                "Error inesperado",
                f"No se pudo guardar el producto.\n{e}",
            )
