# ============================================================
# ARCHIVO: utils/constantes.py
# CONSTANTES DEL SISTEMA
#
# ¿POR QUE CONSTANTES EN VEZ DE STRINGS LITERALES?
#   Evita "magic strings" repetidos en todo el codigo.
#   Si el nombre de un metodo de pago cambia, solo se
#   modifica AQUI, no en 10 archivos diferentes.
#
# ¿COMO SE USA?
#   from sistema_financiero.utils import METODO_PAGO_EFECTIVO_BS
#   metodo_pago[METODO_PAGO_EFECTIVO_BS] = Decimal("100.00")
# ============================================================

# ----------------------------------------------------------
# METODOS DE PAGO
# Son los 5 metodos de pago que acepta el sistema:
#   efectivo_bs  → Bolivares en efectivo.
#   efectivo_usd → Dolares en efectivo.
#   tarjeta      → Tarjeta de debito/credito (en Bs).
#   pago_movil   → Pago movil (en Bs).
#   bio_pago     → BioPago (en Bs).
#
# Cada metodo de pago se identifica con un string que
# funciona como clave en los diccionarios. Se usa en:
#   - VentaController.crear() para recibir los montos.
#   - Venta.efectivo_bs, Venta.tarjeta, etc. (modelo ORM).
#   - ReporteDiario.efectivo_bs, ReporteDiario.tarjeta, etc.
#   - interfaz.py para crear los QDoubleSpinBox de pago.
#   - reporte_service.py para los encabezados de Excel.
# ----------------------------------------------------------
METODO_PAGO_EFECTIVO_BS: str = "efectivo_bs"
METODO_PAGO_EFECTIVO_USD: str = "efectivo_usd"
METODO_PAGO_TARJETA: str = "tarjeta"
METODO_PAGO_PAGO_MOVIL: str = "pago_movil"
METODO_PAGO_BIO_PAGO: str = "bio_pago"

# Lista completa de metodos de pago para iterar.
METODOS_PAGO: list[str] = [
    METODO_PAGO_EFECTIVO_BS,
    METODO_PAGO_EFECTIVO_USD,
    METODO_PAGO_TARJETA,
    METODO_PAGO_PAGO_MOVIL,
    METODO_PAGO_BIO_PAGO,
]


# ----------------------------------------------------------
# ESTADOS DE VENTA
# Una venta puede estar COMPLETADA (exitosa) o ANULADA.
# COMPLETADA → Venta normal, cuenta en reportes.
# ANULADA    → Se devolvio el stock, no cuenta en reportes.
#
# Se usan en:
#   - Venta.estado (modelo ORM, default "COMPLETADA").
#   - VentaController.crear() → asigna "COMPLETADA".
#   - VentaController.anular() → cambia a "ANULADA".
#   - ReporteService.generar_reporte() → filtra por estado.
# ----------------------------------------------------------
ESTADO_VENTA_COMPLETADA: str = "COMPLETADA"
ESTADO_VENTA_ANULADA: str = "ANULADA"


# ----------------------------------------------------------
# TIPOS DE MOVIMIENTO DE INVENTARIO
# Cada cambio de stock se registra con un tipo:
#   ENTRADA → Suma stock (compra, devolucion).
#   SALIDA  → Resta stock (venta, merma).
#   AJUSTE  → Stock exacto (inventario fisico).
#
# Se usan en:
#   - MovimientoInventario.tipo (modelo ORM).
#   - InventarioService.registrar_entrada/salida/ajuste().
# ----------------------------------------------------------
TIPO_MOVIMIENTO_ENTRADA: str = "ENTRADA"
TIPO_MOVIMIENTO_SALIDA: str = "SALIDA"
TIPO_MOVIMIENTO_AJUSTE: str = "AJUSTE"


# ----------------------------------------------------------
# MOTIVOS DE MOVIMIENTO DE INVENTARIO
# Motivos comunes para registrar movimientos de stock.
# ----------------------------------------------------------
MOTIVO_COMPRA: str = "COMPRA"
MOTIVO_VENTA: str = "VENTA"
MOTIVO_DEVOLUCION: str = "DEVOLUCION"
MOTIVO_MERMA: str = "MERMA"
MOTIVO_AJUSTE: str = "AJUSTE"
MOTIVO_INVENTARIO_FISICO: str = "INVENTARIO FISICO"


# ----------------------------------------------------------
# PREFIJO DE FACTURA
# Formato: FAC-YYYYMMDD-NNN
#   FAC    → prefijo fijo.
#   YYYYMMDD → fecha de emision.
#   NNN   → numero correlativo del dia (001, 002, ...).
#
# Se usa en:
#   - VentaController.crear() para generar numero_factura.
# ----------------------------------------------------------
PREFIJO_FACTURA: str = "FAC"


# ----------------------------------------------------------
# LONGITUD MINIMA DE CONTRASENA
# Politica de seguridad: minimo 4 caracteres.
# Se usa en:
#   - AuthService.crear_usuario().
#   - AuthService.cambiar_contrasena().
#   - AuthService.cambiar_contrasena_admin().
# ----------------------------------------------------------
LONGITUD_MINIMA_CONTRASENA: int = 4


# ----------------------------------------------------------
# RANGO MAXIMO PARA SPINBOX DE PAGO
# Limite superior para QDoubleSpinBox en la UI de ventas.
# ----------------------------------------------------------
RANGO_SPINBOX_MAX: int = 999999


# ----------------------------------------------------------
# TIPOS DE VENTA DE PRODUCTO
# UNIDAD → Se vende por pieza entera (huevos, aceite, pasta).
#           Stock y cantidad en enteros.
# PESO   → Se vende por kilogramos (carne, pollo, verduras).
#           Stock en kg, cantidad en kg (decimal).
# GRAMOS → Se vende por gramos (condimentos, especias).
#           Stock en kg, cantidad en gramos (decimal).
# ----------------------------------------------------------
TIPO_VENTA_UNIDAD: str = "UNIDAD"
TIPO_VENTA_PESO: str = "PESO"
TIPO_VENTA_GRAMOS: str = "GRAMOS"

TIPOS_VENTA: list[str] = [
    TIPO_VENTA_UNIDAD,
    TIPO_VENTA_PESO,
    TIPO_VENTA_GRAMOS,
]
