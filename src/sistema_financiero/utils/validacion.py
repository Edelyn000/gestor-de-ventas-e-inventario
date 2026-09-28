# validacion.py: Validacion y parseo de decimales escritos.

from decimal import Decimal


def validar_no_vacio(valor: str | None, nombre: str) -> None:
    """Valida que un string no sea None, vacio o solo espacios."""
    if not valor or not valor.strip():
        msg = f"El {nombre} es obligatorio."
        raise ValueError(msg)


def validar_longitud_minima(valor: str, minimo: int, nombre: str) -> None:
    """Valida que un string tenga al menos N caracteres."""
    if len(valor) < minimo:
        msg = f"La {nombre} debe tener al menos {minimo} caracteres."
        raise ValueError(msg)


def validar_no_negativo(valor: int | Decimal, nombre: str) -> None:
    """Valida que un numero no sea negativo."""
    if valor < 0:
        msg = f"El {nombre} no puede ser negativo."
        raise ValueError(msg)


def validar_positivo(valor: int | Decimal, nombre: str) -> None:
    """Valida que un numero sea mayor a cero."""
    if valor <= 0:
        msg = f"La {nombre} debe ser mayor a cero."
        raise ValueError(msg)


def validar_existe(obj: object | None, nombre: str) -> None:
    """Valida que un objeto no sea None (existe en BD)."""
    if obj is None:
        msg = f"{nombre} no existe."
        raise ValueError(msg)


def validar_pagos_cubren_total(suma_pagos: Decimal, total: Decimal) -> None:
    """Valida que la suma de pagos cubra el total de la venta."""
    if suma_pagos < total:
        msg = (
            f"La suma de los metodos de pago ({suma_pagos}) "
            f"no cubre el total de la venta ({total})."
        )
        raise ValueError(msg)


def parsear_decimal_escrito(texto: str) -> Decimal | None:
    """Convierte un texto de monto a Decimal, aceptando ',' o '.' decimal."""
    if not texto:
        return None
    limpio = texto.strip()
    if not limpio:
        return None

    pos_coma = limpio.find(",")
    pos_punto = limpio.find(".")
    if pos_coma != -1 and pos_punto != -1:
        if pos_coma > pos_punto:
            normalizado = limpio.replace(".", "").replace(",", ".")
        else:
            normalizado = limpio.replace(",", "")
    elif pos_coma != -1:
        normalizado = limpio.replace(",", ".")
    else:
        normalizado = limpio

    try:
        valor = Decimal(normalizado)
    except Exception:
        return None
    if not valor.is_finite():
        return None
    return valor

