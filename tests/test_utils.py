"""Pruebas para utils/ — constantes, moneda y validacion.

Todas son funciones puras (sin BD, sin UI) excepto
configurar_spinbox_bs/usd que requieren QDoubleSpinBox."""
from decimal import Decimal

import pytest

from sistema_financiero.utils import (
    DECIMAL_CENTIMO,
    DECIMAL_CERO,
    ESTADO_VENTA_ANULADA,
    ESTADO_VENTA_COMPLETADA,
    LONGITUD_MINIMA_CONTRASENA,
    METODO_PAGO_BIO_PAGO,
    METODO_PAGO_EFECTIVO_BS,
    METODO_PAGO_EFECTIVO_USD,
    METODO_PAGO_PAGO_MOVIL,
    METODO_PAGO_TARJETA,
    METODOS_PAGO,
    MOTIVO_AJUSTE,
    MOTIVO_COMPRA,
    MOTIVO_DEVOLUCION,
    MOTIVO_INVENTARIO_FISICO,
    MOTIVO_MERMA,
    MOTIVO_VENTA,
    PREFIJO_FACTURA,
    RANGO_SPINBOX_MAX,
    SIMBOLO_BS,
    SIMBOLO_USD,
    TIPO_MOVIMIENTO_AJUSTE,
    TIPO_MOVIMIENTO_ENTRADA,
    TIPO_MOVIMIENTO_SALIDA,
    formatear_bs,
    formatear_usd,
    formatear_usd_texto,
    redondear_moneda,
    validar_existe,
    validar_longitud_minima,
    validar_no_negativo,
    validar_no_vacio,
    validar_pagos_cubren_total,
    validar_positivo,
)


# ============================================================
# CONSTANTES
# ============================================================
class TestConstantes:
    def test_metodos_pago_todos_definidos(self):
        assert METODO_PAGO_EFECTIVO_BS == "efectivo_bs"
        assert METODO_PAGO_EFECTIVO_USD == "efectivo_usd"
        assert METODO_PAGO_TARJETA == "tarjeta"
        assert METODO_PAGO_PAGO_MOVIL == "pago_movil"
        assert METODO_PAGO_BIO_PAGO == "bio_pago"
        assert METODOS_PAGO == [
            "efectivo_bs",
            "efectivo_usd",
            "tarjeta",
            "pago_movil",
            "bio_pago",
        ]

    def test_estados_venta(self):
        assert ESTADO_VENTA_COMPLETADA == "COMPLETADA"
        assert ESTADO_VENTA_ANULADA == "ANULADA"

    def test_tipos_movimiento(self):
        assert TIPO_MOVIMIENTO_ENTRADA == "ENTRADA"
        assert TIPO_MOVIMIENTO_SALIDA == "SALIDA"
        assert TIPO_MOVIMIENTO_AJUSTE == "AJUSTE"

    def test_motivos_movimiento(self):
        assert MOTIVO_COMPRA == "COMPRA"
        assert MOTIVO_VENTA == "VENTA"
        assert MOTIVO_DEVOLUCION == "DEVOLUCION"
        assert MOTIVO_MERMA == "MERMA"
        assert MOTIVO_AJUSTE == "AJUSTE"
        assert MOTIVO_INVENTARIO_FISICO == "INVENTARIO FISICO"

    def test_prefijo_factura(self):
        assert PREFIJO_FACTURA == "FAC"

    def test_longitud_minima_contrasena(self):
        assert LONGITUD_MINIMA_CONTRASENA == 4

    def test_rango_spinbox(self):
        assert RANGO_SPINBOX_MAX == 999999


# ============================================================
# MONEDA
# ============================================================
class TestMoneda:
    def test_decimal_cero(self):
        assert Decimal("0.00") == DECIMAL_CERO

    def test_decimal_centimo(self):
        assert Decimal("0.01") == DECIMAL_CENTIMO

    def test_simbolos(self):
        assert SIMBOLO_BS == "Bs."
        assert SIMBOLO_USD == "$"

    @pytest.mark.parametrize(
        ("valor", "decimales", "miles", "esperado"),
        [
            (Decimal("1234.50"), 2, True, "Bs. 1,234.50"),
            (Decimal("0.00"), 2, True, "Bs. 0.00"),
            (Decimal("1000"), 2, False, "Bs. 1000.00"),
            (Decimal("99.9999"), 3, True, "Bs. 99.9999" if False else "Bs. 100.000"),
        ],
    )
    def test_formatear_bs(self, valor, decimales, miles, esperado):
        assert formatear_bs(valor, decimales, miles) == esperado

    def test_formatear_bs_por_defecto(self):
        assert formatear_bs(Decimal("1500.50")) == "Bs. 1,500.50"

    def test_formatear_usd(self):
        assert formatear_usd(Decimal("50.00")) == "$ 50.00"
        assert formatear_usd(Decimal("1234.56")) == "$ 1,234.56"
        assert formatear_usd(Decimal("0.00"), miles=False) == "$ 0.00"

    def test_formatear_usd_texto(self):
        assert formatear_usd_texto(Decimal("50.00")) == "USD 50.00"
        assert formatear_usd_texto(Decimal("1234.56")) == "USD 1,234.56"

    def test_redondear_moneda(self):
        assert redondear_moneda(Decimal("10.003")) == Decimal("10.00")
        assert redondear_moneda(Decimal("10.006")) == Decimal("10.01")
        assert redondear_moneda(Decimal("0.999")) == Decimal("1.00")

    def test_redondear_moneda_con_division(self):
        resultado = redondear_moneda(Decimal("10.00") / Decimal("3"))
        assert resultado == Decimal("3.33")


# ============================================================
# VALIDACION
# ============================================================
class TestValidacion:
    def test_validar_no_vacio_ok(self):
        assert validar_no_vacio("hola", "campo") is None

    def test_validar_no_vacio_none(self):
        with pytest.raises(ValueError, match="El campo es obligatorio."):
            validar_no_vacio(None, "campo")

    def test_validar_no_vacio_vacio(self):
        with pytest.raises(ValueError, match="El nombre es obligatorio."):
            validar_no_vacio("", "nombre")

    def test_validar_no_vacio_espacios(self):
        with pytest.raises(ValueError, match="El campo es obligatorio."):
            validar_no_vacio("   ", "campo")

    def test_validar_longitud_minima_ok(self):
        assert validar_longitud_minima("12345", 4, "contrasena") is None

    def test_validar_longitud_minima_exacta(self):
        assert validar_longitud_minima("1234", 4, "contrasena") is None

    def test_validar_longitud_minima_falla(self):
        with pytest.raises(ValueError, match="La contrasena debe tener al menos 4 caracteres."):
            validar_longitud_minima("123", 4, "contrasena")

    def test_validar_no_negativo_ok(self):
        assert validar_no_negativo(0, "precio") is None
        assert validar_no_negativo(Decimal("0.00"), "precio") is None
        assert validar_no_negativo(5, "stock") is None

    def test_validar_no_negativo_falla(self):
        with pytest.raises(ValueError, match="El precio no puede ser negativo."):
            validar_no_negativo(-1, "precio")
        with pytest.raises(ValueError, match="El precio no puede ser negativo."):
            validar_no_negativo(Decimal("-0.01"), "precio")

    def test_validar_positivo_ok(self):
        assert validar_positivo(1, "cantidad") is None
        assert validar_positivo(Decimal("0.01"), "cantidad") is None

    def test_validar_positivo_cero(self):
        with pytest.raises(ValueError, match="La cantidad debe ser mayor a cero."):
            validar_positivo(0, "cantidad")

    def test_validar_positivo_negativo(self):
        with pytest.raises(ValueError, match="La cantidad debe ser mayor a cero."):
            validar_positivo(-5, "cantidad")

    def test_validar_existe_ok(self):
        assert validar_existe("algo", "Producto") is None

    def test_validar_existe_none(self):
        with pytest.raises(ValueError, match="Producto no existe."):
            validar_existe(None, "Producto")

    def test_validar_pagos_cubren_total_ok(self):
        assert validar_pagos_cubren_total(Decimal("100"), Decimal("100")) is None
        assert validar_pagos_cubren_total(Decimal("150"), Decimal("100")) is None

    def test_validar_pagos_cubren_total_insuficiente(self):
        with pytest.raises(ValueError, match="La suma de los metodos de pago"):
            validar_pagos_cubren_total(Decimal("50"), Decimal("100"))
