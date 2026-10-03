"""Pruebas para core/rentabilidad.py — reglas de COGS, utilidad y margen

Modulo PURO (sin BD ni Qt): los calculos se prueban con instancias de
``Producto`` construidas en memoria.
"""

from decimal import Decimal

import pytest

from sistema_financiero.core.rentabilidad import (
    TEXTO_SIN_MARGEN,
    UMBRAL_COSTO_SOSPECHOSO,
    costo_no_confiable,
    formatear_margen,
    margen_ganancia,
    productos_con_costo_no_confiable,
    rentabilidad_calculada,
    utilidad_bruta,
)
from sistema_financiero.models import Producto

pytestmark = pytest.mark.unitarias


# Construye un Producto de prueba con el costo y el precio de venta indicados.
def _producto(
    precio_compra: Decimal | None = None, precio_venta_bs: Decimal | None = None
) -> Producto:
    producto = Producto(nombre_producto="PRODUCTO PRUEBA")
    if precio_compra is not None:
        producto.precio_compra = precio_compra
    if precio_venta_bs is not None:
        producto.precio_venta_bs = precio_venta_bs
    return producto


# Atajo: costo_no_confiable sobre un producto de prueba.
def _no_confiable(costo: str, precio_venta: str) -> bool:
    return costo_no_confiable(
        _producto(precio_compra=Decimal(costo), precio_venta_bs=Decimal(precio_venta)),
    )


# Grupo de pruebas: deteccion de costos no confiables.
class TestCostoNoConfiable:
    def test_sin_costo_es_no_confiable(self) -> None:
        assert _no_confiable("0.00", "100.00") is True

    def test_costo_negativo_es_no_confiable(self) -> None:
        assert _no_confiable("-5.00", "100.00") is True

    def test_costo_igual_al_precio_es_no_confiable(self) -> None:
        assert _no_confiable("100.00", "100.00") is True

    def test_costo_mayor_al_precio_es_no_confiable(self) -> None:
        assert _no_confiable("120.00", "100.00") is True

    def test_costo_menos_del_uno_porciento_es_no_confiable(self) -> None:
        costo = Decimal("100.00") * UMBRAL_COSTO_SOSPECHOSO / Decimal("100")
        assert costo < Decimal("1.00")
        assert (
            costo_no_confiable(
                _producto(precio_compra=costo, precio_venta_bs=Decimal("100.00")),
            )
            is True
        )

    def test_costo_normal_es_confiable(self) -> None:
        assert _no_confiable("70.00", "100.00") is False

    def test_sin_precio_de_venta_no_marca(self) -> None:
        assert _no_confiable("70.00", "0.00") is False


# Grupo de pruebas: calculo de la utilidad bruta.
class TestUtilidadBruta:
    def test_resta_simple(self) -> None:
        assert utilidad_bruta(Decimal("100.00"), Decimal("60.00")) == Decimal("40.00")

    def test_redondea_a_centimos(self) -> None:
        assert utilidad_bruta(Decimal("100.00"), Decimal("60.005")) == Decimal("40.00")

    def test_redondeo_half_up(self) -> None:
        assert utilidad_bruta(Decimal("100.00"), Decimal("70.005")) == Decimal("30.00")

    def test_utilidad_negativa(self) -> None:
        assert utilidad_bruta(Decimal("50.00"), Decimal("70.50")) == Decimal("-20.50")


# Grupo de pruebas: calculo del margen de ganancia.
class TestMargenGanancia:
    def test_margen_normal(self) -> None:
        assert margen_ganancia(Decimal("100.00"), Decimal("30.00")) == Decimal("30.00")

    def test_margen_con_tercios(self) -> None:
        assert margen_ganancia(Decimal("300.00"), Decimal("100.00")) == Decimal("33.33")

    def test_sin_ingresos_devuelve_none(self) -> None:
        assert margen_ganancia(Decimal("0.00"), Decimal("0.00")) is None

    def test_ingresos_negativos_devuelven_none(self) -> None:
        assert margen_ganancia(Decimal("-10.00"), Decimal("0.00")) is None

    def test_tolerancia_a_no_decimal(self) -> None:
        assert margen_ganancia(100, 30) == Decimal("30.00")


# Grupo de pruebas: formato del margen para la interfaz.
class TestFormatearMargen:
    def test_none_muestra_placeholder(self) -> None:
        assert formatear_margen(None) == TEXTO_SIN_MARGEN

    def test_valor_muestra_porcentaje_con_1_decimal(self) -> None:
        assert formatear_margen(Decimal("23.30")) == "23.3 %"

    def test_cero_muestra_cero(self) -> None:
        assert formatear_margen(Decimal("0.00")) == "0.0 %"

    def test_negativo_con_signo(self) -> None:
        assert formatear_margen(Decimal("-5.00")) == "-5.0 %"

    def test_tolerancia_a_no_decimal(self) -> None:
        assert formatear_margen(100) == "100.0 %"


# Grupo de pruebas: distingue reporte calculado de reporte legado.
class TestRentabilidadCalculada:
    def test_sin_ingresos_es_calculada(self) -> None:
        assert rentabilidad_calculada(Decimal("0.00"), None) is True

    def test_sin_datos_es_calculada(self) -> None:
        assert rentabilidad_calculada(None, None) is True

    def test_con_ingresos_y_sin_margen_no_es_calculada(self) -> None:
        assert rentabilidad_calculada(Decimal("100.00"), None) is False

    def test_con_ingresos_y_margen_es_calculada(self) -> None:
        assert rentabilidad_calculada(Decimal("100.00"), Decimal("30.00")) is True


# Grupo de pruebas: listado de productos con costo no confiable.
class TestProductosConCostoNoConfiable:
    def test_filtra_los_no_confiables(self) -> None:
        bueno = _producto(precio_compra=Decimal("70.00"), precio_venta_bs=Decimal("100.00"))
        sin_costo = _producto(precio_compra=Decimal("0.00"), precio_venta_bs=Decimal("100.00"))
        a_perdida = _producto(precio_compra=Decimal("150.00"), precio_venta_bs=Decimal("100.00"))
        resultado = productos_con_costo_no_confiable([bueno, sin_costo, a_perdida])
        assert resultado == [sin_costo, a_perdida]

    def test_lista_vacia(self) -> None:
        assert productos_con_costo_no_confiable([]) == []
