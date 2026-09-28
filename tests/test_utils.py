"""Pruebas para utils/ — constantes, moneda, validacion y zona horaria."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from sistema_financiero.utils import (
    DECIMAL_CENTIMO,
    DECIMAL_CERO,
    ESTADO_VENTA_ANULADA,
    ESTADO_VENTA_COMPLETADA,
    GRAMOS_POR_KILO,
    LONGITUD_MINIMA_CONTRASENA,
    MAX_GRAMOS_CAPTURA,
    MAX_KILOS_CAPTURA,
    METODO_PAGO_BIO_PAGO,
    METODO_PAGO_EFECTIVO_BS,
    METODO_PAGO_EFECTIVO_USD,
    METODO_PAGO_PAGO_MOVIL,
    METODO_PAGO_TARJETA,
    METODO_PAGO_TRANSFERENCIA,
    METODOS_PAGO,
    MOTIVO_AJUSTE,
    MOTIVO_COMPRA,
    MOTIVO_DEVOLUCION,
    MOTIVO_DEVOLUCION_ANULACION,
    MOTIVO_INVENTARIO_FISICO,
    MOTIVO_MERMA,
    MOTIVO_VENTA,
    PASOS_PESO_RAPIDO,
    PREFIJO_FACTURA,
    RANGO_SPINBOX_MAX,
    SIMBOLO_BS,
    SIMBOLO_USD,
    SUFIJO_BS,
    SUFIJO_USD,
    TIPO_MOVIMIENTO_AJUSTE,
    TIPO_MOVIMIENTO_ENTRADA,
    TIPO_MOVIMIENTO_SALIDA,
    TIPO_VENTA_GRAMOS_LEGADO,
    TIPO_VENTA_PESO,
    TIPO_VENTA_UNIDAD,
    TIPOS_VENTA,
    UNIDADES_MEDIDA,
    UNIDADES_VENTA,
    a_kg,
    a_local,
    a_utc,
    ahora,
    clave_normalizada,
    deducir_tipo_venta,
    descomponer_kg,
    es_medida,
    formatear_bs,
    formatear_bs_sin_sufijo,
    formatear_peso_kg,
    formatear_stock,
    formatear_usd,
    formatear_usd_texto,
    hoy,
    normalizar_nombre_categoria,
    normalizar_unidad,
    parsear_decimal_escrito,
    rango_dia_utc,
    redondear_moneda,
    validar_existe,
    validar_longitud_minima,
    validar_no_negativo,
    validar_no_vacio,
    validar_pagos_cubren_total,
    validar_positivo,
)

pytestmark = pytest.mark.unitarias


class TestConstantes:
    # Prueba que todos los metodos de pago tienen etiqueta.
    def test_metodos_pago_todos_definidos(self) -> None:
        assert METODO_PAGO_EFECTIVO_BS == "efectivo_bs"
        assert METODO_PAGO_EFECTIVO_USD == "efectivo_usd"
        assert METODO_PAGO_TARJETA == "tarjeta"
        assert METODO_PAGO_PAGO_MOVIL == "pago_movil"
        assert METODO_PAGO_BIO_PAGO == "bio_pago"
        assert METODO_PAGO_TRANSFERENCIA == "transferencia"
        assert METODOS_PAGO == [
            "efectivo_bs",
            "efectivo_usd",
            "tarjeta",
            "pago_movil",
            "bio_pago",
            "transferencia",
        ]

    # Prueba los estados de venta definidos.
    def test_estados_venta(self) -> None:
        assert ESTADO_VENTA_COMPLETADA == "COMPLETADA"
        assert ESTADO_VENTA_ANULADA == "ANULADA"

    # Prueba los tipos de movimiento de inventario.
    def test_tipos_movimiento(self) -> None:
        assert TIPO_MOVIMIENTO_ENTRADA == "ENTRADA"
        assert TIPO_MOVIMIENTO_SALIDA == "SALIDA"
        assert TIPO_MOVIMIENTO_AJUSTE == "AJUSTE"

    # Prueba los motivos de movimiento.
    def test_motivos_movimiento(self) -> None:
        assert MOTIVO_COMPRA == "COMPRA"
        assert MOTIVO_VENTA == "VENTA"
        assert MOTIVO_DEVOLUCION == "DEVOLUCION"
        assert MOTIVO_DEVOLUCION_ANULACION == "DEVOLUCION POR ANULACION"
        assert MOTIVO_MERMA == "MERMA"
        assert MOTIVO_AJUSTE == "AJUSTE"
        assert MOTIVO_INVENTARIO_FISICO == "INVENTARIO FISICO"

    # Prueba el prefijo de la factura.
    def test_prefijo_factura(self) -> None:
        assert PREFIJO_FACTURA == "FAC"

    # Prueba la longitud minima de contrasena.
    def test_longitud_minima_contrasena(self) -> None:
        assert LONGITUD_MINIMA_CONTRASENA == 4

    # Prueba el rango maximo del spinbox.
    def test_rango_spinbox(self) -> None:
        assert RANGO_SPINBOX_MAX == 999999


class TestDeducirTipoVenta:
    """deducir_tipo_venta: del formulario de producto se quito el combo
    "Tipo Venta"; el tipo se deduce de la unidad de medida."""

    # Prueba deducir el tipo de venta por unidad.
    @pytest.mark.parametrize(
        ("unidad", "esperado"),
        [
            ("KG", "PESO"),
            ("kgs", "PESO"),
            ("KILO", "PESO"),
            (" KILOGRAMO ", "PESO"),
            ("GR", "PESO"),
            ("GRAMOS", "PESO"),
            ("gr", "PESO"),
            (" UNIDAD ", "UNIDAD"),
            ("", "UNIDAD"),
            ("PAQUETE", "UNIDAD"),
            ("CAJA", "UNIDAD"),
            ("LTS", "UNIDAD"),
            ("litros", "UNIDAD"),
        ],
    )
    def test_deduccion_por_unidad(self, unidad: str, esperado: str) -> None:
        assert deducir_tipo_venta(unidad) == esperado


class TestNormalizarUnidad:
    """normalizar_unidad: lleva una unidad guardada en BD (abreviada,
    plural o en minusculas) a la opcion exacta del combo UNIDADES_VENTA."""

    # Prueba normalizar unidades a las opciones del combo.
    @pytest.mark.parametrize(
        ("unidad", "esperado"),
        [
            ("KG", "KILO"),
            ("KGS", "KILO"),
            ("kilo", "KILO"),
            ("KILOGRAMOS", "KILO"),
            ("GR", "KILO"),
            ("gramos", "KILO"),
            ("UNIDAD", "UNIDAD"),
            ("unidad", "UNIDAD"),
            ("PAQUETE", "UNIDAD"),
            ("CAJA", "UNIDAD"),
            ("LTS", "UNIDAD"),
            ("LT", "UNIDAD"),
            ("litro", "UNIDAD"),
        ],
    )
    def test_normaliza_a_opcion_del_combo(self, unidad: str, esperado: str) -> None:
        assert normalizar_unidad(unidad) == esperado

    # Prueba las unidades de venta y las de medida.
    def test_unidades_venta_y_medida(self) -> None:
        assert UNIDADES_VENTA == ["UNIDAD", "KILO"]
        assert frozenset({"KILO"}) == UNIDADES_MEDIDA

    # Prueba los tipos de venta definidos.
    def test_tipos_venta(self) -> None:
        assert TIPOS_VENTA == ["UNIDAD", "PESO"]
        assert TIPO_VENTA_UNIDAD == "UNIDAD"
        assert TIPO_VENTA_PESO == "PESO"
        assert TIPO_VENTA_GRAMOS_LEGADO == "GRAMOS"

    # Prueba que GRAMOS legacy no es creable.
    def test_legacy_gramos_no_esta_en_los_tipos_creables(self) -> None:
        assert TIPO_VENTA_GRAMOS_LEGADO not in TIPOS_VENTA
        assert TIPO_VENTA_GRAMOS_LEGADO not in UNIDADES_VENTA


class TestCapturaPesoKgYGramos:
    """El POS captura el peso en DOS casillas (Kg y g) y guarda kg."""

    # Prueba las constantes de captura del POS.
    def test_constantes_de_captura(self) -> None:
        assert GRAMOS_POR_KILO == 1000
        assert MAX_GRAMOS_CAPTURA == 999
        assert MAX_KILOS_CAPTURA == 999
        assert (
            Decimal("1.000"),
            Decimal("0.500"),
            Decimal("0.250"),
            Decimal("0.100"),
        ) == PASOS_PESO_RAPIDO

    # Prueba a_kg sumando kilos y gramos.
    @pytest.mark.parametrize(
        ("kg", "g", "esperado"),
        [
            (1, 0, "1.000"),
            (0, 0, "0.000"),
            (0, 1, "0.001"),
            (0, 999, "0.999"),
            (1, 250, "1.250"),
            (2, 500, "2.500"),
            (0.5, 0, "0.500"),
            (0.25, 500, "0.750"),
        ],
    )
    def test_a_kg_suma_kilos_y_gramos(self, kg: str, g: str, esperado: str) -> None:
        assert a_kg(Decimal(kg), Decimal(g)) == Decimal(esperado)

    # Prueba a_kg con valores por defecto.
    def test_a_kg_acepta_el_0_por_defecto(self) -> None:
        assert a_kg(None, None) == Decimal("0.000")
        assert a_kg(Decimal("0"), Decimal("0")) == Decimal("0.000")

    # Prueba que a_kg normaliza gramos mayores a 999.
    def test_a_kg_normaliza_gramos_que_pasan_de_999(self) -> None:
        assert a_kg(Decimal("0"), Decimal("1000")) == Decimal("1.000")
        assert a_kg(Decimal("1"), Decimal("1500")) == Decimal("2.500")

    # Prueba que a_kg nunca devuelve negativo.
    def test_a_kg_nunca_devuelve_negativo(self) -> None:
        assert a_kg(Decimal("-1"), Decimal("0")) == Decimal("0.000")

    # Prueba que descomponer_kg es la inversa de a_kg.
    @pytest.mark.parametrize(
        ("kg", "esperado"),
        [
            ("1.000", (1, 0)),
            ("0.000", (0, 0)),
            ("0.001", (0, 1)),
            ("0.999", (0, 999)),
            ("1.250", (1, 250)),
            ("2.500", (2, 500)),
            ("12.345", (12, 345)),
        ],
    )
    def test_descomponer_kg_es_la_inversa(self, kg: str, esperado: tuple[int, int]) -> None:
        valor = Decimal(kg)
        kilos, gramos = descomponer_kg(valor)
        assert (kilos, gramos) == esperado
        assert a_kg(Decimal(kilos), Decimal(gramos)) == valor

    # Prueba descomponer_kg con cero.
    def test_descomponer_kg_acepta_el_0_por_defecto(self) -> None:
        assert descomponer_kg(None) == (0, 0)
        assert descomponer_kg(Decimal("0")) == (0, 0)

    # Prueba el redondeo al gramo mas cercano.
    def test_descomponer_kg_redondea_al_gramo_mas_cercano(self) -> None:
        assert descomponer_kg(Decimal("1.0004")) == (1, 0)
        assert descomponer_kg(Decimal("1.0005")) == (1, 1)

    # Prueba que trunca gramos que exceden 999.
    def test_descomponer_kg_trunca_un_grano_que_excede_999(self) -> None:
        kilos, gramos = descomponer_kg(Decimal("2.9996"))
        assert gramos <= MAX_GRAMOS_CAPTURA
        assert a_kg(Decimal(kilos), Decimal(gramos)) == Decimal("3.000")

    # Prueba es_medida con PESO y legacy GRAMOS.
    @pytest.mark.parametrize(
        ("tipo", "esperado"),
        [
            (TIPO_VENTA_PESO, True),
            ("peso", True),
            (" PESO ", True),
            (TIPO_VENTA_UNIDAD, False),
            ("", False),
            (None, False),
            (TIPO_VENTA_GRAMOS_LEGADO, True),
            (" gramos ", True),
        ],
    )
    def test_es_medida(self, tipo: str | None, esperado: bool) -> None:
        assert es_medida(tipo) is esperado


class TestNormalizarNombreCategoria:
    """normalizar_nombre_categoria: "Titulo Español" por palabra."""

    # Prueba el titulo espanol al normalizar.
    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("jabón de baño", "Jabón de Baño"),
            ("JABÓN DE BAÑO", "Jabón de Baño"),
            ("aBc Def", "Abc Def"),
            ("HIGIENE", "Higiene"),
            ("crema para manos", "Crema para Manos"),
            ("pan y dulce", "Pan y Dulce"),
            ("aceite de oliva extra virgen", "Aceite de Oliva Extra Virgen"),
            ("jabón  de   baño", "Jabón de Baño"),
            ("jabon de baño", "Jabon de Baño"),
            ("", ""),
        ],
    )
    def test_normaliza_a_titulo_espanol(self, texto: str, esperado: str) -> None:
        assert normalizar_nombre_categoria(texto) == esperado

    # Prueba que None y espacios devuelven vacio.
    def test_none_y_espacios_devuelven_vacio(self) -> None:
        assert normalizar_nombre_categoria(None) == ""
        assert normalizar_nombre_categoria("   ") == ""

    # Prueba que los conectores van en minuscula.
    def test_conectores_no_iniciales_en_minuscula(self) -> None:
        assert normalizar_nombre_categoria("CREMA PARA MANOS") == "Crema para Manos"
        assert normalizar_nombre_categoria("JABÓN DE BAÑO") == "Jabón de Baño"

    # Prueba la clave sin tildes ni mayusculas.
    def test_clave_normalizada_ignora_tildes_y_mayusculas(self) -> None:
        assert clave_normalizada("Jabón de Baño") == "jabon de bano"
        assert clave_normalizada("JABON DE BAÑO") == "jabon de bano"
        assert clave_normalizada("Higiene") == "higiene"
        assert clave_normalizada(None) == ""
        assert clave_normalizada("  ") == ""


class TestMoneda:
    # Prueba el formateo del cero decimal.
    def test_decimal_cero(self) -> None:
        assert Decimal("0.00") == DECIMAL_CERO

    # Prueba el formateo de un centimo.
    def test_decimal_centimo(self) -> None:
        assert Decimal("0.01") == DECIMAL_CENTIMO

    # Prueba los simbolos de las monedas.
    def test_simbolos(self) -> None:
        assert SIMBOLO_BS == "Bs."
        assert SIMBOLO_USD == "$"
        assert SUFIJO_BS == " Bs."
        assert SUFIJO_USD == " $"

    # Prueba formatear_bs con un valor.
    @pytest.mark.parametrize(
        ("valor", "decimales", "miles", "esperado"),
        [
            (Decimal("1234.50"), 2, True, "1.234,50 Bs."),
            (Decimal("0.00"), 2, True, "0,00 Bs."),
            (Decimal("1000"), 2, False, "1000,00 Bs."),
            (Decimal("99.9999"), 3, True, "100,000 Bs."),
        ],
    )
    def test_formatear_bs(self, valor: Decimal, decimales: int, miles: bool, esperado: str) -> None:
        assert formatear_bs(valor, decimales, miles) == esperado

    # Prueba formatear_bs sin sufijo.
    def test_formatear_bs_por_defecto(self) -> None:
        assert formatear_bs(Decimal("1500.50")) == "1.500,50 Bs."

    # El ticket del POS usa el numero pelado: la columna es de 100px.
    def test_formatear_bs_sin_sufijo(self) -> None:
        """El ticket del POS usa el numero pelado: la columna es de 100px."""
        assert formatear_bs_sin_sufijo(Decimal("1500.50")) == "1.500,50"
        assert formatear_bs_sin_sufijo(Decimal("60.00")) == "60,00"
        assert formatear_bs_sin_sufijo(Decimal("1234.56")) == "1.234,56"
        assert formatear_bs_sin_sufijo(Decimal("0.00")) == "0,00"
        assert formatear_bs_sin_sufijo(Decimal("1000"), 2, False) == "1000,00"
        assert formatear_bs_sin_sufijo(Decimal("99.9999"), 3, True) == "100,000"
        assert "Bs." not in formatear_bs_sin_sufijo(Decimal("9.999"))

    # Prueba formatear_usd con un valor.
    def test_formatear_usd(self) -> None:
        assert formatear_usd(Decimal("50.00")) == "50.00 $"
        assert formatear_usd(Decimal("1234.56")) == "1,234.56 $"
        assert formatear_usd(Decimal("0.00"), miles=False) == "0.00 $"

    # Prueba formatear_usd con texto.
    def test_formatear_usd_texto(self) -> None:
        assert formatear_usd_texto(Decimal("50.00")) == "50.00 USD"
        assert formatear_usd_texto(Decimal("1234.56")) == "1,234.56 USD"

    # Prueba formatear_stock con enteros y decimales.
    def test_formatear_stock(self) -> None:
        assert formatear_stock(Decimal("5")) == "5"
        assert formatear_stock(Decimal("0")) == "0"
        assert formatear_stock(Decimal("10000")) == "10.000"
        assert formatear_stock(Decimal("5.000")) == "5"
        assert formatear_stock(Decimal("0.5")) == "0,5"
        assert formatear_stock(Decimal("1.25")) == "1,25"
        assert formatear_stock(Decimal("1.5")) == "1,5"
        assert formatear_stock(Decimal("1234.5")) == "1.234,5"
        assert formatear_stock(Decimal("999999.99")) == "999.999,99"

    # Prueba redondear_moneda a dos decimales.
    def test_redondear_moneda(self) -> None:
        assert redondear_moneda(Decimal("10.003")) == Decimal("10.00")
        assert redondear_moneda(Decimal("10.006")) == Decimal("10.01")
        assert redondear_moneda(Decimal("0.999")) == Decimal("1.00")

    # Prueba redondear_moneda tras una division.
    def test_redondear_moneda_con_division(self) -> None:
        resultado = redondear_moneda(Decimal("10.00") / Decimal("3"))
        assert resultado == Decimal("3.33")


class TestValidacion:
    # Prueba validar_no_vacio con valor.
    def test_validar_no_vacio_ok(self) -> None:
        assert validar_no_vacio("hola", "campo") is None

    # Prueba validar_no_vacio con None.
    def test_validar_no_vacio_none(self) -> None:
        with pytest.raises(ValueError, match="El campo es obligatorio."):
            validar_no_vacio(None, "campo")

    # Prueba validar_no_vacio con texto vacio.
    def test_validar_no_vacio_vacio(self) -> None:
        with pytest.raises(ValueError, match="El nombre es obligatorio."):
            validar_no_vacio("", "nombre")

    # Prueba validar_no_vacio con solo espacios.
    def test_validar_no_vacio_espacios(self) -> None:
        with pytest.raises(ValueError, match="El campo es obligatorio."):
            validar_no_vacio("   ", "campo")

    # Prueba validar_longitud_minima con longitud valida.
    def test_validar_longitud_minima_ok(self) -> None:
        assert validar_longitud_minima("12345", 4, "contrasena") is None

    # Prueba validar_longitud_minima en el limite exacto.
    def test_validar_longitud_minima_exacta(self) -> None:
        assert validar_longitud_minima("1234", 4, "contrasena") is None

    # Prueba validar_longitud_minima con texto corto.
    def test_validar_longitud_minima_falla(self) -> None:
        with pytest.raises(ValueError, match="La contrasena debe tener al menos 4 caracteres."):
            validar_longitud_minima("123", 4, "contrasena")

    # Prueba validar_no_negativo con positivo.
    def test_validar_no_negativo_ok(self) -> None:
        assert validar_no_negativo(0, "precio") is None
        assert validar_no_negativo(Decimal("0.00"), "precio") is None
        assert validar_no_negativo(5, "stock") is None

    # Prueba validar_no_negativo con negativo.
    def test_validar_no_negativo_falla(self) -> None:
        with pytest.raises(ValueError, match="El precio no puede ser negativo."):
            validar_no_negativo(-1, "precio")
        with pytest.raises(ValueError, match="El precio no puede ser negativo."):
            validar_no_negativo(Decimal("-0.01"), "precio")

    # Prueba validar_positivo con positivo.
    def test_validar_positivo_ok(self) -> None:
        assert validar_positivo(1, "cantidad") is None
        assert validar_positivo(Decimal("0.01"), "cantidad") is None

    # Prueba validar_positivo con cero.
    def test_validar_positivo_cero(self) -> None:
        with pytest.raises(ValueError, match="La cantidad debe ser mayor a cero."):
            validar_positivo(0, "cantidad")

    # Prueba validar_positivo con negativo.
    def test_validar_positivo_negativo(self) -> None:
        with pytest.raises(ValueError, match="La cantidad debe ser mayor a cero."):
            validar_positivo(-5, "cantidad")

    # Prueba validar_existe con un valor presente.
    def test_validar_existe_ok(self) -> None:
        assert validar_existe("algo", "Producto") is None

    # Prueba validar_existe con None.
    def test_validar_existe_none(self) -> None:
        with pytest.raises(ValueError, match="Producto no existe."):
            validar_existe(None, "Producto")

    # Prueba que los pagos cubren el total.
    def test_validar_pagos_cubren_total_ok(self) -> None:
        assert validar_pagos_cubren_total(Decimal("100"), Decimal("100")) is None
        assert validar_pagos_cubren_total(Decimal("150"), Decimal("100")) is None

    # Prueba que rechaza pagos insuficientes.
    def test_validar_pagos_cubren_total_insuficiente(self) -> None:
        with pytest.raises(ValueError, match="La suma de los metodos de pago"):
            validar_pagos_cubren_total(Decimal("50"), Decimal("100"))


class TestZonaHorariaVET:
    # Prueba convertir UTC a hora local de Venezuela.
    def test_a_local_convierte_utc_a_vet(self) -> None:
        assert a_local(datetime(2026, 1, 2, 0, 30)) == datetime(2026, 1, 1, 20, 30)

    # Prueba convertir hora local de Venezuela a UTC.
    def test_a_utc_convierte_vet_a_utc(self) -> None:
        assert a_utc(datetime(2026, 1, 1, 20, 30)) == datetime(2026, 1, 2, 0, 30)

    # Prueba que convertir ida y vuelta conserva el instante.
    def test_ida_y_vuelta_conserva_el_instante(self) -> None:
        for utc in [
            datetime(2026, 1, 2, 0, 30),
            datetime(2026, 1, 2, 12, 0),
            datetime(2026, 1, 2, 23, 59, 59),
        ]:
            assert a_utc(a_local(utc)) == utc

    # Prueba que el rango del dia cubre la noche local.
    def test_rango_dia_utc_cubre_la_noche_local(self) -> None:
        desde, hasta = rango_dia_utc(date(2026, 1, 1))
        assert desde == datetime(2026, 1, 1, 4, 0, 0)
        assert hasta == datetime(2026, 1, 2, 3, 59, 59)
        assert desde <= datetime(2026, 1, 2, 0, 30, 0) <= hasta

    # Prueba que hoy es el dia local.
    def test_hoy_es_el_dia_local_no_el_utc(self) -> None:
        assert hoy() == a_local(ahora()).date()


class TestFormatearPeso:
    # Prueba formatear_peso_kg con kilos enteros.
    def test_kilos_enteros(self) -> None:
        assert formatear_peso_kg(Decimal("1.000")) == "1 kg"
        assert formatear_peso_kg(Decimal("2.000")) == "2 kg"

    # Prueba formatear_peso_kg con solo gramos.
    def test_gramos_sin_kilos(self) -> None:
        assert formatear_peso_kg(Decimal("0.500")) == "500 g"
        assert formatear_peso_kg(Decimal("0.250")) == "250 g"

    # Prueba formatear_peso_kg con kilos y gramos.
    def test_kilos_con_gramos(self) -> None:
        assert formatear_peso_kg(Decimal("2.500")) == "2 kg y 500 g"
        assert formatear_peso_kg(Decimal("1.005")) == "1 kg y 5 g"

    # Prueba el redondeo a tres decimales.
    def test_redondea_a_3_decimales(self) -> None:
        assert formatear_peso_kg(Decimal("0.1234")) == "123 g"

    # Prueba que el cero muestra un guion.
    def test_cero_muestra_guion(self) -> None:
        assert formatear_peso_kg(Decimal("0.000")) == "—"

    # Prueba que None muestra un guion largo.
    def test_none_muestra_guion_largo(self) -> None:
        assert formatear_peso_kg(None) == "−"

    # Prueba formatear_peso_kg con int y float.
    def test_acepta_int_y_float(self) -> None:
        assert formatear_peso_kg(2) == "2 kg"
        assert formatear_peso_kg(0.5) == "500 g"


class TestParsearDecimalEscrito:
    # Prueba parsear_decimal_escrito con punto decimal.
    def test_punto_decimal_pos(self) -> None:
        assert parsear_decimal_escrito("860.50") == Decimal("860.50")
        assert parsear_decimal_escrito("860.5") == Decimal("860.5")

    # Prueba parsear_decimal_escrito con coma decimal.
    def test_coma_decimal_pos(self) -> None:
        assert parsear_decimal_escrito("860,50") == Decimal("860.50")

    # Prueba parsear_decimal_escrito con solo entero.
    def test_solo_entero(self) -> None:
        assert parsear_decimal_escrito("860") == Decimal("860")
        assert parsear_decimal_escrito("0.01") == Decimal("0.01")

    # Prueba que el ultimo separador es el decimal.
    def test_ambos_separadores_ultimo_es_decimal(self) -> None:
        assert parsear_decimal_escrito("1.000,50") == Decimal("1000.50")
        assert parsear_decimal_escrito("1,000.50") == Decimal("1000.50")

    # Prueba que ignora los espacios adyacentes.
    def test_espacios_adyacentes_se_ignoran(self) -> None:
        assert parsear_decimal_escrito("  860.50  ") == Decimal("860.50")

    # Prueba que texto vacio o invalido devuelve None.
    def test_texto_vacio_o_invalido_devuelve_none(self) -> None:
        assert parsear_decimal_escrito("") is None
        assert parsear_decimal_escrito("   ") is None
        assert parsear_decimal_escrito("abc") is None
        assert parsear_decimal_escrito("1.2.3") is None
        assert parsear_decimal_escrito("1,2,3") is None
        assert parsear_decimal_escrito("123e") is None

    # Prueba que el punto solitario se lee como decimal.
    def test_punto_sin_coma_se_lee_como_decimal(self) -> None:
        assert parsear_decimal_escrito("1.000") == Decimal("1")

    # Prueba que NaN e infinito devuelven None.
    def test_valores_no_finitos_devuelven_none(self) -> None:
        assert parsear_decimal_escrito("NaN") is None
        assert parsear_decimal_escrito("Infinity") is None

