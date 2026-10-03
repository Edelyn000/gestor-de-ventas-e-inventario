# estilos.py: Estilos QSS globales del tema claro con roles.

AZUL_PRINCIPAL = "#1e3a8a"
AZUL_ACCION = "#2563eb"
ROJO_ALERTA = "#dc2626"
VERDE_EXITO = "#16a34a"
NARANJA_ADVERTENCIA = "#d97706"
COLOR_FONDO = "#f3f4f6"
COLOR_TEXTO = "#000000"
COLOR_TEXTO_SUAVE = "#000000"
COLOR_SUPERFICIE = "#ffffff"
COLOR_BORDE = "#e5e7eb"
COLOR_FOCO = "#2563eb"

QSS_APP = """
/* ===== Tema claro global: fondo gris claro, texto gris oscuro ===== */
QMainWindow, QWidget, QDialog {
    background-color: #f3f4f6;
    color: #000000;
}
QLabel {
    color: #000000;
}
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
    color: #000000;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #000000;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 5px 8px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #2563eb;
}
QComboBox::drop-down {
    background-color: #ffffff;
    border: none;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #000000;
    selection-background-color: #dbeafe;
    selection-color: #1e3a8a;
}
QPushButton {
    background-color: #f1f5f9;
    color: #000000;
    border: 1px solid #d5dbe3;
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #e2e8f0;
}
QPushButton:pressed {
    background-color: #cbd5e1;
}
QTableWidget, QTableWidget QHeaderView {
    background-color: #ffffff;
    color: #000000;
    gridline-color: #e5e7eb;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
}
QTableWidget::item {
    padding: 6px;
}
/* Filas resaltadas: el fondo claro SIEMPRE lleva texto oscuro (negro).
   Sin la regla de color, Qt usa el texto de seleccion del sistema
   (blanco/gris claro) y la fila queda ilegible sobre #dbeafe.
   Las celdas con color propio (ENTRADA/SALIDA, ANULADA/COMPLETADA,
   Estado del dashboard) conservan su color al NO estar seleccionadas. */
QTableWidget::item:hover {
    background-color: #f1f5f9;
    color: #000000;
}
QTableWidget::item:selected {
    background-color: #dbeafe;
    color: #000000;
}
QTableWidget::item:selected:hover {
    background-color: #bfdbfe;
    color: #000000;
}
QHeaderView::section {
    background-color: #eff6ff;
    color: #1e3a8a;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #2563eb;
    font-weight: bold;
}
QListWidget {
    background-color: #f3f4f6;
    color: #1e3a8a;
    border: none;
    outline: none;
    padding: 6px;
}
QListWidget::item {
    padding: 12px;
    border: none;
    border-radius: 6px;
    margin: 2px 0;
    color: #1e3a8a;
    font-weight: bold;
}
QListWidget::item:selected {
    background-color: #1e3a8a;
    color: #ffffff;
}
QListWidget::item:hover {
    background-color: #e0e7ff;
}
QListWidget::item:selected:hover {
    background-color: #1e3a8a;
    color: #ffffff;
}
QStatusBar {
    background-color: #f1f5f9;
    color: #000000;
}
QFrame {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
}
QScrollBar:vertical {
    background-color: #f3f4f6;
    width: 10px;
    border: none;
}
QScrollBar:horizontal {
    background-color: #f3f4f6;
    height: 10px;
    border: none;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #cbd5e1;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background-color: #94a3b8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    height: 0px;
    width: 0px;
}
QToolTip {
    background-color: #334155;
    color: #ffffff;
    border: none;
    padding: 4px;
}
QMessageBox {
    background-color: #ffffff;
}
QMessageBox QLabel {
    color: #000000;
}
QMessageBox QPushButton {
    min-width: 80px;
}

/* ===== Botones de color (texto blanco sobre tono suave) ===== */
QPushButton[rol="primario"] {
    background-color: #2563eb;
    color: #ffffff;
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
}
QPushButton[rol="primario"]:hover { background-color: #1d4ed8; }

QPushButton[rol="accion"] {
    background-color: #16a34a;
    color: #ffffff;
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
}
QPushButton[rol="accion"]:hover { background-color: #15803d; }

QPushButton[rol="peligro"] {
    background-color: #dc2626;
    color: #ffffff;
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
}
QPushButton[rol="peligro"]:hover { background-color: #b91c1c; }

QPushButton[rol="alerta"] {
    background-color: #d97706;
    color: #ffffff;
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
}
QPushButton[rol="alerta"]:hover { background-color: #b45309; }

QPushButton[rol="informacion"] {
    background-color: #2563eb;
    color: #ffffff;
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
}
QPushButton[rol="informacion"]:hover { background-color: #1d4ed8; }

QPushButton[rol="secundario"] {
    background-color: #e2e8f0;
    color: #000000;
    border: 1px solid #cbd5e1;
    padding: 8px 16px;
    border-radius: 6px;
}
QPushButton[rol="secundario"]:hover { background-color: #cbd5e1; }

QPushButton[rol="guardar"] {
    background-color: #2563eb;
    color: #ffffff;
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
}
QPushButton[rol="guardar"]:hover { background-color: #1d4ed8; }

QPushButton[rol="exito"] {
    background-color: #16a34a;
    color: #ffffff;
    padding: 10px 20px;
    border: none;
    border-radius: 6px;
}
QPushButton[rol="exito"]:hover { background-color: #15803d; }

QPushButton[rol="caja_abrir"] {
    background-color: #16a34a;
    color: #ffffff;
    padding: 6px 14px;
    border: none;
    border-radius: 6px;
}
QPushButton[rol="caja_abrir"]:hover { background-color: #15803d; }

QPushButton[rol="caja_cerrar"] {
    background-color: #d97706;
    color: #ffffff;
    padding: 6px 14px;
    border: none;
    border-radius: 6px;
}
QPushButton[rol="caja_cerrar"]:hover { background-color: #b45309; }

/* ===== POS de venta (FormularioVenta) ===== */
/* Cabecera azul de marca con texto claro (solo dentro del POS). */
QFrame[rol="cabecera"] {
    background-color: #1e3a8a;
    border: none;
    border-radius: 0px;
}
QFrame[rol="cabecera"] QLabel {
    color: #ffffff;
    background-color: transparent;
    border: none;
}
QLabel[rol="cabecera_titulo"] {
    color: #ffffff;
    font-size: 18px;
    font-weight: bold;
    background-color: transparent;
    border: none;
}

/* Tasa del POS: BCV (blanco) vs MANUAL (ambar, avisa al cajero).
   Selectores con ancestro cabecera para ganar especificidad sobre
   QFrame[rol="cabecera"] QLabel (las reglas [rol=...] solas tienen
   menor peso que el selector de ancestro). */
QFrame[rol="cabecera"] QLabel[rol="tasa_bcv_auto"] {
    color: #ffffff;
    font-weight: bold;
    background-color: transparent;
    border: none;
}
QFrame[rol="cabecera"] QLabel[rol="tasa_bcv_manual"] {
    color: #fcd34d;
    font-weight: bold;
    background-color: transparent;
    border: none;
}

/* Boton "Tasa Manual" de la cabecera del POS (blanco sobre azul). */
QFrame[rol="cabecera"] QPushButton[rol="tasa_manual_boton"] {
    background-color: #ffffff;
    color: #1e3a8a;
    border: none;
    border-radius: 6px;
    font-size: 12px;
    font-weight: bold;
    padding: 4px 10px;
}
QFrame[rol="cabecera"] QPushButton[rol="tasa_manual_boton"]:hover {
    background-color: #e0e7ff;
}
QFrame[rol="cabecera"] QPushButton[rol="tasa_manual_boton"]:disabled {
    background-color: #94a3b8;
    color: #e2e8f0;
}

/* Boton (+) del catalogo del POS (lista de productos a la izquierda). */
QPushButton[rol="agregar_catalogo"] {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 14px;
    font-size: 14px;
    font-weight: bold;
    padding: 2px 6px;
    min-width: 0;
}
QPushButton[rol="agregar_catalogo"]:hover {
    background-color: #1d4ed8;
}

/* Botones rapidos de peso de la FILA del ticket (PESO): boton amarillo
   suave. (El catalogo ya no los muestra: ahi hay un solo "+" azul con el
   rol agregar_catalogo; los 4 rapidos viven solo en la columna "+ Peso"
   de cada linea, donde tienen altura propia.) */
QPushButton[rol="agregar_catalogo_peso"] {
    background-color: #f0c14b;
    color: #1a1a1a;
    border: none;
    border-radius: 14px;
    font-size: 11px;
    font-weight: bold;
    /* Padding 2px 3px (no 6px): con 6px las etiquetas de los botones
       rapidos de peso ("100g") se recortaban dentro del ancho medido. */
    padding: 2px 3px;
    min-width: 0;
}
QPushButton[rol="agregar_catalogo_peso"]:hover {
    background-color: #d9a82e;
}

/* Casillas de cantidad del ticket: spinbox compacto. Sin flechas
   nativas (set_modo_kg/gramos usan NoButtons) y con rango 0-999 la caja
   pide ~60px ("999,999" en la Kg decimal): la columna de 88px la deja
   holgada y la altura (34px) la fija
   formulario_venta._crear_casilla_peso / _crear_casilla_unidad (la
   casilla "Cant." de las lineas UNIDAD usa la misma caja). Este padding
   pequeño es lo que evita que el numero se recorte. */
QDoubleSpinBox[rol="casilla_peso"] {
    padding: 1px 2px;
    min-width: 0;
}

/* Fila de categorias del POS. */
QPushButton[rol="categoria"] {
    background-color: #f1f5f9;
    color: #000000;
    padding: 8px 14px;
    border-radius: 16px;
    border: 1px solid #d5dbe3;
    font-weight: bold;
}
QPushButton[rol="categoria"]:hover { background-color: #e2e8f0; }
QPushButton[rol="categoria_activa"] {
    background-color: #2563eb;
    color: #ffffff;
    padding: 8px 14px;
    border-radius: 16px;
    border: none;
    font-weight: bold;
}
QPushButton[rol="categoria_activa"]:hover { background-color: #1d4ed8; }

/* Acciones principales del ticket. */
QPushButton[rol="cobrar"] {
    background-color: #16a34a;
    color: #ffffff;
    padding: 10px 20px;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton[rol="cobrar"]:hover { background-color: #15803d; }
QPushButton[rol="anular"] {
    background-color: #dc2626;
    color: #ffffff;
    padding: 10px 20px;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton[rol="anular"]:hover { background-color: #b91c1c; }

/* Metodos de pago del POS (desglose multi-pago). */
QPushButton[rol="metodo"] {
    background-color: #f1f5f9;
    color: #000000;
    border: 1px solid #d5dbe3;
    border-radius: 6px;
    font-size: 12px;
    font-weight: bold;
}
QPushButton[rol="metodo"]:hover { background-color: #e2e8f0; }
QPushButton[rol="metodo_activo"] {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #1d4ed8;
    border-radius: 6px;
    font-size: 12px;
    font-weight: bold;
}
QPushButton[rol="metodo_activo"]:hover { background-color: #1d4ed8; }
QPushButton[rol="quitar_pago"] {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    font-size: 11px;
    font-weight: bold;
    /* Compacto: tiene que entrar en la columna Borrar del desglose de pagos
       (el padding 6px 16px generico daba un sizeHint de 81px y desbordaba). */
    padding: 2px 4px;
    min-width: 0px;
}
QPushButton[rol="quitar_pago"]:hover { background-color: #b91c1c; }
QPushButton[rol="anular_fila"] {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    font-size: 12px;
    /* Compacto: entra en la columna Acciones de la tabla de ventas (48x26). */
    padding: 2px 4px;
    min-width: 0px;
}
QPushButton[rol="anular_fila"]:hover { background-color: #b91c1c; }
QPushButton[rol="anular_fila"]:disabled {
    background-color: #e5e7eb;
    color: #9ca3af;
}

/* POS: boton PAGO MIXTO (abre el panel docked de pagos parciales). */
QPushButton[rol="pago_mixto_boton"] {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    font-size: 12px;
    font-weight: bold;
}
QPushButton[rol="pago_mixto_boton"]:hover { background-color: #1d4ed8; }
QPushButton[rol="pago_mixto_boton"]:checked { background-color: #1e3a8a; }

/* POS: fila de efectivo recibido (cobro rapido con vuelto en vivo). */
QFrame[rol="fila_recibido"] {
    background-color: #ffffff;
    border: 1px solid #d5dbe3;
    border-radius: 6px;
}

/* POS: panel docked "Combinar metodos de pago" (parciales). */
QFrame[rol="panel_mixto"] {
    background-color: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 6px;
}

/* ===== Tarjetas del dashboard (borde superior de color) ===== */
QFrame[rol="tarjeta"] {
    background-color: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 10px;
}
QFrame[rol="tarjeta"][acento="azul"] { border-top: 4px solid #2563eb; }
QFrame[rol="tarjeta"][acento="naranja"] { border-top: 4px solid #d97706; }
QFrame[rol="tarjeta"][acento="rojo"] { border-top: 4px solid #dc2626; }
QFrame[rol="tarjeta"][acento="verde"] { border-top: 4px solid #16a34a; }

/* ===== Panel de informacion / resumen (tarjeta azul claro) ===== */
/* Misma regla que el panel "Caja del Turno" de Ventas: los paneles
   informativos se distinguen con fondo azul claro y borde suave,
   mientras que tablas y filtros se mantienen blancos (decision del
   usuario 2026-09-25). */
QFrame[rol="panel_interno"] {
    background-color: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 10px;
}

/* ===== Labels con rol ===== */
QLabel[rol="seccion"] {
    font-size: 14px;
    font-weight: bold;
    color: #000000;
}
QLabel[rol="seccion_grande"] {
    font-size: 16px;
    font-weight: bold;
    color: #000000;
}
QLabel[rol="titulo_tarjeta"] {
    color: #000000;
    font-size: 12px;
}
QLabel[rol="valor_tarjeta"] {
    font-size: 18px;
    font-weight: bold;
    color: #000000;
}
QLabel[rol="total"] {
    font-size: 18px;
    font-weight: bold;
}
QLabel[rol="total_gigante"] {
    font-size: 24px;
    font-weight: bold;
    color: #000000;
}
QLabel[rol="resumen_falta"] {
    font-size: 13px;
    font-weight: bold;
    color: #dc2626;
}
QLabel[rol="resumen_ok"] {
    font-size: 13px;
    font-weight: bold;
    color: #16a34a;
}

/* ===== Barra superior del sistema (header) ===== */
/* Fondo azul oscuro de marca; texto y (si los hubiera) botones blancos.
   Reutilizado por la ventana principal y la ventana de login. */
QFrame[rol="cabecera_aplicacion"] {
    background-color: #1e3a8a;
    border: none;
    border-radius: 0px;
}
QFrame[rol="cabecera_aplicacion"] QLabel {
    color: #ffffff;
    background-color: transparent;
    border: none;
}
QLabel[rol="cabecera_aplicacion_titulo"] {
    color: #ffffff;
    font-size: 18px;
    font-weight: bold;
    background-color: transparent;
    border: none;
}
QLabel[rol="cabecera_aplicacion_usuario"] {
    color: #ffffff;
    font-size: 13px;
    background-color: transparent;
    border: none;
}
/* Boton "Cerrar Sesion" de la cabecera: transparente con borde claro;
   al pasar el mouse se vuelve blanco con texto azul (misma marca). */
QPushButton[rol="cabecera_salir"] {
    background-color: transparent;
    color: #ffffff;
    border: 1px solid #93c5fd;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 12px;
}
QPushButton[rol="cabecera_salir"]:hover {
    background-color: #ffffff;
    color: #1e3a8a;
    border-color: #ffffff;
}
QPushButton[rol="cabecera_salir"]:pressed {
    background-color: #dbeafe;
}

/* ===== Titulo de pantalla (tarjeta con barra lateral) ===== */
/* Fondo blanco, barra vertical izquierda de 5px (#2563eb) y esquinas
   redondeadas SOLO a la derecha: la barra queda recta (si se redondean
   las 4 esquinas, la barra de acento quedaria curva). */
QFrame[rol="titulo_pagina"] {
    background-color: #ffffff;
    border: none;
    border-left: 5px solid #2563eb;
    border-top-left-radius: 0px;
    border-bottom-left-radius: 0px;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}
QFrame[rol="titulo_pagina"] QLabel {
    color: #1e3a8a;
    font-size: 24px;
    font-weight: bold;
    background-color: transparent;
    border: none;
}

/* ===== Pestanas (Catalogo / Movimientos de Productos) ===== */
/* Texto SIEMPRE negro en todos los estados, sobre fondos claros (tema
   claro). Antes solo se fijaba `color` sin background/border: Qt dejaba
   al estilo nativo de Windows dibujar la pestana con su propia paleta
   (texto blanco ilegible sobre gris claro). Se definen los estados con
   los grises de QPushButton del tema (misma paleta) y la pestana activa
   se distingue con acento azul superior + negrita, nunca texto blanco.
   (2026-09-27) */
QTabWidget::pane {
    border: 1px solid #e5e7eb;
    top: -1px;
    background-color: #ffffff;
}
QTabBar {
    background-color: #f3f4f6;
}
QTabBar::tab {
    color: #000000;
    background-color: #f1f5f9;
    border: 1px solid #d5dbe3;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 20px;
    min-width: 110px;
}
QTabBar::tab:hover:!selected {
    background-color: #e2e8f0;
    color: #000000;
}
QTabBar::tab:selected {
    color: #000000;
    font-weight: bold;
    background-color: #ffffff;
    border-top: 3px solid #2563eb;
}

/* ===== Texto equivalente en Bs (formulario de producto) ===== */
/* Muestra pequena junto a cada precio en USD ("Equivalente: X Bs"). Se
   usa texto gris azulado discreto para no competir con el campo editable. */
QLabel[rol="equivalente"] {
    color: #475569;
    font-size: 11px;
    background-color: transparent;
    border: none;
    padding-left: 4px;
}

/* ===== Panel "Caja del Turno" (tarjeta clara) ===== */
/* Tarjeta azul claro sutil con las cajas de valor blancas: mantiene el
   contraste de los valores pero en armonia con el tema claro general. */
QGroupBox[rol="panel_caja"] {
    background-color: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 10px;
    font-weight: bold;
    color: #1e3a8a;
}
QGroupBox[rol="panel_caja"]::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #1e3a8a;
}
QLabel[rol="etiqueta_panel_caja"] {
    color: #334155;
    font-size: 12px;
    font-weight: bold;
    background-color: transparent;
    border: none;
}
/* Caja blanca con borde gris medio: los valores destacan sobre el gris. */
QLabel[rol="valor_caja"] {
    background-color: #ffffff;
    border: 2px solid #9ca3af;
    border-radius: 4px;
    padding: 4px 10px;
    color: #111827;
    font-size: 13px;
}
QLabel[rol="estado_abierta"] {
    background-color: #ffffff;
    border: 2px solid #16a34a;
    border-radius: 4px;
    padding: 4px 10px;
    color: #16a34a;
    font-size: 14px;
    font-weight: bold;
}
QLabel[rol="estado_cerrada"] {
    background-color: #ffffff;
    border: 2px solid #dc2626;
    border-radius: 4px;
    padding: 4px 10px;
    color: #dc2626;
    font-size: 14px;
    font-weight: bold;
}

/* ===== Celda "Total de Venta" de la tabla de ventas ===== */
/* UNA cantidad clara (Bs salvo ventas pagadas solo en USD): se muestra
   siempre en negrita oscura, la moneda del total facturado. */
QLabel[rol="total_tabla_bs"] {
    font-size: 13px;
    font-weight: bold;
    color: #111827;
}

/* ===== POS: indicador de pago mixto ===== */
/* Aparece en el resumen cuando hay 2+ metodos de pago registrados. */
QLabel[rol="pago_mixto"] {
    font-size: 13px;
    font-weight: bold;
    color: #2563eb;
}
"""
