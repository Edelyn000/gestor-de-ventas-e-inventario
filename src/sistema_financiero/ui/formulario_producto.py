from decimal import Decimal

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.producto_controller import ProductoController
from ..core.tasa_cambio_service import TasaCambioService
from ..models import Producto
from ..utils import (
    DECIMAL_CERO,
    GRAMOS_POR_KILO,
    TIPO_VENTA_GRAMOS_LEGADO,
    TIPO_VENTA_PESO,
    UNIDADES_MEDIDA,
    UNIDADES_VENTA,
    configurar_spinbox_usd,
    deducir_tipo_venta,
    formatear_bs,
    normalizar_unidad,
    redondear_moneda,
)
from ..utils.logging_setup import registrar_excepcion
from .widgets import SpinBoxStock


# FormularioProducto: Crear o editar productos con precios en USD.
class FormularioProducto(QDialog):
    ITEM_NUEVA_CATEGORIA = "＋ Nueva categoría…"

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
        self._actualizando = False

        self._bs_compra: Decimal = DECIMAL_CERO
        self._bs_venta: Decimal = DECIMAL_CERO

        self.producto = producto

        if producto:
            self.setWindowTitle(f"Editar producto: {producto.nombre_producto}")
        else:
            self.setWindowTitle("Agregar producto")

        self.setFixedSize(440, 520)

        self._setup_ui()

        if producto:
            self._cargar_datos(producto)

    def _setup_ui(self) -> None:
        """Crea todos los campos del formulario y los botones."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addLayout(self._crear_formulario())
        layout.addSpacing(20)
        layout.addLayout(self._crear_botones())

    def _crear_formulario(self) -> QFormLayout:
        """Crea los campos del formulario de producto."""
        form = QFormLayout()

        self.txt_nombre = QLineEdit()
        self.txt_nombre.setPlaceholderText("Nombre del producto")
        form.addRow("Nombre:", self.txt_nombre)

        self.cmb_categoria = QComboBox()
        self._categoria_anterior: str = ""
        self._cargar_categorias()
        form.addRow("Categoria:", self.cmb_categoria)

        self._crear_campos_precio(form)

        self.spin_stock_actual = SpinBoxStock()
        self.spin_stock_actual.setValue(0)
        form.addRow("Stock Actual:", self.spin_stock_actual)

        self.spin_stock_minimo = SpinBoxStock()
        self.spin_stock_minimo.setValue(5)
        form.addRow("Stock Minimo:", self.spin_stock_minimo)

        self.cmb_unidad = QComboBox()
        self.cmb_unidad.addItems(UNIDADES_VENTA)
        self.cmb_unidad.currentTextChanged.connect(self._ajustar_segun_unidad)
        form.addRow("Unidad:", self.cmb_unidad)

        return form

    def _cargar_categorias(self) -> None:
        """Llena el combo con las categorias existentes + el item especial."""
        self.cmb_categoria.blockSignals(True)
        self.cmb_categoria.clear()
        if self.controlador_productos:
            try:
                categorias = self.controlador_productos.obtener_categorias()
                if isinstance(categorias, (list, tuple)):
                    self.cmb_categoria.addItems([str(c) for c in categorias])
            except Exception:
                pass
        self.cmb_categoria.addItem(self.ITEM_NUEVA_CATEGORIA)
        self.cmb_categoria.blockSignals(False)
        self.cmb_categoria.currentIndexChanged.connect(self._gestionar_categoria)

    def _gestionar_categoria(self, indice: int) -> None:
        """Si el usuario elige 'Nueva categoria…', pide el nombre y lo crea."""
        if self._actualizando:
            return

        if self.cmb_categoria.itemText(indice) != self.ITEM_NUEVA_CATEGORIA:
            self._categoria_anterior = self.cmb_categoria.itemText(indice)
            return

        nombre, aceptado = QInputDialog.getText(
            self,
            "Nueva categoria",
            "Nombre de la categoria:",
        )
        nombre = nombre.strip() if aceptado else ""
        if not nombre:
            inicio = self.cmb_categoria.findText(self._categoria_anterior)
            self.cmb_categoria.setCurrentIndex(inicio if inicio != -1 else -1)
            return

        if not self.controlador_productos:
            self.cmb_categoria.setCurrentIndex(-1)
            return

        try:
            categoria = self.controlador_productos.crear_categoria(nombre)
            if categoria is not None and categoria.nombre:
                if self.cmb_categoria.findText(categoria.nombre) == -1:
                    self.cmb_categoria.insertItem(
                        self.cmb_categoria.count() - 1,
                        categoria.nombre,
                    )
                self._categoria_anterior = categoria.nombre
                self.cmb_categoria.setCurrentIndex(
                    self.cmb_categoria.findText(categoria.nombre),
                )
        except Exception as e:
            registrar_excepcion(e, "FormularioProducto._gestionar_categoria")
            QMessageBox.warning(self, "Error", f"No se pudo crear la categoria.\n{e}")

    def _resolver_categoria_id(self) -> int | None:
        """Devuelve el id de la categoria seleccionada (creando/reutilizando)."""
        nombre = self.cmb_categoria.currentText()
        if not nombre or nombre == self.ITEM_NUEVA_CATEGORIA:
            return None
        if not self.controlador_productos:
            return None
        categoria = self.controlador_productos.crear_categoria(nombre)
        if categoria is None or categoria.id is None:
            return None
        return categoria.id

    def _crear_campos_precio(self, form: QFormLayout) -> None:
        """Crea los campos de precio: USD manual y su equivalente en Bs."""
        fila_compra = QWidget()
        layout_compra = QHBoxLayout(fila_compra)
        layout_compra.setContentsMargins(0, 0, 0, 0)
        layout_compra.setSpacing(4)
        self.spin_precio_compra_usd = QDoubleSpinBox()
        configurar_spinbox_usd(self.spin_precio_compra_usd)
        layout_compra.addWidget(self.spin_precio_compra_usd)
        self.lbl_equiv_compra = QLabel("Equivalente: —")
        self.lbl_equiv_compra.setProperty("rol", "equivalente")
        layout_compra.addWidget(self.lbl_equiv_compra)
        self.lbl_precio_compra = QLabel("Precio Compra por UNIDAD:")
        form.addRow(self.lbl_precio_compra, fila_compra)

        fila_venta = QWidget()
        layout_venta = QHBoxLayout(fila_venta)
        layout_venta.setContentsMargins(0, 0, 0, 0)
        layout_venta.setSpacing(4)
        self.spin_precio_venta_usd = QDoubleSpinBox()
        configurar_spinbox_usd(self.spin_precio_venta_usd)
        layout_venta.addWidget(self.spin_precio_venta_usd)
        self.lbl_equiv_venta = QLabel("Equivalente: —")
        self.lbl_equiv_venta.setProperty("rol", "equivalente")
        layout_venta.addWidget(self.lbl_equiv_venta)
        self.lbl_precio_venta = QLabel("Precio Venta por UNIDAD:")
        form.addRow(self.lbl_precio_venta, fila_venta)

        self.lbl_aviso = QLabel("")
        self.lbl_aviso.setWordWrap(True)
        self.lbl_aviso.setStyleSheet("color: #2563eb; font-size: 11px;")
        self.lbl_aviso.hide()
        form.addRow("", self.lbl_aviso)

        self.lbl_tasa = QLabel("")
        self._actualizar_label_tasa()
        form.addRow("", self.lbl_tasa)

        self.spin_precio_venta_usd.valueChanged.connect(self._actualizar_bs_desde_usd)
        self.spin_precio_compra_usd.valueChanged.connect(self._actualizar_compra_bs_desde_usd)

    def _crear_botones(self) -> QHBoxLayout:
        """Crea los botones Cancelar y Guardar."""
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)

        btn_guardar = QPushButton("Guardar")
        btn_guardar.setProperty("rol", "primario")
        btn_guardar.clicked.connect(self._guardar)
        btn_layout.addWidget(btn_guardar)

        return btn_layout

    def _ajustar_segun_unidad(self) -> None:
        """Ajusta el spin de stock (enteros/decimales) y las etiquetas de precio."""
        unidad = self.cmb_unidad.currentText()
        es_medida = unidad in UNIDADES_MEDIDA
        self.spin_stock_actual.set_modo_entero(not es_medida)
        self.spin_stock_minimo.set_modo_entero(not es_medida)
        self.lbl_precio_compra.setText(f"Precio Compra por {unidad}:")
        self.lbl_precio_venta.setText(f"Precio Venta por {unidad}:")

    def _mostrar_equiv_compra(self) -> None:
        if self._bs_compra > 0:
            self.lbl_equiv_compra.setText(f"Equivalente: {formatear_bs(self._bs_compra)}")
        else:
            self.lbl_equiv_compra.setText("Equivalente: —")

    def _mostrar_equiv_venta(self) -> None:
        if self._bs_venta > 0:
            self.lbl_equiv_venta.setText(f"Equivalente: {formatear_bs(self._bs_venta)}")
        else:
            self.lbl_equiv_venta.setText("Equivalente: —")

    def _cargar_datos(self, producto: Producto) -> None:
        """Rellena los campos con los datos del producto a editar."""
        self._actualizando = True
        self.txt_nombre.setText(producto.nombre_producto)
        if producto.categoria is not None and producto.categoria.nombre:
            nombre_cat = producto.categoria.nombre
            if self.cmb_categoria.findText(nombre_cat) == -1:
                self.cmb_categoria.insertItem(
                    self.cmb_categoria.count() - 1,
                    nombre_cat,
                )
            self.cmb_categoria.setCurrentIndex(self.cmb_categoria.findText(nombre_cat))
            self._categoria_anterior = nombre_cat
        unidad = normalizar_unidad(producto.unidad)
        if self.cmb_unidad.findText(unidad) == -1:
            self.cmb_unidad.addItem(unidad)
        self.cmb_unidad.setCurrentText(unidad)

        factor, aviso_escala = self._factor_precio_por_gramo(producto, unidad)

        def _reescalar(valor: Decimal | int | float | None) -> Decimal:
            """Multiplica un precio legado por gramo por el factor (1 = sin cambio)."""
            if factor == 1:
                return Decimal(str(valor or 0))
            return redondear_moneda(Decimal(str(valor or 0)) * factor)

        self._bs_compra = _reescalar(producto.precio_compra)
        self._bs_venta = _reescalar(producto.precio_venta_bs)
        precio_venta_usd = _reescalar(producto.precio_venta_usd)
        self.spin_precio_venta_usd.setValue(float(precio_venta_usd))
        self.spin_stock_actual.setValue(float(producto.stock_actual))
        self.spin_stock_minimo.setValue(float(producto.stock_minimo))

        self._mostrar_equiv_compra()
        self._mostrar_equiv_venta()
        self._actualizando = False

        self._recalcular_venta_bs_con_tasa_actual(
            _reescalar(producto.precio_venta_bs), aviso_escala
        )

    @staticmethod
    def _factor_precio_por_gramo(producto: Producto, unidad: str) -> tuple[int, str]:
        """Devuelve (factor_a_multiplicar, texto_del_aviso) para _cargar_datos."""
        es_legado_gramos = (producto.tipo_venta or "").strip().upper() == TIPO_VENTA_GRAMOS_LEGADO
        if not es_legado_gramos or deducir_tipo_venta(unidad) != TIPO_VENTA_PESO:
            return 1, ""
        return (
            GRAMOS_POR_KILO,
            f"El producto estaba cotizado POR GRAMO: sus precios se multiplicaron "
            f"por {GRAMOS_POR_KILO} para pasarlos a precio POR KILO "
            f"(el stock y las cantidades ya estaban en kg).",
        )

        return (
            f"El producto estaba cotizado POR GRAMO. Los precios se "
            f"multiplicaron por {GRAMOS_POR_KILO} para pasarlos a "
            f"precio POR KILO (stock y cantidades ya estaban en kg)."
        )

    def _actualizar_label_tasa(self) -> None:
        tasa = self.controlador_tasas.tasa_activa() if self.controlador_tasas else None
        if tasa:
            self.lbl_tasa.setText(
                f"Tasa: {formatear_bs(tasa.tasa_venta)} / USD  (al {tasa.fecha})",
            )
            self.lbl_tasa.setStyleSheet("color: #000000; font-size: 11px;")
        else:
            self.lbl_tasa.setText("No hay tasa activa. Los precios no se sincronizaran.")
            self.lbl_tasa.setStyleSheet("color: #000000; font-size: 11px;")

    def _actualizar_compra_bs_desde_usd(self, valor_usd: float) -> None:
        if self._actualizando or not self.controlador_tasas:
            return
        tasa = self.controlador_tasas.tasa_activa()
        if valor_usd <= 0:
            self._actualizando = True
            self._bs_compra = DECIMAL_CERO
            self._mostrar_equiv_compra()
            self._actualizando = False
            return
        if tasa and tasa.tasa_venta > 0:
            self._actualizando = True
            bs = redondear_moneda(Decimal(str(valor_usd)) * tasa.tasa_venta)
            self._bs_compra = bs
            self._mostrar_equiv_compra()
            self._actualizando = False

    def _actualizar_bs_desde_usd(self, valor_usd: float) -> None:
        if self._actualizando or not self.controlador_tasas:
            return
        tasa = self.controlador_tasas.tasa_activa()
        if valor_usd <= 0:
            self._actualizando = True
            self._bs_venta = DECIMAL_CERO
            self._mostrar_equiv_venta()
            self._actualizando = False
            return
        if tasa and tasa.tasa_venta > 0:
            self._actualizando = True
            bs = redondear_moneda(Decimal(str(valor_usd)) * tasa.tasa_venta)
            self._bs_venta = bs
            self._mostrar_equiv_venta()
            self._actualizando = False

    def _recalcular_venta_bs_con_tasa_actual(
        self,
        bs_anterior: Decimal,
        aviso_extra: str = "",
    ) -> None:
        """Recalcula el Bs de venta con la tasa de hoy y avisa si cambio."""
        if not self.controlador_tasas:
            if aviso_extra:
                self.lbl_aviso.setText(aviso_extra)
                self.lbl_aviso.show()
            return
        tasa = self.controlador_tasas.tasa_activa()
        if not tasa or tasa.tasa_venta <= 0:
            return
        if self.spin_precio_venta_usd.value() <= 0:
            return

        self._actualizando = True
        bs_nuevo = redondear_moneda(
            Decimal(str(self.spin_precio_venta_usd.value())) * tasa.tasa_venta,
        )
        self._bs_venta = bs_nuevo
        self._mostrar_equiv_venta()
        self._actualizando = False

        if bs_nuevo != bs_anterior:
            aviso_tasa = (
                f"Precio en Bs. actualizado a la tasa de hoy "
                f"({formatear_bs(tasa.tasa_venta)}). "
                f"Precio anterior: {formatear_bs(bs_anterior)}"
            )
            self.lbl_aviso.setText(
                f"{aviso_extra} {aviso_tasa}".strip() if aviso_extra else aviso_tasa
            )
            self.lbl_aviso.show()
        elif aviso_extra:
            self.lbl_aviso.setText(aviso_extra)
            self.lbl_aviso.show()
        else:
            self.lbl_aviso.hide()

    def _guardar(self) -> None:
        """Valida los campos y guarda el producto en la BD."""
        nombre = self.txt_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Validacion", "El nombre es obligatorio.")
            self.txt_nombre.setFocus()
            return

        categoria_id = self._resolver_categoria_id()
        precio_compra = self._bs_compra
        precio_venta_bs = self._bs_venta
        precio_venta_usd = self.spin_precio_venta_usd.value()
        stock_actual = Decimal(str(self.spin_stock_actual.value()))
        stock_minimo = Decimal(str(self.spin_stock_minimo.value()))
        unidad = self.cmb_unidad.currentText().strip().upper() or "UNIDAD"
        tipo_venta = deducir_tipo_venta(unidad)
        precio_compra_usd = self.spin_precio_compra_usd.value()

        if precio_venta_usd > 0 and precio_venta_bs <= 0:
            QMessageBox.warning(
                self,
                "Validacion",
                "No hay tasa activa. Registre la tasa del dia antes de guardar "
                "para poder calcular el precio de venta en Bs.",
            )
            return
        if precio_compra_usd > 0 and precio_compra <= 0:
            QMessageBox.warning(
                self,
                "Validacion",
                "No hay tasa activa. Registre la tasa del dia antes de guardar "
                "para poder calcular el precio de compra en Bs.",
            )
            return

        try:
            if self.producto:
                producto_id = self.producto.idproducto
                if producto_id is None:
                    msg = "ID de producto no disponible después de guardar"
                    raise RuntimeError(msg)

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
                    categoria_id=categoria_id,
                    precio_compra=precio_compra,
                    precio_venta_bs=precio_venta_bs,
                    precio_venta_usd=Decimal(str(precio_venta_usd)),
                    stock_actual=stock_actual,
                    stock_minimo=stock_minimo,
                    unidad=unidad,
                    tipo_venta=tipo_venta,
                )
            else:
                nuevo = Producto(
                    nombre_producto=nombre,
                    categoria_id=categoria_id,
                    precio_compra=precio_compra,
                    precio_venta_bs=precio_venta_bs,
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

