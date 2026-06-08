# ============================================================
# ARCHIVO: utils/validacion.py
# FUNCIONES DE VALIDACION DE DATOS
#
# ¿POR QUE CENTRALIZAR LAS VALIDACIONES?
#   - Evita repetir el mismo "if not x: raise ValueError"
#     en cada servicio.
#   - Los mensajes de error son consistentes.
#   - Si la logica de validacion cambia, se actualiza
#     en un solo lugar.
#
# ¿COMO SE USA?
#   from sistema_financiero.utils import validar_no_vacio
#   validar_no_vacio(producto.nombre_producto, "nombre del producto")
#
# ¿QUE PASA SI FALLA?
#   Lanzan ValueError con un mensaje descriptivo.
#   El llamador (servicio o UI) debe atraparlo con
#   try/except o dejarlo propagar.
# ============================================================

from decimal import Decimal


# ----------------------------------------------------------
# FUNCION: validar_no_vacio()
# Valida que un string no sea None, vacio o solo espacios.
#
# Parametros:
#   valor       → El string a validar.
#   nombre      → Nombre del campo (para el mensaje de error).
#
# Lanza: ValueError si valor es None, "" o "   ".
#
# Uso:
#   validar_no_vacio(usuario, "nombre de usuario")
#   → Si usuario = "" → ValueError: "El nombre de usuario
#     es obligatorio."
#
# ¿POR QUE .strip()?
#   - "   " solo tiene espacios, no es un nombre valido.
#   - .strip() elimina espacios al inicio y final.
#   - Si el resultado es vacio, el campo esta "vacio".
# ----------------------------------------------------------
def validar_no_vacio(valor: str | None, nombre: str) -> None:
    """Valida que un string no sea None, vacio o solo espacios."""
    if not valor or not valor.strip():
        raise ValueError(f"El {nombre} es obligatorio.")


# ----------------------------------------------------------
# FUNCION: validar_longitud_minima()
# Valida que un string tenga al menos N caracteres.
#
# Parametros:
#   valor       → El string a validar.
#   minimo      → Longitud minima aceptable.
#   nombre      → Nombre del campo (para el error).
#
# Lanza: ValueError si len(valor) < minimo.
#
# Uso:
#   validar_longitud_minima(contrasena, 4, "contrasena")
# ----------------------------------------------------------
def validar_longitud_minima(valor: str, minimo: int, nombre: str) -> None:
    """Valida que un string tenga al menos N caracteres."""
    if len(valor) < minimo:
        raise ValueError(
            f"La {nombre} debe tener al menos {minimo} caracteres."
        )


# ----------------------------------------------------------
# FUNCION: validar_no_negativo()
# Valida que un numero (int o Decimal) no sea negativo.
#
# Parametros:
#   valor       → int o Decimal a validar.
#   nombre      → Nombre del campo (para el error).
#
# Lanza: ValueError si valor < 0.
#
# Uso:
#   validar_no_negativo(precio, "precio de venta")
#   → Si precio = -5 → ValueError: "El precio de venta
#     no puede ser negativo."
#
# ¿POR QUE ACEPTA int y Decimal?
#   - El stock es int, los precios son Decimal.
#   - Una sola funcion para ambos casos.
# ----------------------------------------------------------
def validar_no_negativo(valor: int | Decimal, nombre: str) -> None:
    """Valida que un numero no sea negativo."""
    if valor < 0:
        raise ValueError(f"El {nombre} no puede ser negativo.")


# ----------------------------------------------------------
# FUNCION: validar_positivo()
# Valida que un numero sea ESTRICTAMENTE positivo (> 0).
#
# Diferencia con validar_no_negativo():
#   - no_negativo: permite 0 (cero).
#   - positivo: NO permite 0 (debe ser > 0).
#
# Lanza: ValueError si valor <= 0.
#
# Uso:
#   validar_positivo(cantidad, "cantidad")
#   → Si cantidad = 0 → ValueError: "La cantidad debe ser
#     mayor a cero."
# ----------------------------------------------------------
def validar_positivo(valor: int | Decimal, nombre: str) -> None:
    """Valida que un numero sea mayor a cero."""
    if valor <= 0:
        raise ValueError(f"La {nombre} debe ser mayor a cero.")


# ----------------------------------------------------------
# FUNCION: validar_existe()
# Valida que un objeto no sea None (existe en BD).
#
# Uso tipico:
#   producto = session.get(Producto, producto_id)
#   validar_existe(producto, "Producto")
#   → Si producto es None: ValueError: "Producto no existe."
# ----------------------------------------------------------
def validar_existe(obj: object | None, nombre: str) -> None:
    """Valida que un objeto no sea None (existe en BD)."""
    if obj is None:
        raise ValueError(f"{nombre} no existe.")


# ----------------------------------------------------------
# FUNCION: validar_pagos_cubren_total()
# Valida que la suma de los metodos de pago cubra el total.
#
# Parametros:
#   suma_pagos  → Suma de todos los metodos de pago en Bs.
#   total       → Total de la venta en Bs.
#
# Lanza: ValueError si suma_pagos < total.
#
# Uso:
#   validar_pagos_cubren_total(suma_pagos, total_venta)
#   → Si pago 50 y el total es 100:
#     ValueError: "La suma de los metodos de pago (50.00)
#     no cubre el total de la venta (100.00)."
# ----------------------------------------------------------
def validar_pagos_cubren_total(suma_pagos: Decimal, total: Decimal) -> None:
    """Valida que la suma de pagos cubra el total de la venta."""
    if suma_pagos < total:
        raise ValueError(
            f"La suma de los metodos de pago ({suma_pagos}) "
            f"no cubre el total de la venta ({total})."
        )
