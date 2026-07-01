# ============================================================
# PAQUETE: utils/
# UTILIDADES Y HELPERS
# Funciones auxiliares que no pertenecen a una capa
# especifica: formateo de moneda, validacion de datos,
# constantes del sistema, etc.
#
# SUBMODULOS:
#   constantes.py → Constantes del sistema (metodos de pago,
#                   estados, tipos de movimiento, etc.).
#   moneda.py     → Formateo de VES/USD, redondeo, config
#                   de QDoubleSpinBox.
#   validacion.py → Validaciones reutilizables (no vacio,
#                   no negativo, existe en BD, etc.).
#
# USO:
#   from sistema_financiero.utils import formatear_bs
#   from sistema_financiero.utils import METODO_PAGO_EFECTIVO_BS
#   from sistema_financiero.utils import validar_no_vacio
# ============================================================

# Exportar helpers de fecha.
# Exportar constantes.
from .constantes import ESTADO_VENTA_ANULADA as ESTADO_VENTA_ANULADA
from .constantes import ESTADO_VENTA_COMPLETADA as ESTADO_VENTA_COMPLETADA
from .constantes import LONGITUD_MINIMA_CONTRASENA as LONGITUD_MINIMA_CONTRASENA
from .constantes import METODO_PAGO_BIO_PAGO as METODO_PAGO_BIO_PAGO
from .constantes import METODO_PAGO_EFECTIVO_BS as METODO_PAGO_EFECTIVO_BS
from .constantes import METODO_PAGO_EFECTIVO_USD as METODO_PAGO_EFECTIVO_USD
from .constantes import METODO_PAGO_PAGO_MOVIL as METODO_PAGO_PAGO_MOVIL
from .constantes import METODO_PAGO_TARJETA as METODO_PAGO_TARJETA
from .constantes import METODOS_PAGO as METODOS_PAGO
from .constantes import MOTIVO_AJUSTE as MOTIVO_AJUSTE
from .constantes import MOTIVO_COMPRA as MOTIVO_COMPRA
from .constantes import MOTIVO_DEVOLUCION as MOTIVO_DEVOLUCION
from .constantes import MOTIVO_INVENTARIO_FISICO as MOTIVO_INVENTARIO_FISICO
from .constantes import MOTIVO_MERMA as MOTIVO_MERMA
from .constantes import MOTIVO_VENTA as MOTIVO_VENTA
from .constantes import PREFIJO_FACTURA as PREFIJO_FACTURA
from .constantes import RANGO_SPINBOX_MAX as RANGO_SPINBOX_MAX
from .constantes import TIPO_MOVIMIENTO_AJUSTE as TIPO_MOVIMIENTO_AJUSTE
from .constantes import TIPO_MOVIMIENTO_ENTRADA as TIPO_MOVIMIENTO_ENTRADA
from .constantes import TIPO_MOVIMIENTO_SALIDA as TIPO_MOVIMIENTO_SALIDA
from .fecha import ahora as ahora
from .fecha import hoy as hoy

# Exportar funciones de moneda.
from .moneda import DECIMAL_CENTIMO as DECIMAL_CENTIMO
from .moneda import DECIMAL_CERO as DECIMAL_CERO
from .moneda import PREFIJO_BS as PREFIJO_BS
from .moneda import PREFIJO_USD as PREFIJO_USD
from .moneda import PREFIJO_USD_TEXTO as PREFIJO_USD_TEXTO
from .moneda import SIGLAS_USD as SIGLAS_USD
from .moneda import SIMBOLO_BS as SIMBOLO_BS
from .moneda import SIMBOLO_USD as SIMBOLO_USD
from .moneda import configurar_spinbox_bs as configurar_spinbox_bs
from .moneda import configurar_spinbox_usd as configurar_spinbox_usd
from .moneda import formatear_bs as formatear_bs
from .moneda import formatear_usd as formatear_usd
from .moneda import formatear_usd_texto as formatear_usd_texto
from .moneda import redondear_moneda as redondear_moneda

# Exportar funciones de validacion.
from .validacion import validar_existe as validar_existe
from .validacion import validar_longitud_minima as validar_longitud_minima
from .validacion import validar_no_negativo as validar_no_negativo
from .validacion import validar_no_vacio as validar_no_vacio
from .validacion import validar_pagos_cubren_total as validar_pagos_cubren_total
from .validacion import validar_positivo as validar_positivo
