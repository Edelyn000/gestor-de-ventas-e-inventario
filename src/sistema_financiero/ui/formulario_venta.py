import logging
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import TypedDict

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut, QShowEvent
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
from ..models import Producto, TasaCambio, Venta
from ..utils import (
    MAX_KILOS_CAPTURA,
    METODO_PAGO_BIO_PAGO,
    METODO_PAGO_EFECTIVO_BS,
    METODO_PAGO_EFECTIVO_USD,
    METODO_PAGO_PAGO_MOVIL,
    METODO_PAGO_TARJETA,
    METODO_PAGO_TRANSFERENCIA,
    METODOS_PAGO,
    MONEDA_BS,
    MONEDA_USD,
    ORIGEN_TASA_MANUAL,
    PASOS_PESO_RAPIDO,
    TOLERANCIA_REDONDEO,
    a_kg,
    a_local,
    configurar_spinbox_bs,
    configurar_spinbox_usd,
    descomponer_kg,
    es_medida,
    formatear_bs,
    formatear_bs_sin_sufijo,
    formatear_peso_kg,
    formatear_stock,
    formatear_usd,
    hoy,
)
from ..utils.logging_setup import registrar_evento, registrar_excepcion
from .dialogo_factura import DialogoFactura
from .dialogo_tasa_manual import DialogoTasaManual
from .widgets import CampoBusqueda, SpinBoxStock


# ProductoVenta: Item del carrito del POS con cantidad y precios.
class ProductoVenta(TypedDict):
    idproducto: int | None
    nombre: str
    cantidad: Decimal
    precio: Decimal
    subtotal: Decimal
    tipo_venta: str


# MetodoPago: Metodo de pago seleccionado en el POS.
class MetodoPago(TypedDict):
    efectivo_bs: Decimal
    efectivo_usd: Decimal
    tarjeta: Decimal
    pago_movil: Decimal
    bio_pago: Decimal
    transferencia: Decimal


# PagoPOS: Pago parcial del POS con aplicado y vuelto.
class PagoPOS(TypedDict):
    metodo: str
    moneda: str
    monto: Decimal
    monto_bs: Decimal
    vuelto_bs: Decimal
    tasa_venta: Decimal | None
    referencia: str


ETIQUETAS_METODO: dict[str, str] = {
    METODO_PAGO_EFECTIVO_BS: "EFECTIVO Bs",
    METODO_PAGO_EFECTIVO_USD: "EFECTIVO USD",
    METODO_PAGO_TARJETA: "TARJETA",
    METODO_PAGO_PAGO_MOVIL: "PAGO MOVIL",
    METODO_PAGO_BIO_PAGO: "BIOPAGO",
    METODO_PAGO_TRANSFERENCIA: "TRANSFERENCIA",
}

METODOS_PAGO_DIGITALES: frozenset[str] = frozenset(
    {
        METODO_PAGO_TARJETA,
        METODO_PAGO_PAGO_MOVIL,
        METODO_PAGO_BIO_PAGO,
        METODO_PAGO_TRANSFERENCIA,
    }
)


ALTO_ENCABEZADO_PAGOS = 24
ALTO_RESERVA_SCROLL_PAGOS = 16
ALTO_FILA_PAGOS = 30
MIN_FILAS_VISIBLES_PAGOS = 2
MAX_FILAS_VISIBLES_PAGOS = 4
ANCHO_COLUMNA_BORRAR_PAGOS = 58

ANCHO_COLUMNA_KG = 88
ANCHO_COLUMNA_GRAMOS = 88
ALTO_CASILLA_PESO = 34
MARGEN_CASILLA_PESO = 2

ANCHO_COLUMNA_PRECIO = 70
ANCHO_COLUMNA_IMPORTE = 100
ANCHO_COLUMNA_QUITAR = 48

ANCHO_MINIMO_TICKET = 621
PROPORCION_PANEL_TICKET = 0.54

ANCHO_BOTON_PESO_RAPIDO = 50
ALTO_BOTON_PESO_RAPIDO = 24
ANCHO_BOTON_AGREGAR_UNIDAD = 34
SEPARACION_BOTON_PESO_RAPIDO = 3
MARGEN_IZQ_GRUPO_PESO = 4
MARGEN_DER_GRUPO_PESO = 10
MARGEN_V_GRUPO_PESO = 4
ANCHO_COLUMNA_PESO_RAPIDO = (
    MARGEN_IZQ_GRUPO_PESO
    + 2 * ANCHO_BOTON_PESO_RAPIDO
    + SEPARACION_BOTON_PESO_RAPIDO
    + MARGEN_DER_GRUPO_PESO
)
ANCHO_COLUMNA_ACCION_CATALOGO = 44

ETIQUETAS_PESO_RAPIDO: tuple[str, ...] = ("1kg", "1/2", "1/4", "100g")
ETIQUETAS_PESO_RAPIDO_LARGAS: tuple[str, ...] = (
    "1 Kg",
    "1/2 Kg (500 g)",
    "1/4 Kg (250 g)",
    "100 g",
)

PESO_POR_DEFECTO_KG = Decimal("1.000")

ALTO_FILA_TICKET = 2 * ALTO_BOTON_PESO_RAPIDO + 2 * SEPARACION_BOTON_PESO_RAPIDO + 12


# FormularioVenta: POS de venta: catalogo, ticket, pago y factura.
class FormularioVenta(QDialog):
    # Construye el POS: cabecera, catalogo, ticket y seccion de pago.
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

        self.controlador_productos = controlador_productos
        self.controlador_ventas = controlador_ventas
        self.controlador_tasas = controlador_tasas
        self.controlador_caja = controlador_caja
        self.nombre_cajero = nombre_cajero

        self.setWindowTitle("Nueva Venta")
        self.resize(1300, 750)
        self.setMinimumSize(1024, 680)

        self.productos_venta: list[ProductoVenta] = []
        self.total_bs = Decimal("0.00")
        self._tasa: TasaCambio | None = None
        self._tasa_manual_activa = False
        self._tasa_base_bcv: Decimal | None = None
        self._reversion_pendiente = False
        self._reversion_avisada_por: Decimal | None = None
        self._productos_catalogo: list[Producto] = []
        self._categorias: list[str] = []
        self._categoria_seleccionada = "Todos"
        self._refrescando = False
        self._layout_ticket = ""
        self.pagos: list[PagoPOS] = []
        self._metodo_actual: str | None = None
        self._botones_metodo: dict[str, QPushButton] = {}
        self._metodo_mixto: str | None = None
        self._botones_mixto: dict[str, QPushButton] = {}

        self._setup_ui()
        self._actualizar_tasa()
        self._cargar_catalogo()

        self._timer_tasa = QTimer(self)
        self._timer_tasa.setInterval(60_000)
        self._timer_tasa.timeout.connect(self._comprobar_tasa_bcv)
        self._timer_tasa.start()

    # Arma el layout raiz del POS y delega en los creadores de secciones.
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._crear_cabecera(layout)
        layout.addWidget(self._crear_splitter(), 1)

    # Crea la barra superior con cajero, estado de caja y tasa.
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
        self.lbl_tasa.setProperty("rol", "tasa_bcv_auto")
        hbox.addWidget(self.lbl_tasa)

        self.btn_tasa_manual = QPushButton("✏️ Tasa Manual")
        self.btn_tasa_manual.setProperty("rol", "tasa_manual_boton")
        self.btn_tasa_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tasa_manual.setEnabled(self.controlador_tasas is not None)
        self.btn_tasa_manual.clicked.connect(self._pedir_tasa_manual)
        hbox.addWidget(self.btn_tasa_manual)

        layout.addWidget(cabecera)

    # Divide la ventana entre catalogo y ticket.
    def _crear_splitter(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        panel_catalogo = self._crear_panel_catalogo()
        panel_ticket = self._crear_panel_ticket()
        panel_ticket.setMinimumWidth(ANCHO_MINIMO_TICKET)
        splitter.addWidget(panel_catalogo)
        splitter.addWidget(panel_ticket)
        splitter.setSizes([600, 700])
        self.splitter_paneles = splitter
        return splitter

    # Reparte el ancho entre catalogo y ticket al mostrar la ventana.
    def showEvent(self, event: QShowEvent | None) -> None:  # noqa: N802 (Qt)
        """Reparte el ancho entre catalogo y ticket al mostrar la ventana."""
        super().showEvent(event)
        self._repartir_paneles()

    # Reparte el ancho util respetando el minimo del ticket.
    def _repartir_paneles(self) -> None:
        splitter = getattr(self, "splitter_paneles", None)
        if splitter is None:
            return
        ancho_util = splitter.width() - splitter.handleWidth()
        if ancho_util <= 0:
            return
        ticket = min(
            max(ANCHO_MINIMO_TICKET, int(ancho_util * PROPORCION_PANEL_TICKET)),
            ancho_util,
        )
        splitter.setSizes([max(0, ancho_util - ticket), ticket])

    # Crea la lista de productos con busqueda, categorias y tabla.
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

        columnas: list[tuple[str, int]] = [
            ("Producto", 240),
            ("USD", 74),
            ("Bs", 86),
            ("Stock", 78),
            ("", ANCHO_COLUMNA_ACCION_CATALOGO),
        ]
        tabla = QTableWidget()
        tabla.setColumnCount(len(columnas))
        tabla.setHorizontalHeaderLabels([c[0] for c in columnas])
        for i, (_, ancho) in enumerate(columnas):
            tabla.setColumnWidth(i, ancho)
        vheader = tabla.verticalHeader()
        if vheader is not None:
            vheader.setVisible(False)
            vheader.setDefaultSectionSize(36)
        tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabla.setShowGrid(False)
        tabla.setAlternatingRowColors(True)
        header = tabla.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tabla.itemDoubleClicked.connect(self._on_catalogo_doble_clic)
        self.tabla_productos_catalogo = tabla
        layout.addWidget(tabla, 1)

        self._atajo_buscar = QShortcut(QKeySequence(Qt.Key.Key_F1), self)
        self._atajo_buscar.activated.connect(self._enfocar_busqueda)
        self._atajo_enter = QShortcut(
            QKeySequence(Qt.Key.Key_Return),
            self.tabla_productos_catalogo,
        )
        self._atajo_enter.activated.connect(self._agregar_fila_activa)
        self._atajo_enter_numpad = QShortcut(
            QKeySequence(Qt.Key.Key_Enter),
            self.tabla_productos_catalogo,
        )
        self._atajo_enter_numpad.activated.connect(self._agregar_fila_activa)

        return panel

    # Precio en Bs.
    def _precio_bs_efectivo(self, producto: Producto) -> Decimal:
        """Precio en Bs. que se muestra y cobra en el POS."""
        if self._tasa is not None and self._tasa.tasa_venta > 0 and producto.precio_venta_usd > 0:
            return (producto.precio_venta_usd * self._tasa.tasa_venta).quantize(
                Decimal("0.01"),
            )
        return producto.precio_venta_bs

    # Ultima celda del catalogo: (+) para UNIDAD y para PESO.
    def _crear_boton_agregar(self, producto: Producto) -> QWidget:
        """Ultima celda del catalogo: (+) para UNIDAD y para PESO."""
        btn = QPushButton("+")
        btn.setFixedSize(ANCHO_BOTON_AGREGAR_UNIDAD, ALTO_BOTON_PESO_RAPIDO)
        if es_medida(producto.tipo_venta):
            btn.setToolTip(
                f"Agregar 1 Kg de {producto.nombre_producto} al ticket. "
                "Ajusta el peso con los botones rapidos de la fila.",
            )
        else:
            btn.setToolTip(f"Agregar 1 {producto.nombre_producto} al ticket")
        btn.setProperty("rol", "agregar_catalogo")
        idproducto = int(str(producto.idproducto))
        btn.clicked.connect(
            lambda _=False, pid=idproducto: self._agregar_producto_venta(pid),
        )
        return btn

    # Boton rapido de peso, usado en la fila del ticket.
    @staticmethod
    def _crear_boton_peso_rapido(etiqueta: str, tooltip: str) -> QPushButton:
        """Boton rapido de peso, usado en la fila del ticket."""
        btn = QPushButton(etiqueta)
        btn.setFixedSize(ANCHO_BOTON_PESO_RAPIDO, ALTO_BOTON_PESO_RAPIDO)
        btn.setProperty("rol", "agregar_catalogo_peso")
        btn.setToolTip(tooltip)
        return btn

    # Carga una fila de la lista: Producto | USD | Bs | Stock | (+).
    def _rellenar_fila_catalogo(self, fila: int, producto: Producto) -> None:
        """Carga una fila de la lista: Producto | USD | Bs | Stock | (+)."""
        tabla = self.tabla_productos_catalogo

        item_nombre = QTableWidgetItem(producto.nombre_producto)
        item_nombre.setData(
            Qt.ItemDataRole.UserRole,
            int(str(producto.idproducto)),
        )
        detalle = []
        if producto.categoria is not None and producto.categoria.nombre:
            detalle.append(f"Categoria: {producto.categoria.nombre}")
        detalle.append(f"Stock: {formatear_stock(producto.stock_actual)}")
        item_nombre.setToolTip("\n".join(detalle))
        tabla.setItem(fila, 0, item_nombre)

        item_usd = QTableWidgetItem(f"{producto.precio_venta_usd:,.2f}")
        item_usd.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        item_usd.setToolTip(f"Precio en dolares: {formatear_usd(producto.precio_venta_usd)}")
        tabla.setItem(fila, 1, item_usd)

        item_bs = QTableWidgetItem(
            formatear_bs_sin_sufijo(self._precio_bs_efectivo(producto)),
        )
        item_bs.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        item_bs.setToolTip(
            f"Precio en bolivares: {formatear_bs(self._precio_bs_efectivo(producto))}",
        )
        tabla.setItem(fila, 2, item_bs)

        item_stock = QTableWidgetItem(formatear_stock(producto.stock_actual))
        item_stock.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        tabla.setItem(fila, 3, item_stock)

        tabla.setCellWidget(fila, 4, self._crear_boton_agregar(producto))

    # Doble clic en una fila del catalogo → agrega el producto.
    def _on_catalogo_doble_clic(self, item: QTableWidgetItem) -> None:
        """Doble clic en una fila del catalogo → agrega el producto."""
        self._agregar_fila_catalogo(item.row())

    # Enter sobre el catalogo → agrega el producto seleccionado.
    def _agregar_fila_activa(self) -> None:
        """Enter sobre el catalogo → agrega el producto seleccionado."""
        self._agregar_fila_catalogo(self.tabla_productos_catalogo.currentRow())

    # Agrega el producto de la fila indicada de la lista del catalogo.
    def _agregar_fila_catalogo(self, fila: int) -> None:
        """Agrega el producto de la fila indicada de la lista del catalogo."""
        item = self.tabla_productos_catalogo.item(fila, 0)
        if item is None:
            return
        valor = item.data(Qt.ItemDataRole.UserRole)
        if valor is not None:
            self._agregar_producto_venta(int(valor))

    # Crea un boton de filtro por categoria (marcable).
    def _crear_boton_categoria(self, nombre: str) -> QPushButton:
        btn = QPushButton(nombre)
        btn.setCheckable(True)
        btn.setProperty("rol", "categoria")
        if nombre == self._categoria_seleccionada:
            btn.setProperty("rol", "categoria_activa")
        btn.clicked.connect(lambda _=False, cat=nombre: self._seleccionar_categoria(cat))
        return btn

    # Reconstruye la fila de categorias: [Todos] + categorias de la BD.
    def _refrescar_botones_categorias(self) -> None:
        """Reconstruye la fila de categorias: [Todos] + categorias de la BD."""
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

    # Marca la categoria activa y re-aplica el filtro.
    def _seleccionar_categoria(self, nombre: str) -> None:
        """Marca la categoria activa y re-aplica el filtro."""
        self._categoria_seleccionada = nombre
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

    # Crea la tabla del ticket con sus columnas por tipo de venta.
    def _crear_panel_ticket(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        columnas: list[tuple[str, int]] = [
            ("Producto", 200),
            ("Kg", ANCHO_COLUMNA_KG),
            ("g", ANCHO_COLUMNA_GRAMOS),
            ("P.U.", ANCHO_COLUMNA_PRECIO),
            ("Importe", ANCHO_COLUMNA_IMPORTE),
            ("+ Peso", ANCHO_COLUMNA_PESO_RAPIDO),
            ("✕", ANCHO_COLUMNA_QUITAR),
        ]
        tooltips_columnas: list[str] = [
            "Producto del ticket",
            "Kilos enteros de la linea (0 a 999)",
            "Gramos de la linea (0 a 999)",
            "Precio unitario en bolivares",
            "Importe de la linea en bolivares",
            "Suma un peso rapido a ESTA linea",
            "Quita SOLO esta linea del ticket",
        ]
        self.tabla_productos_venta = QTableWidget()
        self.tabla_productos_venta.setColumnCount(len(columnas))
        self.tabla_productos_venta.setHorizontalHeaderLabels([c[0] for c in columnas])
        for i, (_, ancho) in enumerate(columnas):
            self.tabla_productos_venta.setColumnWidth(i, ancho)
        for i, texto_tooltip in enumerate(tooltips_columnas):
            header = self.tabla_productos_venta.horizontalHeader()
            modelo_header = header.model() if header is not None else None
            if modelo_header is not None:
                modelo_header.setHeaderData(
                    i,
                    Qt.Orientation.Horizontal,
                    texto_tooltip,
                    Qt.ItemDataRole.ToolTipRole,
                )
        self._aplicar_layout_ticket()
        self.tabla_productos_venta.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.tabla_productos_venta.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        vheader_ticket = self.tabla_productos_venta.verticalHeader()
        if vheader_ticket is not None:
            vheader_ticket.setVisible(False)
            vheader_ticket.setDefaultSectionSize(ALTO_FILA_TICKET)
        header_ticket = self.tabla_productos_venta.horizontalHeader()
        if header_ticket is not None:
            header_ticket.setStretchLastSection(False)
            header_ticket.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla_productos_venta.setShowGrid(False)
        self.tabla_productos_venta.setAlternatingRowColors(True)
        layout.addWidget(self.tabla_productos_venta, 1)

        self.lbl_total = QLabel(f"TOTAL: {formatear_bs(Decimal('0.00'))}")
        self.lbl_total.setProperty("rol", "total_gigante")
        self.lbl_total_usd = QLabel("≈ 0,00 USD")
        self.lbl_total_usd.setProperty("rol", "equivalente")
        layout.addWidget(self.lbl_total)
        layout.addWidget(self.lbl_total_usd)

        self._crear_seccion_pago(layout)

        self._crear_botones(layout)

        self._atajo_cobrar = QShortcut(QKeySequence(Qt.Key.Key_F12), self)
        self._atajo_cobrar.activated.connect(self._finalizar_venta)
        self._atajo_eliminar = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        self._atajo_eliminar.activated.connect(self._eliminar_fila_seleccionada)

        return panel

    # Crea el grupo de pago con metodos, desglose y resumen.
    def _crear_seccion_pago(self, layout: QVBoxLayout) -> None:
        layout.addSpacing(6)
        self.grupo_pago = QGroupBox("Pago")
        vbox_pago = QVBoxLayout(self.grupo_pago)
        vbox_pago.setSpacing(6)

        self._crear_botones_metodo(vbox_pago)
        self._crear_fila_recibido(vbox_pago)
        self._crear_panel_mixto(vbox_pago)
        self._crear_tabla_pagos(vbox_pago)
        self._crear_resumen_pagos(vbox_pago)
        self._crear_atajo_pago()

        self._actualizar_estado_cobrar()

        self.grupo_pago.setVisible(False)
        layout.addWidget(self.grupo_pago)

    # Crea los seis botones de metodo de pago en un grid.
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

        self.btn_pago_mixto = QPushButton("PAGO MIXTO")
        self.btn_pago_mixto.setCheckable(True)
        self.btn_pago_mixto.setMinimumHeight(32)
        self.btn_pago_mixto.setProperty("rol", "pago_mixto_boton")
        self.btn_pago_mixto.clicked.connect(self._alternar_panel_mixto)
        vbox_pago.addWidget(self.btn_pago_mixto)

    # Cobro rapido en efectivo: monto RECIBIDO editable.
    def _crear_fila_recibido(self, vbox_pago: QVBoxLayout) -> None:
        """Cobro rapido en efectivo: monto RECIBIDO editable."""
        self.fila_recibido = QFrame()
        self.fila_recibido.setProperty("rol", "fila_recibido")
        fila = QHBoxLayout(self.fila_recibido)
        fila.setContentsMargins(8, 6, 8, 6)
        fila.setSpacing(8)

        self.lbl_recibido = QLabel("Recibido Bs.:")
        fila.addWidget(self.lbl_recibido)

        self.spin_recibido = QDoubleSpinBox()
        self.spin_recibido.setMinimumHeight(32)
        self.spin_recibido.valueChanged.connect(self._actualizar_estado_recibido)
        fila.addWidget(self.spin_recibido, 1)

        self.lbl_estado_recibido = QLabel("")
        self.lbl_estado_recibido.setProperty("rol", "resumen_falta")
        fila.addWidget(self.lbl_estado_recibido, 1)

        self.btn_registrar_recibido = QPushButton("REGISTRAR")
        self.btn_registrar_recibido.setProperty("rol", "primario")
        self.btn_registrar_recibido.setMinimumHeight(32)
        self.btn_registrar_recibido.clicked.connect(self._registrar_efectivo)
        fila.addWidget(self.btn_registrar_recibido)

        self.fila_recibido.setVisible(False)
        vbox_pago.addWidget(self.fila_recibido)

    # Panel "Combinar metodos de pago": parciales con cualquier metodo.
    def _crear_panel_mixto(self, vbox_pago: QVBoxLayout) -> None:
        """Panel "Combinar metodos de pago": parciales con cualquier metodo."""
        self.panel_mixto = QFrame()
        self.panel_mixto.setProperty("rol", "panel_mixto")
        vbox = QVBoxLayout(self.panel_mixto)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(6)

        cabecera = QHBoxLayout()
        self.lbl_titulo_mixto = QLabel("Combinar metodos de pago")
        self.lbl_titulo_mixto.setProperty("rol", "titulo_tarjeta")
        cabecera.addWidget(self.lbl_titulo_mixto)
        cabecera.addStretch()
        btn_cerrar = QPushButton("✕")
        btn_cerrar.setProperty("rol", "quitar_pago")
        btn_cerrar.setFixedSize(26, 26)
        btn_cerrar.setToolTip("Cerrar (los pagos parciales se conservan)")
        btn_cerrar.clicked.connect(self._cerrar_panel_mixto)
        cabecera.addWidget(btn_cerrar)
        vbox.addLayout(cabecera)

        grid_mixto = QGridLayout()
        grid_mixto.setSpacing(6)
        self._crear_botones_mixto(grid_mixto)
        vbox.addLayout(grid_mixto)

        fila_monto = QHBoxLayout()
        fila_monto.setSpacing(8)
        self.lbl_monto_mixto = QLabel("Monto:")
        fila_monto.addWidget(self.lbl_monto_mixto)
        self.spin_monto_mixto = QDoubleSpinBox()
        self.spin_monto_mixto.setMinimumHeight(32)
        self.spin_monto_mixto.valueChanged.connect(self._actualizar_info_mixto)
        fila_monto.addWidget(self.spin_monto_mixto, 1)
        self.lbl_info_mixto = QLabel("")
        self.lbl_info_mixto.setProperty("rol", "titulo_tarjeta")
        fila_monto.addWidget(self.lbl_info_mixto, 1)
        vbox.addLayout(fila_monto)

        fila_ref = QHBoxLayout()
        fila_ref.setSpacing(8)
        fila_ref.addWidget(QLabel("Referencia:"))
        self.campo_ref_mixto = QLineEdit()
        self.campo_ref_mixto.setPlaceholderText("Nro. de operacion (opcional)")
        fila_ref.addWidget(self.campo_ref_mixto, 1)
        self.btn_agregar_mixto = QPushButton("+ AGREGAR")
        self.btn_agregar_mixto.setProperty("rol", "primario")
        self.btn_agregar_mixto.setMinimumHeight(32)
        self.btn_agregar_mixto.clicked.connect(self._agregar_pago_mixto)
        fila_ref.addWidget(self.btn_agregar_mixto)
        vbox.addLayout(fila_ref)

        self.panel_mixto.setVisible(False)
        vbox_pago.addWidget(self.panel_mixto)

    # Crea los 6 botones de metodo internos del panel mixto.
    def _crear_botones_mixto(self, grid_mixto: QGridLayout) -> None:
        """Crea los 6 botones de metodo internos del panel mixto."""
        for indice, metodo in enumerate(METODOS_PAGO):
            boton = QPushButton(ETIQUETAS_METODO[metodo])
            boton.setCheckable(True)
            boton.setMinimumHeight(30)
            boton.setProperty("rol", "metodo")
            boton.clicked.connect(lambda _=False, m=metodo: self._seleccionar_metodo_mixto(m))
            self._botones_mixto[metodo] = boton
            grid_mixto.addWidget(boton, indice // 3, indice % 3)

    # Crea la tabla del desglose de pagos (metodo, monto, vuelto).
    def _crear_tabla_pagos(self, vbox_pago: QVBoxLayout) -> None:
        self.tabla_pagos = QTableWidget()
        self.tabla_pagos.setColumnCount(5)
        self.tabla_pagos.setHorizontalHeaderLabels(
            ["Metodo", "Monto", "Aplicado Bs.", "Vuelto", ""]
        )
        self.tabla_pagos.setColumnWidth(1, 95)
        self.tabla_pagos.setColumnWidth(2, 105)
        self.tabla_pagos.setColumnWidth(3, 95)
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

    # Muestra hasta MAX_FILAS_VISIBLES_PAGOS filas; el resto con scrollbar.
    def _ajustar_alto_tabla_pagos(self) -> None:
        """Muestra hasta MAX_FILAS_VISIBLES_PAGOS filas; el resto con scrollbar."""
        filas = min(self.tabla_pagos.rowCount(), MAX_FILAS_VISIBLES_PAGOS)
        filas = max(filas, MIN_FILAS_VISIBLES_PAGOS)
        alto = (
            ALTO_ENCABEZADO_PAGOS
            + ALTO_RESERVA_SCROLL_PAGOS
            + filas * ALTO_FILA_PAGOS
            + 2
        )
        self.tabla_pagos.setFixedHeight(alto)

    # Crea el resumen de cobertura y el indicador PAGO MIXTO.
    def _crear_resumen_pagos(self, vbox_pago: QVBoxLayout) -> None:
        fila_resumen = QHBoxLayout()
        self.lbl_modo_pago = QLabel("PAGO MIXTO")
        self.lbl_modo_pago.setProperty("rol", "pago_mixto")
        self.lbl_modo_pago.setVisible(False)
        fila_resumen.addWidget(self.lbl_modo_pago)
        self.lbl_cubierto = QLabel(f"CUBIERTO: {formatear_bs(Decimal('0.00'))}")
        self.lbl_cubierto.setProperty("rol", "titulo_tarjeta")
        self.lbl_restante = QLabel("RESTANTE: 0,00 Bs.")
        self.lbl_restante.setProperty("rol", "resumen_falta")
        fila_resumen.addStretch()
        fila_resumen.addWidget(self.lbl_cubierto)
        fila_resumen.addStretch()
        fila_resumen.addWidget(self.lbl_restante)
        vbox_pago.addLayout(fila_resumen)

    # Conecta Enter para agregar pago dentro del grupo Pago.
    def _crear_atajo_pago(self) -> None:
        self._atajo_agregar_pago = QShortcut(QKeySequence(Qt.Key.Key_Return), self.grupo_pago)
        self._atajo_agregar_pago.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._atajo_agregar_pago.activated.connect(self._agregar_por_atajo)

    # Cobro rapido: digital cubre el total; efectivo pide el recibido.
    def _seleccionar_metodo(self, metodo: str) -> None:
        """Cobro rapido: digital cubre el total; efectivo pide el recibido."""
        self._cerrar_panel_mixto()

        if self.pagos and not self._confirmar_reemplazo("reemplazar los pagos ya registrados"):
            return

        self._metodo_actual = metodo
        for nombre, boton in self._botones_metodo.items():
            activo = nombre == metodo
            boton.setChecked(activo)
            self._set_rol(boton, "metodo_activo" if activo else "metodo")

        if metodo in METODOS_PAGO_DIGITALES:
            self._cobro_rapido_digital(metodo)
            return
        self._preparar_efectivo(metodo)

    # Registra el total con el metodo digital (monto = faltante).
    def _cobro_rapido_digital(self, metodo: str) -> None:
        """Registra el total con el metodo digital (monto = faltante)."""
        faltante = self._monto_restante_bs()
        if faltante <= TOLERANCIA_REDONDEO:
            return
        self._agregar_pago_metodo(metodo, self._centimos(faltante))
        self._metodo_actual = None
        for boton in self._botones_metodo.values():
            boton.setChecked(False)
            self._set_rol(boton, "metodo")

    # Muestra la fila de recibido con el faltante pre-llenado editable.
    def _preparar_efectivo(self, metodo: str) -> None:
        """Muestra la fila de recibido con el faltante pre-llenado editable."""
        es_usd = metodo == METODO_PAGO_EFECTIVO_USD
        sin_tasa = es_usd and not self._tasa_valida()

        if es_usd:
            configurar_spinbox_usd(self.spin_recibido)
        else:
            configurar_spinbox_bs(self.spin_recibido)
        self.lbl_recibido.setText("Recibido USD:" if es_usd else "Recibido Bs.:")
        self.spin_recibido.setEnabled(not sin_tasa)

        if sin_tasa:
            self.spin_recibido.setValue(0.0)
            self.btn_registrar_recibido.setEnabled(False)
            self.lbl_estado_recibido.setText(
                "Sin tasa BCV activa: no se puede cobrar en USD",
            )
            self._set_rol(self.lbl_estado_recibido, "resumen_falta")
            self.fila_recibido.setVisible(True)
            return

        faltante = self._monto_restante_bs()
        if faltante <= TOLERANCIA_REDONDEO:
            self.spin_recibido.setValue(0.0)
            self.btn_registrar_recibido.setEnabled(False)
            self.lbl_estado_recibido.setText("Pago COMPLETO: el ticket esta cubierto")
            self._set_rol(self.lbl_estado_recibido, "resumen_ok")
        else:
            self.btn_registrar_recibido.setEnabled(True)
            self.spin_recibido.setValue(float(self._en_moneda(faltante, es_usd)))
            self._actualizar_estado_recibido()
        self.fila_recibido.setVisible(True)
        self.spin_recibido.setFocus()
        self.spin_recibido.selectAll()

    # Informa en vivo: VUELTO / FALTA / Pago exacto del cobro rapido.
    def _actualizar_estado_recibido(self) -> None:
        """Informa en vivo: VUELTO / FALTA / Pago exacto del cobro rapido."""
        if self._metodo_actual not in (METODO_PAGO_EFECTIVO_BS, METODO_PAGO_EFECTIVO_USD):
            return
        if not self._tasa_valida():
            return

        monto = self._centimos(Decimal(str(self.spin_recibido.value())))
        es_usd = self._metodo_actual == METODO_PAGO_EFECTIVO_USD
        aplicado_bs = self._monto_aplicado_bs(monto, es_usd)
        faltante = self._monto_restante_bs()

        if faltante <= TOLERANCIA_REDONDEO:
            self.lbl_estado_recibido.setText("Pago COMPLETO: el ticket esta cubierto")
            self._set_rol(self.lbl_estado_recibido, "resumen_ok")
            self.btn_registrar_recibido.setEnabled(False)
        elif aplicado_bs > faltante + TOLERANCIA_REDONDEO:
            vuelto = self._centimos(aplicado_bs - faltante)
            self.lbl_estado_recibido.setText(f"VUELTO: {formatear_bs(vuelto)}")
            self._set_rol(self.lbl_estado_recibido, "resumen_ok")
            self.btn_registrar_recibido.setEnabled(True)
        elif aplicado_bs >= faltante - TOLERANCIA_REDONDEO:
            self.lbl_estado_recibido.setText("Pago exacto: el ticket queda cubierto")
            self._set_rol(self.lbl_estado_recibido, "resumen_ok")
            self.btn_registrar_recibido.setEnabled(True)
        else:
            self.lbl_estado_recibido.setText(
                f"Falta: {formatear_bs(faltante - aplicado_bs)}",
            )
            self._set_rol(self.lbl_estado_recibido, "resumen_falta")
            self.btn_registrar_recibido.setEnabled(True)

    # Registra el cobro rapido en efectivo (recibido >= total).
    def _registrar_efectivo(self) -> None:
        """Registra el cobro rapido en efectivo (recibido >= total)."""
        metodo = self._metodo_actual
        if metodo not in (METODO_PAGO_EFECTIVO_BS, METODO_PAGO_EFECTIVO_USD):
            return

        es_usd = metodo == METODO_PAGO_EFECTIVO_USD
        if es_usd and not self._tasa_valida():
            QMessageBox.warning(self, "Pago", "No hay una tasa BCV activa para cobrar en USD.")
            return

        monto = self._centimos(Decimal(str(self.spin_recibido.value())))
        if monto <= 0:
            QMessageBox.warning(self, "Pago", "Ingresa el monto recibido.")
            return

        faltante = self._monto_restante_bs()
        if faltante <= TOLERANCIA_REDONDEO:
            QMessageBox.information(self, "Pago", "La venta ya esta cubierta.")
            return

        aplicado_bs = self._monto_aplicado_bs(monto, es_usd)
        if aplicado_bs < faltante - TOLERANCIA_REDONDEO:
            QMessageBox.warning(
                self,
                "Pago incompleto",
                f"El efectivo recibido ({formatear_bs(aplicado_bs)}) no cubre "
                f"el total ({formatear_bs(faltante)}).\n\n"
                "Pulsa PAGO MIXTO para dividir el pago entre varios metodos.",
            )
            return

        if self._agregar_pago_metodo(metodo, monto):
            self._repintar_recibido()

    # Reprepara la fila de recibido con el nuevo faltante (o la oculta).
    def _repintar_recibido(self) -> None:
        """Reprepara la fila de recibido con el nuevo faltante (o la oculta)."""
        if self._metodo_actual not in (METODO_PAGO_EFECTIVO_BS, METODO_PAGO_EFECTIVO_USD):
            return
        faltante = self._monto_restante_bs()
        if faltante <= TOLERANCIA_REDONDEO:
            self._metodo_actual = None
            for boton in self._botones_metodo.values():
                boton.setChecked(False)
                self._set_rol(boton, "metodo")
            self.fila_recibido.setVisible(False)
            return
        es_usd = self._metodo_actual == METODO_PAGO_EFECTIVO_USD
        self.spin_recibido.setValue(float(self._en_moneda(faltante, es_usd)))
        self._actualizar_estado_recibido()
        self.spin_recibido.setFocus()
        self.spin_recibido.selectAll()

    # Agrega un pago al desglose (efectivo rapido o mixto).
    def _agregar_pago_metodo(self, metodo: str, monto: Decimal, referencia: str = "") -> bool:
        """Agrega un pago al desglose (efectivo rapido o mixto)."""
        if metodo not in METODOS_PAGO:
            return False
        monto = self._centimos(monto)
        if monto <= 0:
            return False

        faltante = self._monto_restante_bs()
        if faltante <= TOLERANCIA_REDONDEO:
            return False

        es_usd = metodo == METODO_PAGO_EFECTIVO_USD
        if es_usd and not self._tasa_valida():
            QMessageBox.warning(self, "Pago", "No hay una tasa BCV activa para cobrar en USD.")
            return False

        aplicado_bs = self._monto_aplicado_bs(monto, es_usd)
        vuelto_bs = Decimal("0.00")
        if aplicado_bs > faltante + TOLERANCIA_REDONDEO:
            vuelto_bs = self._centimos(aplicado_bs - faltante)
            aplicado_bs = self._centimos(faltante)

        self.pagos.append(
            {
                "metodo": metodo,
                "moneda": MONEDA_USD if es_usd else MONEDA_BS,
                "monto": monto,
                "monto_bs": aplicado_bs,
                "vuelto_bs": vuelto_bs,
                "tasa_venta": self._tasa.tasa_venta if (es_usd and self._tasa) else None,
                "referencia": referencia,
            }
        )
        self._refrescar_tabla_pagos()
        self._actualizar_resumen_pagos()
        return True

    # Abre/cierra el panel docked para dividir el pago en parciales.
    def _alternar_panel_mixto(self) -> None:
        """Abre/cierra el panel docked para dividir el pago en parciales."""
        if not self.panel_mixto.isHidden():
            self._cerrar_panel_mixto()
            return
        if self.pagos and not self._confirmar_reemplazo("reemplazar los pagos ya registrados"):
            self.btn_pago_mixto.setChecked(False)
            return
        self._limpiar_modo_rapido()
        self.panel_mixto.setVisible(True)
        self._seleccionar_metodo_mixto(METODO_PAGO_EFECTIVO_BS)
        self.spin_monto_mixto.setFocus()
        self.spin_monto_mixto.selectAll()

    # Cierra el panel (los pagos parciales agregados se conservan).
    def _cerrar_panel_mixto(self) -> None:
        """Cierra el panel (los pagos parciales agregados se conservan)."""
        self.panel_mixto.setVisible(False)
        self.btn_pago_mixto.setChecked(False)
        self._metodo_mixto = None
        for boton in self._botones_mixto.values():
            boton.setChecked(False)
            self._set_rol(boton, "metodo")

    # Resetea el modo rapido: metodo activo y fila de recibido.
    def _limpiar_modo_rapido(self) -> None:
        """Resetea el modo rapido: metodo activo y fila de recibido."""
        self._metodo_actual = None
        for boton in self._botones_metodo.values():
            boton.setChecked(False)
            self._set_rol(boton, "metodo")
        self.fila_recibido.setVisible(False)

    # Marca el metodo del panel mixto y pre-llena su monto.
    def _seleccionar_metodo_mixto(self, metodo: str) -> None:
        """Marca el metodo del panel mixto y pre-llena su monto."""
        self._metodo_mixto = metodo
        for nombre, boton in self._botones_mixto.items():
            activo = nombre == metodo
            boton.setChecked(activo)
            self._set_rol(boton, "metodo_activo" if activo else "metodo")
        self._pre_llenar_monto_mixto()

    # Pre-llena el monto mixto con el faltante en la moneda del metodo.
    def _pre_llenar_monto_mixto(self) -> None:
        """Pre-llena el monto mixto con el faltante en la moneda del metodo."""
        metodo = self._metodo_mixto
        if metodo is None:
            return
        es_usd = metodo == METODO_PAGO_EFECTIVO_USD
        sin_tasa = es_usd and not self._tasa_valida()

        if es_usd:
            configurar_spinbox_usd(self.spin_monto_mixto)
        else:
            configurar_spinbox_bs(self.spin_monto_mixto)
        self.spin_monto_mixto.setEnabled(not sin_tasa)
        self.btn_agregar_mixto.setEnabled(not sin_tasa)

        if sin_tasa:
            self.spin_monto_mixto.setValue(0.0)
            self.lbl_info_mixto.setText("Sin tasa BCV activa: no se puede cobrar en USD")
            return

        faltante = self._monto_restante_bs()
        if faltante <= TOLERANCIA_REDONDEO:
            self.spin_monto_mixto.setValue(0.0)
            self.lbl_info_mixto.setText("Pago COMPLETO: cierra el panel y pulsa COBRAR")
            self.btn_agregar_mixto.setEnabled(False)
            return
        self.spin_monto_mixto.setValue(float(self._en_moneda(faltante, es_usd)))
        self._actualizar_info_mixto()

    # Muestra el equivalente del monto mixto (y el cambio si sobra).
    def _actualizar_info_mixto(self) -> None:
        """Muestra el equivalente del monto mixto (y el cambio si sobra)."""
        if self._metodo_mixto is None:
            return

        monto = self._centimos(Decimal(str(self.spin_monto_mixto.value())))
        es_usd = self._metodo_mixto == METODO_PAGO_EFECTIVO_USD
        if es_usd and not self._tasa_valida():
            self.lbl_info_mixto.setText("Sin tasa BCV activa")
            return

        aplicado_bs = self._monto_aplicado_bs(monto, es_usd)
        if es_usd:
            texto = f"= {formatear_bs(aplicado_bs)}"
        elif self._tasa is not None and self._tasa.tasa_venta > 0:
            texto = f"≈ {formatear_usd(self._centimos(monto / self._tasa.tasa_venta))}"
        else:
            texto = f"= {formatear_bs(monto)}  (sin tasa para USD)"

        faltante = self._monto_restante_bs()
        if faltante > TOLERANCIA_REDONDEO and aplicado_bs > faltante + TOLERANCIA_REDONDEO:
            texto += f"  ·  CAMBIO: {formatear_bs(aplicado_bs - faltante)}"
        self.lbl_info_mixto.setText(texto)

    # Agrega al desglose el pago parcial tecleado en el panel mixto.
    def _agregar_pago_mixto(self) -> None:
        """Agrega al desglose el pago parcial tecleado en el panel mixto."""
        metodo = self._metodo_mixto
        if metodo is None:
            QMessageBox.warning(self, "Pago", "Selecciona un metodo del panel de pago mixto.")
            return

        monto = self._centimos(Decimal(str(self.spin_monto_mixto.value())))
        if monto <= 0:
            QMessageBox.warning(self, "Pago", "Ingresa un monto mayor a cero.")
            return

        if self._agregar_pago_metodo(
            metodo,
            monto,
            referencia=self.campo_ref_mixto.text().strip(),
        ):
            self.campo_ref_mixto.clear()
            self._pre_llenar_monto_mixto()
            self.spin_monto_mixto.setFocus()
            self.spin_monto_mixto.selectAll()
        elif self._monto_restante_bs() <= TOLERANCIA_REDONDEO:
            QMessageBox.information(
                self,
                "Pago",
                "La venta ya esta cubierta.\nCierra el panel y pulsa COBRAR (F12).",
            )

    # Pregunta si se pueden descartar los pagos parciales registrados.
    def _confirmar_reemplazo(self, accion: str) -> bool:
        """Pregunta si se pueden descartar los pagos parciales registrados."""
        respuesta = QMessageBox.question(
            self,
            "Reemplazar pagos",
            f"Ya hay pagos registrados en esta venta. {accion.capitalize()}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return False
        self.pagos = []
        self._refrescar_tabla_pagos()
        self._actualizar_resumen_pagos()
        return True

    # Enter: registra el efectivo rapido o agrega un pago mixto.
    def _agregar_por_atajo(self) -> None:
        """Enter: registra el efectivo rapido o agrega un pago mixto."""
        if not self.panel_mixto.isHidden():
            self._agregar_pago_mixto()
        elif not self.fila_recibido.isHidden():
            self._registrar_efectivo()

    # Quita de la lista el pago de la fila indicada.
    def _eliminar_pago(self, fila: int) -> None:
        """Quita de la lista el pago de la fila indicada."""
        if not 0 <= fila < len(self.pagos):
            return
        self.pagos.pop(fila)
        self._refrescar_tabla_pagos()
        self._actualizar_resumen_pagos()
        if not self.panel_mixto.isHidden():
            self._pre_llenar_monto_mixto()
        elif not self.fila_recibido.isHidden():
            self._repintar_recibido()

    # Reconstruye la tabla de pagos a partir de self.
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
            btn_quitar.setFixedSize(ANCHO_COLUMNA_BORRAR_PAGOS - 12, ALTO_FILA_PAGOS - 8)
            btn_quitar.clicked.connect(lambda _=False, f=fila: self._eliminar_pago(f))
            self.tabla_pagos.setCellWidget(fila, 4, btn_quitar)

        self._ajustar_alto_tabla_pagos()

    # Muestra CUBIERTO y RESTANTE (o CAMBIO / PAGO COMPLETO).
    def _actualizar_resumen_pagos(self) -> None:
        """Muestra CUBIERTO y RESTANTE (o CAMBIO / PAGO COMPLETO)."""
        cubierto = self._monto_cubierto_bs()
        restante = self._monto_restante_bs()
        self.lbl_cubierto.setText(f"CUBIERTO: {formatear_bs(cubierto)}")
        self._set_rol(self.lbl_cubierto, "resumen_ok" if cubierto > 0 else "titulo_tarjeta")

        metodos_distintos = {pago["metodo"] for pago in self.pagos}
        self.lbl_modo_pago.setVisible(len(metodos_distintos) > 1)

        if restante > TOLERANCIA_REDONDEO:
            self.lbl_restante.setText(f"RESTANTE: {formatear_bs(restante)}")
            self._set_rol(self.lbl_restante, "resumen_falta")
        elif restante < -TOLERANCIA_REDONDEO:
            self.lbl_restante.setText(f"CAMBIO: {formatear_bs(-restante)}")
            self._set_rol(self.lbl_restante, "resumen_ok")
        else:
            self.lbl_restante.setText("PAGO COMPLETO")
            self._set_rol(self.lbl_restante, "resumen_ok")
        self._actualizar_estado_cobrar()

    # Habilita COBRAR solo si el ticket esta cubierto (PAGO COMPLETO).
    def _actualizar_estado_cobrar(self) -> None:
        """Habilita COBRAR solo si el ticket esta cubierto (PAGO COMPLETO)."""
        if not hasattr(self, "btn_cobrar"):
            return
        restante = self._monto_restante_bs()
        completo = (
            bool(self.productos_venta) and bool(self.pagos) and abs(restante) <= TOLERANCIA_REDONDEO
        )
        self.btn_cobrar.setEnabled(completo)

    # Total ya cubierto por los pagos agregados (en Bs.
    def _monto_cubierto_bs(self) -> Decimal:
        """Total ya cubierto por los pagos agregados (en Bs.)."""
        return sum((pago["monto_bs"] for pago in self.pagos), Decimal("0.00"))

    # Lo que falta por cubrir (negativo = cambio a devolver).
    def _monto_restante_bs(self) -> Decimal:
        """Lo que falta por cubrir (negativo = cambio a devolver)."""
        return self.total_bs - self._monto_cubierto_bs()

    # Indica si hay una tasa activa usable para convertir montos.
    def _tasa_valida(self) -> bool:
        """Indica si hay una tasa activa usable para convertir montos."""
        return self._tasa is not None and self._tasa.tasa_venta > 0

    # Cuantiza un monto a centimos (redondeo comercial).
    @staticmethod
    def _centimos(valor: Decimal) -> Decimal:
        """Cuantiza un monto a centimos (redondeo comercial)."""
        return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Convierte un monto en Bs.
    def _en_moneda(self, monto_bs: Decimal, es_usd: bool) -> Decimal:
        """Convierte un monto en Bs. a la moneda del metodo activo."""
        if not es_usd:
            return self._centimos(monto_bs)
        if not self._tasa_valida():
            return Decimal("0.00")
        assert self._tasa is not None
        return (monto_bs / self._tasa.tasa_venta).quantize(Decimal("0.01"), rounding=ROUND_CEILING)

    # Equivalente en Bs.
    def _monto_aplicado_bs(self, monto: Decimal, es_usd: bool) -> Decimal:
        """Equivalente en Bs. del monto tecleado (sin recortar)."""
        if not es_usd:
            return monto
        if not self._tasa_valida():
            return Decimal("0.00")
        assert self._tasa is not None
        return self._centimos(monto * self._tasa.tasa_venta)

    # Recalcula el equivalente en Bs.
    def _recalcular_equivalencias(self) -> None:
        """Recalcula el equivalente en Bs. de los pagos en USD (tasa nueva)."""
        if not self._tasa_valida():
            return
        assert self._tasa is not None
        tasa_actual = self._tasa.tasa_venta
        for pago in self.pagos:
            if pago["moneda"] != MONEDA_USD or pago["tasa_venta"] == tasa_actual:
                continue
            pago["tasa_venta"] = tasa_actual
            pago["monto_bs"] = self._monto_aplicado_bs(pago["monto"], True)
            pago["vuelto_bs"] = Decimal("0.00")

    # Resume los pagos por metodo (mismo criterio que el controlador).
    def _pagos_a_metodo_pago(self) -> dict[str, object]:
        """Resume los pagos por metodo (mismo criterio que el controlador)."""
        acumulado: dict[str, Decimal] = dict.fromkeys(METODOS_PAGO, Decimal("0.00"))
        for pago in self.pagos:
            metodo = pago["metodo"]
            valor = (
                pago["monto"]
                if metodo in (METODO_PAGO_EFECTIVO_BS, METODO_PAGO_EFECTIVO_USD)
                else pago["monto_bs"]
            )
            acumulado[metodo] += valor

        resumen: dict[str, object] = {}
        for nombre, monto in acumulado.items():
            resumen[nombre] = monto
        return resumen

    # Cambia el rol QSS de un widget y lo repinta.
    @staticmethod
    def _set_rol(widget: QWidget, rol: str) -> None:
        """Cambia el rol QSS de un widget y lo repinta."""
        widget.setProperty("rol", rol)
        estilo = widget.style()
        if estilo is not None:
            estilo.unpolish(widget)
            estilo.polish(widget)

    # Crea LIMPIAR TICKET, tasa manual, COBRAR y ANULAR.
    def _crear_botones(self, layout: QVBoxLayout) -> None:
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_limpiar_ticket = QPushButton("LIMPIAR TICKET")
        self.btn_limpiar_ticket.setProperty("rol", "anular")
        self.btn_limpiar_ticket.setMinimumHeight(48)
        self.btn_limpiar_ticket.clicked.connect(self._confirmar_limpiar_ticket)
        btn_layout.addWidget(self.btn_limpiar_ticket)

        self.btn_cobrar = QPushButton("COBRAR (F12)")
        self.btn_cobrar.setProperty("rol", "cobrar")
        self.btn_cobrar.setMinimumHeight(48)
        self.btn_cobrar.clicked.connect(self._finalizar_venta)
        self.btn_cobrar.setEnabled(False)
        btn_layout.addWidget(self.btn_cobrar)

        layout.addLayout(btn_layout)

    # Carga todos los productos y sus categorias en el catalogo.
    def _cargar_catalogo(self) -> None:
        if not self.controlador_productos:
            return

        self._productos_catalogo = self.controlador_productos.listar_todos()
        self._categorias = self.controlador_productos.obtener_categorias()
        self._refrescar_botones_categorias()
        self._aplicar_filtro()

    # Reconstruye la lista del catalogo segun el texto y la categoria.
    def _aplicar_filtro(self) -> None:
        """Reconstruye la lista del catalogo segun el texto y la categoria."""
        termino = self.campo_busqueda.text().strip().lower()

        productos_filtrados: list[Producto] = []
        for producto in self._productos_catalogo:
            categoria = producto.categoria.nombre if producto.categoria else ""
            nombre = producto.nombre_producto.lower()
            coincide_categoria = self._categoria_seleccionada in {"Todos", categoria}
            if not coincide_categoria:
                continue
            if termino and termino not in nombre and termino not in categoria.lower():
                continue
            productos_filtrados.append(producto)

        tabla = self.tabla_productos_catalogo
        tabla.setRowCount(len(productos_filtrados))
        tabla.setUpdatesEnabled(False)
        try:
            for fila, producto in enumerate(productos_filtrados):
                self._rellenar_fila_catalogo(fila, producto)
        finally:
            tabla.setUpdatesEnabled(True)

    # Actualiza el label de la tasa y guarda la tasa activa.
    def _actualizar_tasa(self) -> None:
        """Actualiza el label de la tasa y guarda la tasa activa."""
        if not self.controlador_tasas:
            return
        if not self._tasa_manual_activa:
            self._tasa = self.controlador_tasas.tasa_activa()
        self._pintar_tasa_label()
        self._aplicar_filtro()

    # Pinta el label de la tasa segun el estado (BCV automatica/manual).
    def _pintar_tasa_label(self) -> None:
        """Pinta el label de la tasa segun el estado (BCV automatica/manual)."""
        if self._tasa_manual_activa and self._tasa is not None:
            self.lbl_tasa.setText(
                f"Tasa MANUAL: {formatear_bs(self._tasa.tasa_venta)} / USD  (fijada hoy)"
            )
            self._set_rol(self.lbl_tasa, "tasa_bcv_manual")
            return
        if self._tasa is not None:
            self.lbl_tasa.setText(
                f"Tasa BCV: {formatear_bs(self._tasa.tasa_venta)} / USD  "
                f"(activa: {self._tasa.fecha})"
            )
        else:
            self.lbl_tasa.setText("Tasa BCV: No hay tasa activa registrada.")
        self._set_rol(self.lbl_tasa, "tasa_bcv_auto")

    # Pide al cajero la tasa manual y la fija para la venta en curso.
    def _pedir_tasa_manual(self) -> None:
        """Pide al cajero la tasa manual y la fija para la venta en curso."""
        if self._tasa_manual_activa:
            respuesta = QMessageBox.question(
                self,
                "Tasa manual activa",
                "Ya hay una tasa manual activa para esta venta.\n¿Reemplazarla por una nueva?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if respuesta != QMessageBox.StandardButton.Yes:
                return

        dialogo = DialogoTasaManual(self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        valor = dialogo.tasa()
        if valor <= 0:
            QMessageBox.warning(self, "Tasa manual", "La tasa debe ser mayor a cero.")
            return
        self._establecer_tasa_manual(valor)
        self._pintar_tasa_label()
        self._aplicar_filtro()

    # Fija la tasa manual para la venta en curso y la persiste.
    def _establecer_tasa_manual(self, tasa_venta: Decimal) -> None:
        """Fija la tasa manual para la venta en curso y la persiste."""
        if not self.controlador_tasas:
            return
        try:
            self.controlador_tasas.registrar_tasa_manual(
                tasa_venta,
                registrado_por=self.nombre_cajero,
            )
        except Exception as e:
            registrar_excepcion(e, "FormularioVenta._establecer_tasa_manual")
            QMessageBox.warning(
                self,
                "Tasa manual",
                "No se pudo registrar la tasa manual en la BD.\nLa venta seguira con la tasa BCV.",
            )
            return

        if not self._tasa_manual_activa:
            self._tasa_base_bcv = self._tasa.tasa_venta if self._tasa else None

        if self._tasa is None:
            self._tasa = TasaCambio(
                fecha=hoy(),
                tasa_venta=tasa_venta,
                tasa_compra=tasa_venta,
                activa=True,
                origen=ORIGEN_TASA_MANUAL,
            )
        else:
            self._tasa.tasa_venta = tasa_venta
            self._tasa.tasa_compra = tasa_venta
        self._tasa_manual_activa = True
        self._reversion_pendiente = False
        self._reversion_avisada_por = None
        self._pintar_tasa_label()
        self._aplicar_filtro()
        registrar_evento(
            logging.INFO,
            f"POS: tasa manual {tasa_venta} Bs/USD fijada por {self.nombre_cajero or 'cajero'}.",
        )

    # Vuelve a la tasa BCV capturada y desactiva la manual en la BD.
    def _revertir_tasa_manual(self) -> None:
        """Vuelve a la tasa BCV capturada y desactiva la manual en la BD."""
        if not self._tasa_manual_activa:
            return
        if self._tasa_base_bcv is None:
            self._tasa = None
        elif self._tasa is not None:
            self._tasa.tasa_venta = self._tasa_base_bcv
            self._tasa.tasa_compra = self._tasa_base_bcv
        self._tasa_manual_activa = False
        self._reversion_pendiente = False
        self._reversion_avisada_por = None
        try:
            if self.controlador_tasas is not None:
                self.controlador_tasas.desactivar_tasa_manual()
        except Exception as e:
            registrar_excepcion(e, "FormularioVenta._revertir_tasa_manual")
        self._pintar_tasa_label()
        self._aplicar_filtro()
        self._recalcular_equivalencias()
        self._refrescar_tabla_pagos()
        self._actualizar_resumen_pagos()
        registrar_evento(
            logging.INFO,
            f"POS: tasa manual revertida a la BCV por {self.nombre_cajero or 'cajero'}.",
        )

    # Pregunta si revertir la manual a la BCV nueva (sin ticket).
    def _ofrecer_reversion(self, tasa_bcv_actual: Decimal) -> None:
        """Pregunta si revertir la manual a la BCV nueva (sin ticket)."""
        respuesta = QMessageBox.question(
            self,
            "Tasa BCV actualizada",
            "La tasa BCV cambio mientras habia una tasa manual activa.\n"
            f"Nueva tasa BCV: {formatear_bs(tasa_bcv_actual)} / USD\n\n"
            "¿Volver a la tasa BCV actual?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            self._revertir_tasa_manual()
        else:
            self._reversion_avisada_por = tasa_bcv_actual

    # Ofrece la reversion pendiente cuando ya no hay ticket en curso.
    def _comprobar_reversion_pendiente(self) -> None:
        """Ofrece la reversion pendiente cuando ya no hay ticket en curso."""
        if not self._reversion_pendiente or not self._tasa_manual_activa:
            return
        if not self.controlador_tasas:
            return
        try:
            tasa_bcv = self.controlador_tasas.tasa_activa()
        except Exception as e:
            registrar_excepcion(e, "FormularioVenta._comprobar_reversion_pendiente")
            return
        if tasa_bcv is None:
            return
        self._reversion_pendiente = False
        self._ofrecer_reversion(tasa_bcv.tasa_venta)

    # Tick del timer: detecta si la BCV cambio mientras hay manual.
    def _comprobar_tasa_bcv(self) -> None:
        """Tick del timer: detecta si la BCV cambio mientras hay manual."""
        if not self.controlador_tasas:
            return
        try:
            tasa_bcv = self.controlador_tasas.tasa_activa()
        except Exception as e:
            registrar_excepcion(e, "FormularioVenta._comprobar_tasa_bcv")
            return

        if self._tasa_manual_activa:
            if tasa_bcv is None:
                return
            cambio = tasa_bcv.tasa_venta != self._reversion_avisada_por
            if self._tasa_base_bcv is not None:
                cambio = cambio and tasa_bcv.tasa_venta != self._tasa_base_bcv
            if not cambio:
                return
            if self.productos_venta:
                self._reversion_pendiente = True
            else:
                self._ofrecer_reversion(tasa_bcv.tasa_venta)
            return

        if self.productos_venta:
            return
        if self._tasa is None or tasa_bcv is None or tasa_bcv.tasa_venta != self._tasa.tasa_venta:
            self._actualizar_tasa()

    # Muestra el estado de la caja (ABIERTA/CERRADA) si hay controlador.
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

    # Atajo F1: pone el foco en el campo de busqueda.
    def _enfocar_busqueda(self) -> None:
        """Atajo F1: pone el foco en el campo de busqueda."""
        self.campo_busqueda.setFocus()
        self.campo_busqueda.selectAll()

    # Agrega el producto indicado (boton del catalogo o doble clic).
    def _agregar_producto_venta(self, idproducto: int, peso: Decimal | None = None) -> None:
        """Agrega el producto indicado (boton del catalogo o doble clic)."""
        if self.controlador_productos is None or self.controlador_ventas is None:
            msg = "Controladores no inicializados"
            raise RuntimeError(msg)

        producto = self.controlador_productos.obtener_por_id(int(idproducto))
        if not producto:
            QMessageBox.warning(self, "Error", "El producto no existe.")
            return

        if es_medida(producto.tipo_venta):
            cantidad = a_kg(peso if peso is not None else PESO_POR_DEFECTO_KG, 0)
        else:
            cantidad = Decimal("1.00")

        if producto.stock_actual < cantidad:
            self._avisar_stock_insuficiente(producto, cantidad)
            return

        precio_bs = self._precio_bs_efectivo(producto)

        subtotal = precio_bs * Decimal(str(cantidad))

        self.productos_venta.append(
            {
                "idproducto": producto.idproducto,
                "nombre": producto.nombre_producto,
                "cantidad": cantidad,
                "precio": precio_bs,
                "subtotal": subtotal,
                "tipo_venta": producto.tipo_venta,
            },
        )

        self.total_bs += subtotal
        self._refrescar_tabla_productos()
        self._actualizar_total()
        self._actualizar_visibilidad_pago()

    # "peso" si alguna linea se vende por peso; "unidad" si no.
    def _layout_ticket_actual(self) -> str:
        """ "peso" si alguna linea se vende por peso; "unidad" si no."""
        for item in self.productos_venta:
            if es_medida(item["tipo_venta"]):
                return "peso"
        return "unidad"

    # Oculta/muestra Kg+g segun el ticket y renombra la columna 1.
    def _aplicar_layout_ticket(self) -> None:
        """Oculta/muestra Kg+g segun el ticket y renombra la columna 1."""
        layout = self._layout_ticket_actual()
        if layout == self._layout_ticket:
            return
        self._layout_ticket = layout
        es_peso = layout == "peso"
        tabla = self.tabla_productos_venta
        tabla.setColumnHidden(2, not es_peso)
        tabla.setColumnHidden(5, not es_peso)
        etiqueta, tooltip = (
            ("Kg", "Kilos de la linea (acepta decimales: 0.5 = 500 g)")
            if es_peso
            else ("Cant.", "Cantidad de piezas (entera)")
        )
        header = tabla.horizontalHeader()
        modelo = header.model() if header is not None else None
        if modelo is not None:
            modelo.setHeaderData(
                1,
                Qt.Orientation.Horizontal,
                etiqueta,
                Qt.ItemDataRole.DisplayRole,
            )
            modelo.setHeaderData(
                1,
                Qt.Orientation.Horizontal,
                tooltip,
                Qt.ItemDataRole.ToolTipRole,
            )

    # Refresca la tabla de productos de la venta.
    def _refrescar_tabla_productos(self) -> None:
        """Refresca la tabla de productos de la venta."""
        self._refrescando = True
        try:
            tabla = self.tabla_productos_venta
            tabla.setRowCount(len(self.productos_venta))
            self._aplicar_layout_ticket()

            for fila, item in enumerate(self.productos_venta):
                celda_nombre = QTableWidgetItem(item["nombre"])
                celda_nombre.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable,
                )
                celda_nombre.setToolTip(item["nombre"])
                tabla.setItem(fila, 0, celda_nombre)

                if es_medida(item["tipo_venta"]):
                    kilos, gramos = descomponer_kg(item["cantidad"])
                    tabla.setCellWidget(
                        fila,
                        1,
                        self._crear_casilla_peso(fila, "kg", kilos),
                    )
                    tabla.setCellWidget(
                        fila,
                        2,
                        self._crear_casilla_peso(fila, "g", gramos),
                    )
                    tabla.setCellWidget(
                        fila,
                        5,
                        self._crear_botones_peso_rapido_fila(item["nombre"], fila),
                    )
                else:
                    tabla.setCellWidget(
                        fila,
                        1,
                        self._crear_casilla_unidad(fila, int(item["cantidad"])),
                    )
                    tabla.setCellWidget(fila, 2, None)
                    tabla.setCellWidget(fila, 5, None)

                precio = QTableWidgetItem(formatear_bs_sin_sufijo(item["precio"]))
                precio.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable,
                )
                precio.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                )
                precio.setToolTip(f"Precio unitario: {formatear_bs(item['precio'])}")
                tabla.setItem(fila, 3, precio)

                subtotal = QTableWidgetItem(formatear_bs_sin_sufijo(item["subtotal"]))
                subtotal.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable,
                )
                subtotal.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                )
                subtotal.setToolTip(f"Importe de la linea: {formatear_bs(item['subtotal'])}")
                tabla.setItem(fila, 4, subtotal)


                btn_quitar = QPushButton("✕")
                btn_quitar.setProperty("rol", "quitar_pago")
                btn_quitar.setFixedSize(40, 26)
                btn_quitar.setToolTip("Quitar esta linea del ticket")
                btn_quitar.clicked.connect(
                    lambda _=False, f=fila: self._eliminar_producto_venta(f),
                )
                tabla.setCellWidget(fila, 6, btn_quitar)
        finally:
            self._refrescando = False

    # SpinBoxStock de Kg (modo kg, decimal) o de gramos (modo gramos).
    def _crear_casilla_peso(
        self,
        fila: int,
        modo: str,
        valor: int,
    ) -> QWidget:
        """SpinBoxStock de Kg (modo kg, decimal) o de gramos (modo gramos)."""
        marco = QWidget()
        caja = QHBoxLayout(marco)
        caja.setContentsMargins(
            MARGEN_CASILLA_PESO,
            MARGEN_CASILLA_PESO,
            MARGEN_CASILLA_PESO,
            MARGEN_CASILLA_PESO,
        )
        caja.setSpacing(0)

        spin = SpinBoxStock()
        spin.setProperty("rol", "casilla_peso")
        spin.setFixedHeight(ALTO_CASILLA_PESO)
        if modo == "kg":
            spin.set_modo_kg()
        else:
            spin.set_modo_gramos()
        spin.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        peso_linea = self._texto_peso_linea(self.productos_venta[fila])
        spin.setToolTip(
            f"Kilos de esta linea (decimales: 0.5 = 500 g). Peso total: {peso_linea}"
            if modo == "kg"
            else f"Gramos (0 a 999). Peso total: {peso_linea}",
        )
        spin.blockSignals(True)
        spin.setValue(float(valor))
        spin.blockSignals(False)
        spin.valueChanged.connect(lambda _v, f=fila: self._on_peso_cambiado(f))
        caja.addWidget(spin)
        return marco

    # SpinBoxStock entero para la cantidad de PIEZAS de una linea UNIDAD.
    def _crear_casilla_unidad(self, fila: int, valor: int) -> QWidget:
        """SpinBoxStock entero para la cantidad de PIEZAS de una linea UNIDAD."""
        marco = QWidget()
        caja = QHBoxLayout(marco)
        caja.setContentsMargins(
            MARGEN_CASILLA_PESO,
            MARGEN_CASILLA_PESO,
            MARGEN_CASILLA_PESO,
            MARGEN_CASILLA_PESO,
        )
        caja.setSpacing(0)

        spin = SpinBoxStock()
        spin.setProperty("rol", "casilla_peso")
        spin.setFixedHeight(ALTO_CASILLA_PESO)
        spin.set_modo_entero(True)
        spin.setRange(0, MAX_KILOS_CAPTURA)
        spin.setGroupSeparatorShown(False)
        spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        spin.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        piezas = self._texto_peso_linea(self.productos_venta[fila])
        spin.setToolTip(f"Cantidad de piezas. {piezas}")
        spin.blockSignals(True)
        spin.setValue(float(valor))
        spin.blockSignals(False)
        spin.valueChanged.connect(lambda _v, f=fila: self._on_peso_cambiado(f))
        caja.addWidget(spin)
        return marco

    # Peso legible de la linea: "1 kg y 500 g", "2 und.
    @staticmethod
    def _texto_peso_linea(item: ProductoVenta) -> str:
        """Peso legible de la linea: "1 kg y 500 g", "2 und." o "—"."""
        if not es_medida(item["tipo_venta"]):
            piezas = int(item["cantidad"])
            return f"{piezas} und." if piezas else "—"
        texto = formatear_peso_kg(item["cantidad"])
        return texto if texto else "—"

    # Una de las dos casillas de peso cambio → recalcula la linea.
    def _on_peso_cambiado(self, fila: int) -> None:
        """Una de las dos casillas de peso cambio → recalcula la linea."""
        if self._refrescando or not (0 <= fila < len(self.productos_venta)):
            return

        spin_kg = self._spin_peso_de(fila, "kg")
        if spin_kg is None:
            return

        if not es_medida(self.productos_venta[fila]["tipo_venta"]):
            nueva_cantidad = a_kg(spin_kg.value(), 0)
        else:
            spin_g = self._spin_peso_de(fila, "g")
            nueva_cantidad = a_kg(spin_kg.value(), spin_g.value() if spin_g else 0)

        if nueva_cantidad <= 0 or self.controlador_productos is None:
            self._revertir_cantidad(fila)
            return

        idproducto = int(str(self.productos_venta[fila]["idproducto"]))
        producto = self.controlador_productos.obtener_por_id(idproducto)
        if producto is None:
            self._revertir_cantidad(fila)
            return
        if producto.stock_actual < nueva_cantidad:
            self._avisar_stock_insuficiente(producto, nueva_cantidad)
            self._revertir_cantidad(fila)
            return

        nuevo_subtotal = (self.productos_venta[fila]["precio"] * nueva_cantidad).quantize(
            Decimal("0.01"),
        )
        self.total_bs -= self.productos_venta[fila]["subtotal"]
        self.productos_venta[fila]["cantidad"] = nueva_cantidad
        self.productos_venta[fila]["subtotal"] = nuevo_subtotal
        self.total_bs += nuevo_subtotal
        self._refrescar_tabla_productos()
        self._actualizar_total()

    # Devuelve el SpinBoxStock de Kg o de gramos de la fila indicada.
    def _spin_peso_de(self, fila: int, modo: str) -> SpinBoxStock | None:
        """Devuelve el SpinBoxStock de Kg o de gramos de la fila indicada."""
        columna = 1 if modo == "kg" else 2
        marco = self.tabla_productos_venta.cellWidget(fila, columna)
        if marco is None:
            return None
        spin = marco.findChild(SpinBoxStock)
        return spin if isinstance(spin, SpinBoxStock) else None

    # Los 4 botones rapidos (2x2) que SUMAN peso a una linea del ticket.
    def _crear_botones_peso_rapido_fila(self, nombre: str, fila: int) -> QWidget:
        """Los 4 botones rapidos (2x2) que SUMAN peso a una linea del ticket."""
        contenedor = QWidget()
        grid = QGridLayout(contenedor)
        grid.setContentsMargins(
            MARGEN_IZQ_GRUPO_PESO,
            MARGEN_V_GRUPO_PESO,
            MARGEN_DER_GRUPO_PESO,
            MARGEN_V_GRUPO_PESO,
        )
        grid.setSpacing(SEPARACION_BOTON_PESO_RAPIDO)
        for indice, (peso, etiqueta, larga) in enumerate(
            zip(
                PASOS_PESO_RAPIDO,
                ETIQUETAS_PESO_RAPIDO,
                ETIQUETAS_PESO_RAPIDO_LARGAS,
                strict=True,
            ),
        ):
            btn = self._crear_boton_peso_rapido(etiqueta, f"Sumar {larga} a {nombre}")
            btn.clicked.connect(
                lambda _=False, p=peso, f=fila: self._sumar_peso_rapido(f, p),
            )
            grid.addWidget(btn, indice // 2, indice % 2)
        return contenedor

    # Suma un incremento de peso a la linea indicada y recalcula.
    def _sumar_peso_rapido(self, fila: int, incremento: Decimal) -> None:
        """Suma un incremento de peso a la linea indicada y recalcula."""
        if not (0 <= fila < len(self.productos_venta)):
            return
        spin_kg = self._spin_peso_de(fila, "kg")
        if spin_kg is None:
            return
        spin_g = self._spin_peso_de(fila, "g")
        kilos, gramos = spin_kg.value(), spin_g.value() if spin_g else 0
        total_kg = a_kg(kilos, gramos) + a_kg(incremento, 0)
        kilos, gramos = descomponer_kg(total_kg)
        self._refrescando = True
        try:
            if spin_kg is not None:
                spin_kg.blockSignals(True)
                spin_kg.setValue(float(kilos))
                spin_kg.blockSignals(False)
            if spin_g is not None:
                spin_g.blockSignals(True)
                spin_g.setValue(float(gramos))
                spin_g.blockSignals(False)
        finally:
            self._refrescando = False
        self._on_peso_cambiado(fila)

    # Restaura la cantidad almacenada si la edicion fue invalida.
    def _revertir_cantidad(self, fila: int | None = None) -> None:
        """Restaura la cantidad almacenada si la edicion fue invalida."""
        self._refrescar_tabla_productos()
        if fila is None:
            return
        spin = self._spin_peso_de(fila, "kg")
        if spin is not None:
            spin.setFocus(Qt.FocusReason.OtherFocusReason)
            spin.selectAll()

    # Describe una cantidad en el formato del POS: peso o piezas.
    @staticmethod
    def _texto_cantidad(producto: Producto, cantidad: Decimal) -> str:
        """Describe una cantidad en el formato del POS: peso o piezas."""
        if es_medida(producto.tipo_venta):
            return formatear_peso_kg(cantidad) or formatear_stock(cantidad)
        return f"{formatear_stock(cantidad)} und."

    # Aviso de stock insuficiente, con el peso ya en words (no en kg).
    def _avisar_stock_insuficiente(self, producto: Producto, cantidad: Decimal) -> None:
        """Aviso de stock insuficiente, con el peso ya en words (no en kg)."""
        QMessageBox.warning(
            self,
            "Stock insuficiente",
            f"Stock disponible: {self._texto_cantidad(producto, producto.stock_actual)}."
            f" Solicitado: {self._texto_cantidad(producto, cantidad)}.",
        )

    # Actualiza el total en Bs (grande) y su equivalente en USD.
    def _actualizar_total(self) -> None:
        """Actualiza el total en Bs (grande) y su equivalente en USD."""
        tasa = self._tasa
        if tasa and tasa.tasa_venta > 0:
            total_usd = (self.total_bs / tasa.tasa_venta).quantize(Decimal("0.01"))
            self.lbl_total.setText(f"TOTAL: {formatear_bs(self.total_bs)}")
            self.lbl_total_usd.setText(f"≈ {formatear_usd(total_usd)}")
        else:
            self.lbl_total.setText(f"TOTAL: {formatear_bs(self.total_bs)}")
            self.lbl_total_usd.setText("Sin tasa de cambio")

        self._actualizar_resumen_pagos()

    # Elimina un producto de la lista de la venta.
    def _eliminar_producto_venta(self, fila: int) -> None:
        """Elimina un producto de la lista de la venta."""
        if 0 <= fila < len(self.productos_venta):
            subtotal = self.productos_venta[fila]["subtotal"]
            self.total_bs -= subtotal
            self.productos_venta.pop(fila)
            self._refrescar_tabla_productos()
            self._actualizar_total()
            self._actualizar_visibilidad_pago()

    # Suprimir: elimina la fila seleccionada del ticket.
    def _eliminar_fila_seleccionada(self) -> None:
        """Suprimir: elimina la fila seleccionada del ticket."""
        fila = self.tabla_productos_venta.currentRow()
        if fila >= 0 and fila < len(self.productos_venta):
            self._eliminar_producto_venta(fila)

    # Vacia el ticket de la venta en curso (sin tocar la BD).
    def _limpiar_ticket(self) -> None:
        """Vacia el ticket de la venta en curso (sin tocar la BD)."""
        if not self.productos_venta:
            return
        self.productos_venta = []
        self.total_bs = Decimal("0.00")
        self._reiniciar_pagos()
        self._refrescar_tabla_productos()
        self._actualizar_total()
        self._actualizar_visibilidad_pago()

    # Pregunta antes de vaciar el ticket (los productos se pierden).
    def _confirmar_limpiar_ticket(self) -> None:
        """Pregunta antes de vaciar el ticket (los productos se pierden)."""
        if not self.productos_venta:
            return
        respuesta = QMessageBox.question(
            self,
            "Limpiar Ticket",
            "¿Esta seguro de que desea vaciar el ticket actual?\n"
            "Se perderan los productos agregados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            self._limpiar_ticket()

    # Descarta el desglose de pagos de la venta en curso.
    def _reiniciar_pagos(self) -> None:
        """Descarta el desglose de pagos de la venta en curso."""
        self.pagos = []
        self._limpiar_modo_rapido()
        self._cerrar_panel_mixto()
        self.campo_ref_mixto.clear()
        self.lbl_info_mixto.setText("")
        self._refrescar_tabla_pagos()
        self._actualizar_resumen_pagos()

    # Muestra el metodo de pago solo cuando hay productos en la venta.
    def _actualizar_visibilidad_pago(self) -> None:
        """Muestra el metodo de pago solo cuando hay productos en la venta."""
        hay_productos = bool(self.productos_venta)
        self.grupo_pago.setVisible(hay_productos)
        if not hay_productos and self.pagos:
            self._reiniciar_pagos()
        self._actualizar_estado_cobrar()
        if not hay_productos:
            self._comprobar_reversion_pendiente()

    # Valida los datos y finaliza la venta.
    def _finalizar_venta(self) -> None:
        """Valida los datos y finaliza la venta."""
        if not self.productos_venta:
            QMessageBox.warning(self, "Venta vacia", "Agrega al menos un producto a la venta.")
            return

        if not self.pagos:
            QMessageBox.warning(
                self,
                "Pago",
                "Agrega al menos un pago para cobrar la venta.",
            )
            return

        self._actualizar_tasa()

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

        productos: list[dict[str, object]] = [
            {
                "idproducto": int(str(item["idproducto"])),
                "cantidad": item["cantidad"],
                "precio_bs": item["precio"],
                "subtotal_bs": item["subtotal"],
            }
            for item in self.productos_venta
        ]

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
            venta = self.controlador_ventas.crear(productos, metodo_pago, pagos=pagos)

            QMessageBox.information(
                self,
                "Venta exitosa",
                f"Venta registrada correctamente.\n"
                f"Factura: {venta.numero_factura}\n"
                f"Total: {formatear_bs(venta.total_bs)}",
            )

            self._mostrar_factura(venta)

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

    # Abre la factura imprimible sobre la venta recien registrada.
    def _mostrar_factura(self, venta: Venta) -> None:
        """Abre la factura imprimible sobre la venta recien registrada."""
        try:
            items: list[dict[str, object]] = [dict(item) for item in self.productos_venta]
            pagos: list[dict[str, object]] = [dict(pago) for pago in self.pagos]
            factura = DialogoFactura(
                numero_factura=venta.numero_factura,
                fecha_venta=a_local(venta.fecha_venta),
                nombre_cajero=self.nombre_cajero,
                tasa_venta=venta.tasa_cambio,
                total_bs=venta.total_bs,
                total_usd=venta.total_usd,
                items=items,
                pagos=pagos,
                parent=self,
            )
            factura.exec()
        except Exception as e:
            registrar_excepcion(e, "FormularioVenta._mostrar_factura")
            QMessageBox.warning(
                self,
                "Factura",
                "La venta se registro correctamente, pero no se pudo "
                "mostrar la factura.\n\n"
                "Registrala desde el reporte diario (Excel) si la necesitas.",
            )

