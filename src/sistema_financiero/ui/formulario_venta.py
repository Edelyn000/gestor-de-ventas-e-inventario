# ============================================================
# ARCHIVO: ui/formulario_venta.py  (POS DE NUEVA VENTA)
# ============================================================
# Pantalla de punto de venta (POS) para registrar una venta.
#
# Flujo:
#   1. CATALOGO (panel izquierdo):
#      - Busqueda en vivo (CampoBusqueda) + fila de categorias.
#      - Grid de productos como botones grandes (3 columnas).
#      - Clic en un producto → se agrega al ticket:
#          UNIDAD     → cantidad 1
#          PESO/GRAMOS → peso por defecto 0.100 (boton en amarillo).
#
#   2. TICKET (panel derecho):
#      - Tabla: Producto | Cant/Peso | P.Unit | Subtotal.
#      - Columna "Cant/Peso" editable con doble clic (recalcula total).
#      - Suprimir elimina la fila seleccionada.
#      - Totales: TOTAL en Bs. y su equivalente en USD con la tasa BCV
#        activa (sin desglose de IVA).
#
#   3. COBRO (multi-pago):
#      - Botones de metodo de pago (efectivo Bs/USD, tarjeta, pago movil,
#        bio-pago, transferencia) → el formulario cambia segun la moneda.
#      - "+ AGREGAR PAGO" (o Enter) acumula pagos; la tabla de pagos
#        muestra metodo, monto y equivalente en Bs.
#      - Regla: se registra SOLO el monto aplicado (la suma de los pagos
#        cubre el total exacto); el cambio se informa en pantalla.
#      - Resumen en vivo: CUBIERTO / RESTANTE (o CAMBIO / PAGO COMPLETO).
#      - F12 o clic "COBRAR" → _finalizar_venta → VentaController.crear()
#        con el desglose (se guarda en la tabla venta_pago).
#
#   4. ANULAR VENTA:
#      - Limpia el ticket actual (venta en curso), sin tocar BD.
#
# --- NO TOCAR: nombre de la clase (FormularioVenta), firma base del
#     __init__ (los parametros nuevos son OPCIONALES al final),
#     logica de crear venta (_finalizar_venta), controladores.
# --- MODIFICABLE: layout, estilos, textos, columnas de tabla, colores,
#     catalogo, filtros, atajos de teclado.
# ============================================================
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import TypedDict

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.caja_service import CajaService
from ..core.producto_controller import ProductoController
from ..core.tasa_cambio_service import TasaCambioService
from ..core.venta_controller import VentaController
from ..models import Producto, TasaCambio
from ..utils import (
    METODO_PAGO_BIO_PAGO,
    METODO_PAGO_EFECTIVO_BS,
    METODO_PAGO_EFECTIVO_USD,
    METODO_PAGO_PAGO_MOVIL,
    METODO_PAGO_TARJETA,
    METODO_PAGO_TRANSFERENCIA,
    METODOS_PAGO,
    MONEDA_BS,
    MONEDA_USD,
    TIPO_VENTA_GRAMOS,
    TIPO_VENTA_PESO,
    TIPO_VENTA_UNIDAD,
    TOLERANCIA_REDONDEO,
    configurar_spinbox_bs,
    configurar_spinbox_usd,
    formatear_bs,
    formatear_stock,
    formatear_usd,
)
from ..utils.logging_setup import registrar_excepcion
from .widgets import CampoBusqueda


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
    transferencia: Decimal


# --- MODIFICABLE: pago individual del desglose multi-pago.
class PagoPOS(TypedDict):
    metodo: str
    moneda: str  # BS | USD
    monto: Decimal  # monto RECIBIDO en su moneda (lo que teclea el cajero)
    monto_bs: Decimal  # monto APLICADO a la venta en bolivares (suma = total)
    vuelto_bs: Decimal  # sobrante devuelto en Bs. (0.00 si el pago es exacto)
    tasa_venta: Decimal | None  # tasa usada al convertir (None si es en Bs.)
    referencia: str


# --- MODIFICABLE: texto de cada boton de metodo de pago.
ETIQUETAS_METODO: dict[str, str] = {
    METODO_PAGO_EFECTIVO_BS: "EFECTIVO Bs",
    METODO_PAGO_EFECTIVO_USD: "EFECTIVO USD",
    METODO_PAGO_TARJETA: "TARJETA",
    METODO_PAGO_PAGO_MOVIL: "PAGO MOVIL",
    METODO_PAGO_BIO_PAGO: "BIOPAGO",
    METODO_PAGO_TRANSFERENCIA: "TRANSFERENCIA",
}


# --- MODIFICABLE: alto de la tabla de pagos.
# El viewport real es tabla.height() - encabezado - reserva del scroll horizontal.
# Medido en Qt6: con height 88 el viewport util es de 56 px y una fila mide 30,
# por lo que con 2 pagos la segunda fila quedaba cortada y SIN scrollbar (era
# imposible ver o borrar los pagos ocultos). El alto se calcula por filas.
# El encabezado lleva ahora un borde inferior de 2px (#2563eb): se suma un
# margen extra para que las filas nunca queden recortadas.
ALTO_ENCABEZADO_PAGOS = 24
ALTO_RESERVA_SCROLL_PAGOS = 16
ALTO_FILA_PAGOS = 30
MIN_FILAS_VISIBLES_PAGOS = 2
MAX_FILAS_VISIBLES_PAGOS = 4
ANCHO_COLUMNA_BORRAR_PAGOS = 58


# ============ POS DE NUEVA VENTA ============
class FormularioVenta(QDialog):
    # --- NO TOCAR: firma base (controladores). Los parametros nuevos
    #     (controlador_caja, nombre_cajero) son OPCIONALES y van al final.
    def __init__(
        self,
        parent: QWidget | None = None,
        controlador_productos: ProductoController | None = None,
        controlador_ventas: VentaController | None = None,
        controlador_tasas: TasaCambioService | None = None,
        controlador_caja: CajaService | None = None,
        nombre_cajero: str | None = None,
    ) -> None:
        super().__init__(parent)

        # --- NO TOCAR: almacenamiento de controladores.
        self.controlador_productos = controlador_productos
        self.controlador_ventas = controlador_ventas
        self.controlador_tasas = controlador_tasas
        self.controlador_caja = controlador_caja
        self.nombre_cajero = nombre_cajero

        # --- MODIFICABLE: titulo y tamaño de la ventana.
        self.setWindowTitle("Nueva Venta")
        self.resize(1300, 750)
        self.setMinimumSize(1024, 680)

        # --- NO TOCAR: estado interno de la venta.
        self.productos_venta: list[ProductoVenta] = []
        self.total_bs = Decimal("0.00")
        # Tasa activa capturada al abrir (se refresca en _finalizar_venta).
        self._tasa: TasaCambio | None = None
        # Catalogo cacheado: evita abrir sesiones de BD por cada tecla.
        self._productos_catalogo: list[Producto] = []
        self._categorias: list[str] = []
        self._categoria_seleccionada = "Todos"
        self._refrescando = False
        # --- NO TOCAR: estado del desglose multi-pago de la venta en curso.
        self.pagos: list[PagoPOS] = []
        self._metodo_actual: str | None = None
        self._botones_metodo: dict[str, QPushButton] = {}

        # --- NO TOCAR: construccion del UI y carga inicial.
        self._setup_ui()
        self._cargar_catalogo()
        self._actualizar_tasa()

    # ------------------------------------------------------------------
    # _setup_ui: construye todos los widgets del POS
    # ------------------------------------------------------------------
    # --- MODIFICABLE COMPLETAMENTE: layout, paneles, atajos, estilos.
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._crear_cabecera(layout)
        layout.addWidget(self._crear_splitter(), 1)

    # --- MODIFICABLE: header del POS (cajero, estado de caja, tasa BCV).
    def _crear_cabecera(self, layout: QVBoxLayout) -> None:
        cabecera = QFrame()
        cabecera.setProperty("rol", "cabecera")
        cabecera.setFixedHeight(56)
        hbox = QHBoxLayout(cabecera)
        hbox.setContentsMargins(20, 8, 20, 8)
        hbox.setSpacing(24)

        self.lbl_titulo = QLabel("NUEVA VENTA")
        self.lbl_titulo.setProperty("rol", "cabecera_titulo")
        hbox.addWidget(self.lbl_titulo)

        hbox.addStretch()

        if self.nombre_cajero:
            lbl_cajero = QLabel(f"Cajero: {self.nombre_cajero}")
        else:
            lbl_cajero = QLabel("Cajero: ---")
        hbox.addWidget(lbl_cajero)

        self.lbl_estado_caja = QLabel("Caja: ---")
        hbox.addWidget(self.lbl_estado_caja)
        self._actualizar_estado_caja()

        self.lbl_tasa = QLabel("Tasa BCV: ---")
        hbox.addWidget(self.lbl_tasa)

        layout.addWidget(cabecera)

    # --- MODIFICABLE: catalogo + ticket separados por un splitter.
    def _crear_splitter(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._crear_panel_catalogo())
        splitter.addWidget(self._crear_panel_ticket())
        splitter.setSizes([600, 700])
        return splitter

    # ------------------------------------------------------------------
    # PANEL CATALOGO: busqueda + categorias + grid de productos
    # ------------------------------------------------------------------
    # --- MODIFICABLE: textos, estilos, numero de columnas del grid.
    def _crear_panel_catalogo(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.campo_busqueda = CampoBusqueda(
            placeholder="Buscar producto por nombre o categoria...",
        )
        self.campo_busqueda.setMinimumHeight(40)
        self.campo_busqueda.textChanged.connect(self._aplicar_filtro)
        self.campo_busqueda.setFocus()
        layout.addWidget(self.campo_busqueda)

        self.fila_categorias = QHBoxLayout()
        self.fila_categorias.setSpacing(6)
        layout.addLayout(self.fila_categorias)

        self.scroll_productos = QScrollArea()
        self.scroll_productos.setWidgetResizable(True)
        self.scroll_productos.setFrameShape(QFrame.Shape.NoFrame)

        contenedor = QWidget()
        self.grid_productos = QGridLayout(contenedor)
        self.grid_productos.setSpacing(8)
        self.scroll_productos.setWidget(contenedor)
        layout.addWidget(self.scroll_productos, 1)

        # --- MODIFICABLE: atajo F1 = enfocar busqueda.
        self._atajo_buscar = QShortcut(QKeySequence(Qt.Key.Key_F1), self)
        self._atajo_buscar.activated.connect(self._enfocar_busqueda)

        return panel

    # --- MODIFICABLE: texto y estilo del boton de producto.
    def _crear_boton_producto(self, producto: Producto) -> QPushButton:
        nombre = producto.nombre_producto
        precio = producto.precio_venta_bs
        stock = formatear_stock(producto.stock_actual)
        es_peso = producto.tipo_venta in (TIPO_VENTA_PESO, TIPO_VENTA_GRAMOS)
        texto = f"{nombre}\n{formatear_bs(precio)}  ·  Stock: {stock}"
        btn = QPushButton(texto)
        btn.setMinimumHeight(64)
        if es_peso:
            btn.setProperty("rol", "producto_peso")
        else:
            btn.setProperty("rol", "producto")
        idproducto = int(str(producto.idproducto))
        btn.clicked.connect(lambda _=False, pid=idproducto: self._agregar_producto_venta(pid))
        return btn

    # --- MODIFICABLE: criterio del boton activo de categoria.
    def _crear_boton_categoria(self, nombre: str) -> QPushButton:
        btn = QPushButton(nombre)
        btn.setCheckable(True)
        btn.setProperty("rol", "categoria")
        if nombre == self._categoria_seleccionada:
            btn.setProperty("rol", "categoria_activa")
        btn.clicked.connect(lambda _=False, cat=nombre: self._seleccionar_categoria(cat))
        return btn

    def _refrescar_botones_categorias(self) -> None:
        """Reconstruye la fila de categorias: [Todos] + categorias de la BD."""
        # Limpiar la fila sin tocar el layout padre.
        while self.fila_categorias.count():
            item = self.fila_categorias.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        nombres = ["Todos"] + self._categorias
        for nombre in nombres:
            self.fila_categorias.addWidget(self._crear_boton_categoria(nombre))
        self.fila_categorias.addStretch()

    def _seleccionar_categoria(self, nombre: str) -> None:
        """Marca la categoria activa y re-aplica el filtro."""
        self._categoria_seleccionada = nombre
        # Reactivar estilo del boton activo (QSS necesita re-polish).
        for i in range(self.fila_categorias.count()):
            item = self.fila_categorias.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, QPushButton):
                widget.setChecked(widget.text() == nombre)
                widget.setProperty(
                    "rol",
                    "categoria_activa" if widget.text() == nombre else "categoria",
                )
                estilo = widget.style()
                if estilo is not None:
                    estilo.unpolish(widget)
                    estilo.polish(widget)
        self._aplicar_filtro()

    # ------------------------------------------------------------------
    # PANEL TICKET: tabla + totales + pago + botonera
    # ------------------------------------------------------------------
    # --- MODIFICABLE: columnas, anchos, estilos del ticket.
    def _crear_panel_ticket(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        columnas: list[tuple[str, int]] = [
            ("Producto", 220),
            ("Cant/Peso", 90),
            ("P.Unit", 90),
            ("Subtotal", 110),
        ]
        self.tabla_productos_venta = QTableWidget()
        self.tabla_productos_venta.setColumnCount(len(columnas))
        self.tabla_productos_venta.setHorizontalHeaderLabels([c[0] for c in columnas])
        for i, (_, ancho) in enumerate(columnas):
            self.tabla_productos_venta.setColumnWidth(i, ancho)
        self.tabla_productos_venta.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        # La columna Cant/Peso se edita con doble clic (flags del item).
        self.tabla_productos_venta.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed,
        )
        self.tabla_productos_venta.itemChanged.connect(self._on_item_cambiado)
        layout.addWidget(self.tabla_productos_venta, 1)

        # --- MODIFICABLE: formato de totales. Solo se muestra el TOTAL
        #     en Bs y su equivalente en USD (sin desglose informativo de IVA).
        self.lbl_total = QLabel(f"TOTAL: {formatear_bs(Decimal('0.00'))}")
        self.lbl_total.setProperty("rol", "total_gigante")
        self.lbl_total_usd = QLabel("≈ 0,00 USD")
        layout.addWidget(self.lbl_total)
        layout.addWidget(self.lbl_total_usd)

        self._crear_seccion_pago(layout)

        self._crear_botones(layout)

        # --- MODIFICABLE: atajos F12 (cobrar) y Suprimir (eliminar fila).
        self._atajo_cobrar = QShortcut(QKeySequence(Qt.Key.Key_F12), self)
        self._atajo_cobrar.activated.connect(self._finalizar_venta)
        self._atajo_eliminar = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        self._atajo_eliminar.activated.connect(self._eliminar_fila_seleccionada)

        return panel

    # --- MODIFICABLE: seccion de pago (metodos, monto, lista de pagos, resumen).
    def _crear_seccion_pago(self, layout: QVBoxLayout) -> None:
        layout.addSpacing(6)
        # Se guarda como atributo para poder mostrar/ocultar la seccion.
        self.grupo_pago = QGroupBox("Pago")
        vbox_pago = QVBoxLayout(self.grupo_pago)
        vbox_pago.setSpacing(6)

        self._crear_botones_metodo(vbox_pago)
        self._crear_fila_monto(vbox_pago)
        self._crear_fila_referencia(vbox_pago)
        self._crear_tabla_pagos(vbox_pago)
        self._crear_resumen_pagos(vbox_pago)
        self._crear_atajo_pago()

        # Arranca sin metodo elegido: no se puede agregar hasta elegir uno.
        self._actualizar_form_pago()

        # Oculto hasta que se agregue al menos un producto.
        self.grupo_pago.setVisible(False)
        layout.addWidget(self.grupo_pago)

    # --- MODIFICABLE: grid de botones de metodo de pago (3 columnas).
    def _crear_botones_metodo(self, vbox_pago: QVBoxLayout) -> None:
        grid_metodos = QGridLayout()
        grid_metodos.setSpacing(6)
        for indice, metodo in enumerate(METODOS_PAGO):
            boton = QPushButton(ETIQUETAS_METODO[metodo])
            boton.setCheckable(True)
            boton.setMinimumHeight(32)
            boton.setProperty("rol", "metodo")
            boton.clicked.connect(lambda _=False, m=metodo: self._seleccionar_metodo(m))
            self._botones_metodo[metodo] = boton
            grid_metodos.addWidget(boton, indice // 3, indice % 3)
        vbox_pago.addLayout(grid_metodos)

    # --- MODIFICABLE: monto + equivalencia en vivo + agregar pago.
    def _crear_fila_monto(self, vbox_pago: QVBoxLayout) -> None:
        fila_monto = QHBoxLayout()
        fila_monto.setSpacing(8)

        self.spin_monto = QDoubleSpinBox()
        configurar_spinbox_bs(self.spin_monto)
        self.spin_monto.setMinimumHeight(32)
        self.spin_monto.valueChanged.connect(self._actualizar_equivalencia)
        fila_monto.addWidget(self.spin_monto, 1)

        self.lbl_equivalencia = QLabel("Selecciona un metodo de pago")
        self.lbl_equivalencia.setProperty("rol", "titulo_tarjeta")
        fila_monto.addWidget(self.lbl_equivalencia, 1)

        self.btn_agregar_pago = QPushButton("+ AGREGAR PAGO")
        self.btn_agregar_pago.setProperty("rol", "primario")
        self.btn_agregar_pago.setMinimumHeight(32)
        self.btn_agregar_pago.clicked.connect(self._agregar_pago)
        fila_monto.addWidget(self.btn_agregar_pago)
        vbox_pago.addLayout(fila_monto)

    # --- MODIFICABLE: referencia / numero de operacion (opcional).
    def _crear_fila_referencia(self, vbox_pago: QVBoxLayout) -> None:
        fila_referencia = QHBoxLayout()
        fila_referencia.setSpacing(8)
        fila_referencia.addWidget(QLabel("Referencia:"))
        self.campo_referencia = QLineEdit()
        self.campo_referencia.setPlaceholderText("Nro. de operacion (opcional)")
        fila_referencia.addWidget(self.campo_referencia, 1)
        vbox_pago.addLayout(fila_referencia)

    # --- MODIFICABLE: tabla de pagos agregados (metodo, monto, Bs., vuelto).
    def _crear_tabla_pagos(self, vbox_pago: QVBoxLayout) -> None:
        self.tabla_pagos = QTableWidget()
        self.tabla_pagos.setColumnCount(5)
        self.tabla_pagos.setHorizontalHeaderLabels(
            ["Metodo", "Monto", "Aplicado Bs.", "Vuelto", ""]
        )
        self.tabla_pagos.setColumnWidth(1, 95)
        self.tabla_pagos.setColumnWidth(2, 105)
        self.tabla_pagos.setColumnWidth(3, 95)
        # La columna del metodo absorbe el ancho sobrante y la de Borrar queda
        # con ancho fijo: asi ninguna columna se sale del viewport y el boton
        # Borrar siempre es visible (antes la ultima seccion se estiraba mas
        # alla del viewport y el boton quedaba recortado).
        encabezado_pagos = self.tabla_pagos.horizontalHeader()
        if encabezado_pagos is not None:
            encabezado_pagos.setStretchLastSection(False)
            encabezado_pagos.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            encabezado_pagos.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            self.tabla_pagos.setColumnWidth(4, ANCHO_COLUMNA_BORRAR_PAGOS)
        barra_pagos = self.tabla_pagos.verticalScrollBar()
        if barra_pagos is not None:
            barra_pagos.setSingleStep(ALTO_FILA_PAGOS)
        self._ajustar_alto_tabla_pagos()
        self.tabla_pagos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla_pagos.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        vbox_pago.addWidget(self.tabla_pagos)

    # --- MODIFICABLE: alto de la tabla segun la cantidad de pagos.
    def _ajustar_alto_tabla_pagos(self) -> None:
        """Muestra hasta MAX_FILAS_VISIBLES_PAGOS filas; el resto con scrollbar."""
        filas = min(self.tabla_pagos.rowCount(), MAX_FILAS_VISIBLES_PAGOS)
        filas = max(filas, MIN_FILAS_VISIBLES_PAGOS)
        alto = (
            ALTO_ENCABEZADO_PAGOS
            + ALTO_RESERVA_SCROLL_PAGOS
            + filas * ALTO_FILA_PAGOS
            + 2  # borde del marco
        )
        self.tabla_pagos.setFixedHeight(alto)

    # --- MODIFICABLE: resumen CUBIERTO / RESTANTE (o CAMBIO / COMPLETO).
    def _crear_resumen_pagos(self, vbox_pago: QVBoxLayout) -> None:
        fila_resumen = QHBoxLayout()
        self.lbl_cubierto = QLabel(f"CUBIERTO: {formatear_bs(Decimal('0.00'))}")
        self.lbl_cubierto.setProperty("rol", "titulo_tarjeta")
        self.lbl_restante = QLabel("RESTANTE: 0,00 Bs.")
        self.lbl_restante.setProperty("rol", "resumen_falta")
        fila_resumen.addWidget(self.lbl_cubierto)
        fila_resumen.addStretch()
        fila_resumen.addWidget(self.lbl_restante)
        vbox_pago.addLayout(fila_resumen)

    # --- MODIFICABLE: Enter dentro de la seccion de pago = agregar pago.
    def _crear_atajo_pago(self) -> None:
        self._atajo_agregar_pago = QShortcut(QKeySequence(Qt.Key.Key_Return), self.grupo_pago)
        self._atajo_agregar_pago.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._atajo_agregar_pago.activated.connect(self._agregar_pago)

    # ------------------------------------------------------------------
    # Multi-pago: metodos, monto aplicado, resumen y conversion a Bs.
    # ------------------------------------------------------------------
    # --- MODIFICABLE: resaltado del boton activo.
    def _seleccionar_metodo(self, metodo: str) -> None:
        """Marca el metodo de pago activo y prepara el formulario."""
        self._metodo_actual = metodo
        for nombre, boton in self._botones_metodo.items():
            activo = nombre == metodo
            boton.setChecked(activo)
            self._set_rol(boton, "metodo_activo" if activo else "metodo")
        self._actualizar_form_pago()

    # --- MODIFICABLE: pre-llenado del monto segun el faltante.
    def _actualizar_form_pago(self) -> None:
        """Adapta el formulario al metodo elegido y pre-llena el faltante."""
        metodo = self._metodo_actual
        if metodo is None:
            self.spin_monto.setEnabled(False)
            self.btn_agregar_pago.setEnabled(False)
            self.lbl_equivalencia.setText("Selecciona un metodo de pago")
            return

        es_usd = metodo == METODO_PAGO_EFECTIVO_USD
        # Sin tasa activa no se puede convertir ni cobrar en USD.
        sin_tasa = es_usd and not self._tasa_valida()
        self.spin_monto.setEnabled(not sin_tasa)
        self.btn_agregar_pago.setEnabled(not sin_tasa)

        if es_usd:
            configurar_spinbox_usd(self.spin_monto)
        else:
            configurar_spinbox_bs(self.spin_monto)

        if sin_tasa:
            self.spin_monto.setValue(0.0)
            self.lbl_equivalencia.setText("Sin tasa BCV activa: no se puede cobrar en USD")
            return

        # Pre-llenar con el faltante (en USD se redondea HACIA ARRIBA para
        # no quedar un centimo por debajo al reconvertir a bolivares).
        faltante = self._monto_restante_bs()
        if faltante <= TOLERANCIA_REDONDEO:
            self.spin_monto.setValue(0.0)
        else:
            self.spin_monto.setValue(float(self._en_moneda(faltante, es_usd)))
        self._actualizar_equivalencia()
        self.spin_monto.setFocus()
        self.spin_monto.selectAll()

    # --- MODIFICABLE: equivalencia y cambio mostrados en vivo.
    def _actualizar_equivalencia(self) -> None:
        """Muestra el equivalente en la otra moneda y el cambio si sobra."""
        if self._metodo_actual is None:
            return

        monto = self._centimos(Decimal(str(self.spin_monto.value())))
        es_usd = self._metodo_actual == METODO_PAGO_EFECTIVO_USD
        if not self._tasa_valida():
            self.lbl_equivalencia.setText("Sin tasa BCV activa")
            return

        aplicado_bs = self._monto_aplicado_bs(monto, es_usd)
        if es_usd:
            texto = f"= {formatear_bs(aplicado_bs)}"
        else:
            assert self._tasa is not None
            texto = f"≈ {formatear_usd(self._centimos(monto / self._tasa.tasa_venta))}"

        # Si el monto tecleado supera el faltante, se informa el cambio
        # (solo se registra el monto aplicado, no el tecleado).
        faltante = self._monto_restante_bs()
        if faltante > TOLERANCIA_REDONDEO and aplicado_bs > faltante + TOLERANCIA_REDONDEO:
            texto += f"  ·  CAMBIO: {formatear_bs(aplicado_bs - faltante)}"
        self.lbl_equivalencia.setText(texto)

    # --- MODIFICABLE: validaciones previas al alta de un pago.
    def _agregar_pago(self) -> None:
        """Agrega el pago tecleado a la lista (solo el monto aplicado)."""
        if self._metodo_actual is None:
            QMessageBox.warning(self, "Pago", "Selecciona un metodo de pago.")
            return

        monto = self._centimos(Decimal(str(self.spin_monto.value())))
        if monto <= 0:
            QMessageBox.warning(self, "Pago", "Ingresa un monto mayor a cero.")
            return

        faltante = self._monto_restante_bs()
        if faltante <= TOLERANCIA_REDONDEO:
            QMessageBox.information(self, "Pago", "La venta ya esta cubierta.")
            return

        es_usd = self._metodo_actual == METODO_PAGO_EFECTIVO_USD
        aplicado_bs = self._monto_aplicado_bs(monto, es_usd)
        vuelto_bs = Decimal("0.00")
        if aplicado_bs > faltante + TOLERANCIA_REDONDEO:
            # El sobrante es vuelto: se registra SOLO lo aplicado (el
            # faltante exacto) y el cambio queda visible en la fila.
            # Es lo que permite cobrar en USD aunque la tasa no divida
            # exacto el total (1 centavo USD vale tasa/100 Bs.).
            vuelto_bs = self._centimos(aplicado_bs - faltante)
            aplicado_bs = self._centimos(faltante)

        self.pagos.append(
            {
                "metodo": self._metodo_actual,
                "moneda": MONEDA_USD if es_usd else MONEDA_BS,
                "monto": monto,
                "monto_bs": aplicado_bs,
                "vuelto_bs": vuelto_bs,
                "tasa_venta": self._tasa.tasa_venta if (es_usd and self._tasa) else None,
                "referencia": self.campo_referencia.text().strip(),
            }
        )
        self.campo_referencia.clear()
        self._refrescar_tabla_pagos()
        self._actualizar_resumen_pagos()
        # Deja el formulario listo para el siguiente pago (o en 0 si ya cubre).
        self._actualizar_form_pago()

    # --- MODIFICABLE: eliminacion de un pago del desglose.
    def _eliminar_pago(self, fila: int) -> None:
        """Quita de la lista el pago de la fila indicada."""
        if not 0 <= fila < len(self.pagos):
            return
        self.pagos.pop(fila)
        self._refrescar_tabla_pagos()
        self._actualizar_resumen_pagos()
        self._actualizar_form_pago()

    # --- MODIFICABLE: formato de la tabla de pagos.
    def _refrescar_tabla_pagos(self) -> None:
        """Reconstruye la tabla de pagos a partir de self.pagos."""
        self.tabla_pagos.setRowCount(len(self.pagos))
        for fila, pago in enumerate(self.pagos):
            es_usd = pago["moneda"] == MONEDA_USD
            monto_txt = formatear_usd(pago["monto"]) if es_usd else formatear_bs(pago["monto"])
            etiqueta = ETIQUETAS_METODO.get(pago["metodo"], pago["metodo"])
            if pago["referencia"]:
                etiqueta = f"{etiqueta} ({pago['referencia']})"
            vuelto = pago["vuelto_bs"]
            valores = [
                etiqueta,
                monto_txt,
                formatear_bs(pago["monto_bs"]),
                formatear_bs(vuelto) if vuelto > 0 else "",
            ]
            for columna, texto in enumerate(valores):
                celda = QTableWidgetItem(texto)
                celda.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.tabla_pagos.setItem(fila, columna, celda)

            btn_quitar = QPushButton("Borrar")
            btn_quitar.setProperty("rol", "quitar_pago")
            # Tamano fijo: el boton tiene que entrar en la columna Borrar sin
            # depender del QSS (el estilo por defecto pide 81px de ancho). El
            # alto deja margen dentro de la fila (ALTO_FILA_PAGOS).
            btn_quitar.setFixedSize(ANCHO_COLUMNA_BORRAR_PAGOS - 12, ALTO_FILA_PAGOS - 8)
            btn_quitar.clicked.connect(lambda _=False, f=fila: self._eliminar_pago(f))
            self.tabla_pagos.setCellWidget(fila, 4, btn_quitar)

        self._ajustar_alto_tabla_pagos()

    # --- MODIFICABLE: textos/colores del resumen de cobertura.
    def _actualizar_resumen_pagos(self) -> None:
        """Muestra CUBIERTO y RESTANTE (o CAMBIO / PAGO COMPLETO)."""
        cubierto = self._monto_cubierto_bs()
        restante = self._monto_restante_bs()
        self.lbl_cubierto.setText(f"CUBIERTO: {formatear_bs(cubierto)}")
        self._set_rol(self.lbl_cubierto, "resumen_ok" if cubierto > 0 else "titulo_tarjeta")

        if restante > TOLERANCIA_REDONDEO:
            self.lbl_restante.setText(f"RESTANTE: {formatear_bs(restante)}")
            self._set_rol(self.lbl_restante, "resumen_falta")
        elif restante < -TOLERANCIA_REDONDEO:
            self.lbl_restante.setText(f"CAMBIO: {formatear_bs(-restante)}")
            self._set_rol(self.lbl_restante, "resumen_ok")
        else:
            self.lbl_restante.setText("PAGO COMPLETO")
            self._set_rol(self.lbl_restante, "resumen_ok")

    # --- NO TOCAR: suma de lo cubierto; la tasa manda sobre la moneda.
    def _monto_cubierto_bs(self) -> Decimal:
        """Total ya cubierto por los pagos agregados (en Bs.)."""
        return sum((pago["monto_bs"] for pago in self.pagos), Decimal("0.00"))

    # --- NO TOCAR: restante contra el total del ticket (negativo = cambio).
    def _monto_restante_bs(self) -> Decimal:
        """Lo que falta por cubrir (negativo = cambio a devolver)."""
        return self.total_bs - self._monto_cubierto_bs()

    def _tasa_valida(self) -> bool:
        """Indica si hay una tasa activa usable para convertir montos."""
        return self._tasa is not None and self._tasa.tasa_venta > 0

    @staticmethod
    def _centimos(valor: Decimal) -> Decimal:
        """Cuantiza un monto a centimos (redondeo comercial)."""
        return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _en_moneda(self, monto_bs: Decimal, es_usd: bool) -> Decimal:
        """Convierte un monto en Bs. a la moneda del metodo activo."""
        if not es_usd:
            return self._centimos(monto_bs)
        if not self._tasa_valida():
            return Decimal("0.00")
        assert self._tasa is not None
        return (monto_bs / self._tasa.tasa_venta).quantize(Decimal("0.01"), rounding=ROUND_CEILING)

    def _monto_aplicado_bs(self, monto: Decimal, es_usd: bool) -> Decimal:
        """Equivalente en Bs. del monto tecleado (sin recortar)."""
        if not es_usd:
            return monto
        if not self._tasa_valida():
            return Decimal("0.00")
        assert self._tasa is not None
        return self._centimos(monto * self._tasa.tasa_venta)

    def _recalcular_equivalencias(self) -> None:
        """Recalcula el equivalente en Bs. de los pagos en USD (tasa nueva).

        Solo se recalcula cuando la tasa efectivamente cambio: mientras la
        tasa siga igual, el monto aplicado y el vuelto por redondeo siguen
        siendo validos (recalcular siempre volveria a inventar el descuadre
        de 1 centavo que el recorte ya resolvio).
        """
        if not self._tasa_valida():
            return
        assert self._tasa is not None
        tasa_actual = self._tasa.tasa_venta
        for pago in self.pagos:
            if pago["moneda"] != MONEDA_USD or pago["tasa_venta"] == tasa_actual:
                continue
            pago["tasa_venta"] = tasa_actual
            pago["monto_bs"] = self._monto_aplicado_bs(pago["monto"], True)
            # Con otra tasa el vuelto por redondeo deja de ser valido:
            # se descarta y el resumen muestra el descuadre real.
            pago["vuelto_bs"] = Decimal("0.00")

    # --- NO TOCAR: espejo de VentaController._derivar_metodo_pago.
    def _pagos_a_metodo_pago(self) -> dict[str, object]:
        """Resume los pagos por metodo (mismo criterio que el controlador)."""
        acumulado: dict[str, Decimal] = dict.fromkeys(METODOS_PAGO, Decimal("0.00"))
        for pago in self.pagos:
            metodo = pago["metodo"]
            valor = pago["monto"] if metodo == METODO_PAGO_EFECTIVO_USD else pago["monto_bs"]
            acumulado[metodo] += valor

        # dict[str, object] explicito: VentaController.crear lo tipa asi.
        resumen: dict[str, object] = {}
        for nombre, monto in acumulado.items():
            resumen[nombre] = monto
        return resumen

    @staticmethod
    def _set_rol(widget: QWidget, rol: str) -> None:
        """Cambia el rol QSS de un widget y lo repinta."""
        widget.setProperty("rol", rol)
        estilo = widget.style()
        if estilo is not None:
            estilo.unpolish(widget)
            estilo.polish(widget)

    # --- MODIFICABLE: textos y estilos de botones (Anular Venta, Cobrar).
    def _crear_botones(self, layout: QVBoxLayout) -> None:
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_anular = QPushButton("ANULAR VENTA")
        self.btn_anular.setProperty("rol", "anular")
        self.btn_anular.setMinimumHeight(48)
        self.btn_anular.clicked.connect(self._limpiar_ticket)
        btn_layout.addWidget(self.btn_anular)

        # --- NO TOCAR: conexion a _finalizar_venta.
        self.btn_cobrar = QPushButton("COBRAR (F12)")
        self.btn_cobrar.setProperty("rol", "cobrar")
        self.btn_cobrar.setMinimumHeight(48)
        self.btn_cobrar.clicked.connect(self._finalizar_venta)
        btn_layout.addWidget(self.btn_cobrar)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # _cargar_catalogo: llena el grid con productos filtrables en memoria
    # ------------------------------------------------------------------
    # --- MODIFICABLE: camino de datos (listar_todos + categorias).
    def _cargar_catalogo(self) -> None:
        if not self.controlador_productos:
            return

        # --- NO TOCAR: llamadas al controlador para listar productos/categorias.
        self._productos_catalogo = self.controlador_productos.listar_todos()
        self._categorias = self.controlador_productos.obtener_categorias()
        self._refrescar_botones_categorias()
        self._aplicar_filtro()

    # --- MODIFICABLE: criterio de filtro (nombre o categoria, insensible a mayusculas).
    def _aplicar_filtro(self) -> None:
        """Reconstruye el grid segun el texto de busqueda y la categoria."""
        termino = self.campo_busqueda.text().strip().lower()

        # Limpiar el grid sin tocar el layout padre.
        while self.grid_productos.count():
            item = self.grid_productos.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        productos_filtrados: list[Producto] = []
        for producto in self._productos_catalogo:
            categoria = producto.categoria or ""
            nombre = producto.nombre_producto.lower()
            coincide_categoria = self._categoria_seleccionada in {"Todos", categoria}
            if not coincide_categoria:
                continue
            if termino and termino not in nombre and termino not in categoria.lower():
                continue
            productos_filtrados.append(producto)

        for columna, producto in enumerate(productos_filtrados):
            fila = columna // 3
            col = columna % 3
            self.grid_productos.addWidget(self._crear_boton_producto(producto), fila, col)

    # ------------------------------------------------------------------
    # _actualizar_tasa: muestra la tasa de cambio activa en la UI
    # ------------------------------------------------------------------
    # --- MODIFICABLE: texto de la tasa. NO TOCAR la llamada a tasa_activa().
    def _actualizar_tasa(self) -> None:
        """Actualiza el label de la tasa de cambio y guarda la tasa activa."""
        if not self.controlador_tasas:
            return
        # ADVERTENCIA: tasa_activa() cierra la sesión. Solo columnas directas.
        tasa = self.controlador_tasas.tasa_activa()
        self._tasa = tasa
        if tasa:
            self.lbl_tasa.setText(
                f"Tasa BCV: {formatear_bs(tasa.tasa_venta)} / USD  (activa: {tasa.fecha})"
            )
        else:
            self.lbl_tasa.setText("Tasa BCV: No hay tasa activa registrada.")

    # --- MODIFICABLE: estado de caja mostrado en el header.
    def _actualizar_estado_caja(self) -> None:
        """Muestra el estado de la caja (ABIERTA/CERRADA) si hay controlador."""
        if not self.controlador_caja:
            return
        if self.controlador_caja.obtener_caja_abierta() is not None:
            self.lbl_estado_caja.setText("Caja: ABIERTA")
            self.lbl_estado_caja.setStyleSheet("color: #16a34a; font-weight: bold;")
        else:
            self.lbl_estado_caja.setText("Caja: CERRADA")
            self.lbl_estado_caja.setStyleSheet("color: #dc2626; font-weight: bold;")

    def _enfocar_busqueda(self) -> None:
        """Atajo F1: pone el foco en el campo de busqueda."""
        self.campo_busqueda.setFocus()
        self.campo_busqueda.selectAll()

    # ------------------------------------------------------------------
    # _agregar_producto_venta: agrega un producto del catalogo a la venta
    # ------------------------------------------------------------------
    # --- NO TOCAR: logica de validacion de stock y calculo de subtotal.
    #     MODIFICABLE: cantidad por defecto segun tipo de venta.
    def _agregar_producto_venta(self, idproducto: int) -> None:
        """Agrega el producto indicado (clic en el boton del catalogo)."""
        if self.controlador_productos is None or self.controlador_ventas is None:
            msg = "Controladores no inicializados"
            raise RuntimeError(msg)

        # --- NO TOCAR: obtencion del producto desde el controlador.
        producto = self.controlador_productos.obtener_por_id(int(idproducto))
        if not producto:
            QMessageBox.warning(self, "Error", "El producto no existe.")
            return

        # --- MODIFICABLE: cantidad por defecto: UNIDAD=1, PESO/GRAMOS=0.100.
        cantidad = Decimal("1.00") if producto.tipo_venta == TIPO_VENTA_UNIDAD else Decimal("0.100")

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
        self._actualizar_visibilidad_pago()

    # ------------------------------------------------------------------
    # _refrescar_tabla_productos: actualiza la tabla con los productos agregados
    # ------------------------------------------------------------------
    # --- MODIFICABLE: formato de la tabla (como se muestran los datos).
    def _refrescar_tabla_productos(self) -> None:
        """Refresca la tabla de productos de la venta."""
        self._refrescando = True
        try:
            self.tabla_productos_venta.setRowCount(len(self.productos_venta))

            for fila, item in enumerate(self.productos_venta):
                celda_nombre = QTableWidgetItem(item["nombre"])
                celda_nombre.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable,
                )
                self.tabla_productos_venta.setItem(fila, 0, celda_nombre)

                celda_cantidad = QTableWidgetItem(str(item["cantidad"]))
                celda_cantidad.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEditable,
                )
                self.tabla_productos_venta.setItem(fila, 1, celda_cantidad)

                precio = QTableWidgetItem(formatear_bs(item["precio"]))
                precio.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable,
                )
                self.tabla_productos_venta.setItem(fila, 2, precio)

                subtotal = QTableWidgetItem(formatear_bs(item["subtotal"]))
                subtotal.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable,
                )
                self.tabla_productos_venta.setItem(fila, 3, subtotal)
        finally:
            self._refrescando = False

    # ------------------------------------------------------------------
    # _on_item_cambiado: recalcula subtotal y totales al editar Cant/Peso
    # ------------------------------------------------------------------
    # --- MODIFICABLE: formato aceptado de cantidad. NO TOCAR: validacion
    #     de stock, recalculado de subtotal y del total.
    def _on_item_cambiado(self, item: QTableWidgetItem) -> None:
        """Reacciona a la edicion de la columna Cant/Peso en el ticket."""
        if self._refrescando or item.column() != 1:
            return

        fila = item.row()
        if not (0 <= fila < len(self.productos_venta)):
            return

        try:
            nueva_cantidad = Decimal(item.text().strip())
        except Exception:
            nueva_cantidad = Decimal("0.00")

        # --- NO TOCAR: validacion de stock.
        if nueva_cantidad <= 0 or self.controlador_productos is None:
            self._revertir_cantidad()
            return

        idproducto = int(str(self.productos_venta[fila]["idproducto"]))
        producto = self.controlador_productos.obtener_por_id(idproducto)
        if producto is None:
            self._revertir_cantidad()
            return
        if producto.stock_actual < nueva_cantidad:
            QMessageBox.warning(
                self,
                "Stock insuficiente",
                f"Stock disponible: {producto.stock_actual}. Solicitado: {nueva_cantidad}.",
            )
            self._revertir_cantidad()
            return

        # --- NO TOCAR: recalculado de subtotal y del total.
        nuevo_subtotal = self.productos_venta[fila]["precio"] * nueva_cantidad
        self.total_bs -= self.productos_venta[fila]["subtotal"]
        self.productos_venta[fila]["cantidad"] = nueva_cantidad
        self.productos_venta[fila]["subtotal"] = nuevo_subtotal
        self.total_bs += nuevo_subtotal
        self._refrescar_tabla_productos()
        self._actualizar_total()

    def _revertir_cantidad(self) -> None:
        """Restaura la cantidad almacenada si la edicion fue invalida."""
        self._refrescar_tabla_productos()

    # ------------------------------------------------------------------
    # _actualizar_total: actualiza los labels de total (desglose IVA informativo)
    # ------------------------------------------------------------------
    # --- MODIFICABLE: formato del texto de los totales. Solo se muestra
    #     el TOTAL en Bs y su equivalente en USD (sin desglose de IVA).
    def _actualizar_total(self) -> None:
        """Actualiza el total en Bs y su equivalente en USD."""
        self.lbl_total.setText(f"TOTAL: {formatear_bs(self.total_bs)}")

        # Equivalente en USD con la tasa activa (si existe).
        tasa = self._tasa
        if tasa and tasa.tasa_venta > 0:
            total_usd = (self.total_bs / tasa.tasa_venta).quantize(Decimal("0.01"))
            self.lbl_total_usd.setText(f"≈ {formatear_usd(total_usd)}")
        else:
            self.lbl_total_usd.setText("≈ 0,00 USD")

        # El total manda sobre el desglose: recalcula CUBIERTO/RESTANTE.
        self._actualizar_resumen_pagos()

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
            self._actualizar_visibilidad_pago()

    # --- MODIFICABLE: criterio de la fila a eliminar (seleccion actual).
    def _eliminar_fila_seleccionada(self) -> None:
        """Suprimir: elimina la fila seleccionada del ticket."""
        fila = self.tabla_productos_venta.currentRow()
        if fila >= 0 and fila < len(self.productos_venta):
            self._eliminar_producto_venta(fila)

    # ------------------------------------------------------------------
    # _limpiar_ticket: ANULAR VENTA → vacia el ticket actual (sin BD)
    # ------------------------------------------------------------------
    # --- MODIFICABLE: confirmacion opcional antes de limpiar.
    def _limpiar_ticket(self) -> None:
        """Anula la venta en curso: limpia el ticket y los totales."""
        if not self.productos_venta:
            return
        self.productos_venta = []
        self.total_bs = Decimal("0.00")
        self._reiniciar_pagos()
        self._refrescar_tabla_productos()
        self._actualizar_total()
        self._actualizar_visibilidad_pago()

    # --- MODIFICABLE: estado limpio del desglose de pagos.
    def _reiniciar_pagos(self) -> None:
        """Descarta el desglose de pagos de la venta en curso."""
        self.pagos = []
        self._metodo_actual = None
        for boton in self._botones_metodo.values():
            boton.setChecked(False)
            self._set_rol(boton, "metodo")
        self.campo_referencia.clear()
        self._refrescar_tabla_pagos()
        self._actualizar_resumen_pagos()
        self._actualizar_form_pago()

    # ------------------------------------------------------------------
    # _actualizar_visibilidad_pago: muestra el pago solo si hay productos
    # ------------------------------------------------------------------
    # --- MODIFICABLE: criterio de visibilidad de la seccion de pago.
    def _actualizar_visibilidad_pago(self) -> None:
        """Muestra el metodo de pago solo cuando hay productos en la venta."""
        hay_productos = bool(self.productos_venta)
        self.grupo_pago.setVisible(hay_productos)
        # Sin ticket no hay venta en curso a la que pertenezcan los pagos.
        if not hay_productos and self.pagos:
            self._reiniciar_pagos()

    # ------------------------------------------------------------------
    # _finalizar_venta: valida y guarda la venta en la BD
    # ------------------------------------------------------------------
    # --- NO TOCAR: logica de finalizacion de venta (llamada al controlador).
    def _finalizar_venta(self) -> None:
        """Valida los datos y finaliza la venta."""
        if not self.productos_venta:
            QMessageBox.warning(self, "Venta vacia", "Agrega al menos un producto a la venta.")
            return

        # --- MODIFICABLE: el cobro exige al menos un pago del desglose.
        if not self.pagos:
            QMessageBox.warning(
                self,
                "Pago",
                "Agrega al menos un pago para cobrar la venta.",
            )
            return

        # --- NO TOCAR: refrescar tasa antes de crear (valor del momento).
        self._actualizar_tasa()

        # La tasa pudo cambiar: recalcular el equivalente en Bs. de los
        # pagos en USD y volver a validar la cobertura contra el total.
        self._recalcular_equivalencias()
        self._refrescar_tabla_pagos()
        self._actualizar_resumen_pagos()

        restante = self._monto_restante_bs()
        if restante > TOLERANCIA_REDONDEO:
            QMessageBox.warning(
                self,
                "Pago incompleto",
                f"Falta por cubrir: {formatear_bs(restante)}\n\n"
                "Si cambio la tasa BCV, elimina los pagos en USD y agregalos de nuevo.",
            )
            return
        if restante < -TOLERANCIA_REDONDEO:
            QMessageBox.warning(
                self,
                "Pago de mas",
                f"Los pagos superan el total en {formatear_bs(-restante)}\n\n"
                "Ajusta el desglose antes de cobrar (no se devuelve el cambio "
                "en la venta). Si cambio la tasa BCV, elimina los pagos en USD "
                "y agregalos de nuevo.",
            )
            return

        # --- NO TOCAR: preparacion de datos para el controlador.
        productos: list[dict[str, object]] = [
            {
                "idproducto": int(str(item["idproducto"])),
                "cantidad": item["cantidad"],
            }
            for item in self.productos_venta
        ]

        # --- MODIFICABLE: origen de los montos (desglose multi-pago).
        metodo_pago: dict[str, object] = self._pagos_a_metodo_pago()
        pagos: list[dict[str, object]] = [
            {
                "metodo": pago["metodo"],
                "moneda": pago["moneda"],
                "monto": pago["monto"],
                "monto_bs": pago["monto_bs"],
                "referencia": pago["referencia"],
            }
            for pago in self.pagos
        ]

        if self.controlador_ventas is None:
            msg = "Controlador de ventas no inicializado"
            raise RuntimeError(msg)
        try:
            # --- NO TOCAR: llamada al controlador para crear la venta.
            venta = self.controlador_ventas.crear(productos, metodo_pago, pagos=pagos)

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
        except Exception as e:
            registrar_excepcion(e, "FormularioVenta._finalizar_venta")
            QMessageBox.critical(
                self,
                "Error inesperado",
                f"No se pudo crear la venta.\n{e}",
            )
