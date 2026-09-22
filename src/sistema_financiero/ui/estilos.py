# ============================================================
# ARCHIVO: ui/estilos.py — TEMA CLARO CENTRALIZADO (QSS)
# ============================================================
# Unico lugar donde se definen los estilos globales de la app.
# Tema claro con la paleta de marca (basada en el logo):
#   azul principal, azul de accion, rojo de alerta, verde de
#   exito y naranja de advertencia, todos suavizados para
#   pantalla. Fondo gris muy claro, superficies blancas.
#
# COMO USAR LOS ROLES (botones de color):
#   boton.setProperty("rol", "accion")
#   → el QSS los pinta via QPushButton[rol="accion"]
#
# NOTA IMPORTANTE (cardinalidad): los selectores por atributo
# [rol="..."] SOLO aplican a widgets que tengan setProperty("rol", ...).
# Un boton nuevo sin rol recibe el estilo base QPushButton (fondo gris).
# Si un boton recien creado "no tiene color", falta el setProperty.
#
# ROLES DISPONIBLES:
#   primario      → azul (#2563eb)        : Ingresar, Nueva Venta, Agregar,
#                                           Crear Usuario, Guardar, Cerrar Dia
#   accion        → verde (#16a34a)       : entrada de inventario (exito)
#   peligro       → rojo (#dc2626)        : eliminar, anular, salida inventario
#   alerta        → naranja (#d97706)     : ajuste, regenerar reporte
#   informacion   → azul (#2563eb)        : refrescar, exportar excel
#   secundario    → gris oscuro (#e2e8f0) : acciones secundarias (Editar)
#   guardar       → azul (#2563eb)        : guardar cambios (perfil/usuarios)
#   exito         → verde (#16a34a)       : finalizar venta (reserva)
#   caja_abrir    → verde (#16a34a)       : abrir caja
#   caja_cerrar   → naranja (#d97706)     : cerrar caja
#   metodo        → gris claro            : metodo de pago sin elegir (POS)
#   metodo_activo → azul (#2563eb)        : metodo de pago elegido (POS)
#   quitar_pago   → rojo (#dc2626)        : borrar un pago del desglose
#
# ROLES PARA LABELS:
#   seccion       → titulo de seccion (14px, gris oscuro, bold)
#   seccion_grande→ titulo de seccion (16px, gris oscuro, bold)
#   titulo_tarjeta→ titulo de tarjeta del dashboard (12px, gris suave)
#   valor_tarjeta → valor numerico de tarjeta (18px, gris oscuro, bold)
#   total         → total de la venta (18px, gris oscuro, bold)
#   resumen_falta → falta por cubrir (13px, rojo, bold)
#   resumen_ok    → cubierto / cambio (13px, verde, bold)
#
# ROLES PARA TARJETAS DEL DASHBOARD (QFrame):
#   rol="tarjeta" + acento="azul|naranja|rojo|verde" → borde superior
#   de 4px del color correspondiente (guia visual por tipo de dato).
#
# LO QUE NO SE DEBE TOCAR AQUI:
#   - Los estilos DINAMICOS que cambian por estado en tiempo de
#     ejecucion (colores de IndicadorStock, estado de caja
#     ABIERTA/CERRADA, filas coloreadas de tablas) se mantienen
#     inline en sus widgets de origen, usando esta misma paleta.
# ============================================================

# --- Paleta de marca (constantes de referencia; el QSS usa los hex).
AZUL_PRINCIPAL = "#1e3a8a"  # cabeceras, item activo del menu
AZUL_ACCION = "#2563eb"  # botones principales
ROJO_ALERTA = "#dc2626"  # eliminar, anular, errores, sin stock
VERDE_EXITO = "#16a34a"  # cobrar, entrada, abrir caja, completada
NARANJA_ADVERTENCIA = "#d97706"  # ajuste, stock bajo, cerrar caja
COLOR_FONDO = "#f3f4f6"  # fondo de pantalla (gris muy claro)
COLOR_TEXTO = "#374151"  # texto principal (gris oscuro)
COLOR_TEXTO_SUAVE = "#6b7280"  # texto secundario
COLOR_SUPERFICIE = "#ffffff"  # tarjetas, tablas, inputs
COLOR_BORDE = "#e5e7eb"  # bordes suaves
COLOR_FOCO = "#2563eb"  # foco de inputs y selecciones

QSS_APP = """
/* ===== Tema claro global: fondo gris claro, texto gris oscuro ===== */
QMainWindow, QWidget, QDialog {
    background-color: #f3f4f6;
    color: #374151;
}
QLabel {
    color: #374151;
}
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
    color: #374151;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #374151;
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
    color: #374151;
    selection-background-color: #dbeafe;
    selection-color: #1e3a8a;
}
QPushButton {
    background-color: #f1f5f9;
    color: #374151;
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
    color: #374151;
    gridline-color: #e5e7eb;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
}
QTableWidget::item {
    padding: 6px;
}
QTableWidget::item:selected {
    background-color: #dbeafe;
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
    color: #374151;
    border: none;
    outline: none;
    padding: 6px;
}
QListWidget::item {
    padding: 12px;
    border: none;
    border-radius: 6px;
    margin: 2px 0;
    color: #374151;
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
    color: #4b5563;
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
    color: #374151;
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
    color: #334155;
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

/* Botones de producto del catalogo (grid del POS). */
QPushButton[rol="producto"] {
    background-color: #ffffff;
    color: #374151;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 10px 14px;
    font-weight: bold;
    text-align: center;
}
QPushButton[rol="producto"]:hover {
    background-color: #dbeafe;
    border: 1px solid #2563eb;
}

/* Productos a granel (PESO/GRAMOS): fondo amarillo suave. */
QPushButton[rol="producto_peso"] {
    background-color: #fff3cd;
    color: #374151;
    border: 1px solid #f0d98c;
    border-radius: 8px;
    padding: 10px 14px;
    font-weight: bold;
    text-align: center;
}
QPushButton[rol="producto_peso"]:hover {
    background-color: #ffeaa5;
    border: 1px solid #f0c14b;
}

/* Fila de categorias del POS. */
QPushButton[rol="categoria"] {
    background-color: #f1f5f9;
    color: #374151;
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
    color: #374151;
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

/* ===== Tarjetas del dashboard (borde superior de color) ===== */
QFrame[rol="tarjeta"] {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
}
QFrame[rol="tarjeta"][acento="azul"] { border-top: 4px solid #2563eb; }
QFrame[rol="tarjeta"][acento="naranja"] { border-top: 4px solid #d97706; }
QFrame[rol="tarjeta"][acento="rojo"] { border-top: 4px solid #dc2626; }
QFrame[rol="tarjeta"][acento="verde"] { border-top: 4px solid #16a34a; }

/* ===== Labels con rol ===== */
QLabel[rol="seccion"] {
    font-size: 14px;
    font-weight: bold;
    color: #374151;
}
QLabel[rol="seccion_grande"] {
    font-size: 16px;
    font-weight: bold;
    color: #374151;
}
QLabel[rol="titulo_tarjeta"] {
    color: #6b7280;
    font-size: 12px;
}
QLabel[rol="valor_tarjeta"] {
    font-size: 18px;
    font-weight: bold;
    color: #374151;
}
QLabel[rol="total"] {
    font-size: 18px;
    font-weight: bold;
}
QLabel[rol="total_gigante"] {
    font-size: 24px;
    font-weight: bold;
    color: #374151;
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
"""
