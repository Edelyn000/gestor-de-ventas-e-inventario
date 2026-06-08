# ============================================================
# ARCHIVO: tests/test_venta_controller.py
# Pruebas para el controlador de ventas (VentaController).
#
# ¿QUE ES VentaController?
#   Es el controlador que ORQUESTA una venta completa:
#   1. Crea la venta con sus productos (detalles).
#   2. Valida stock suficiente (via InventarioService).
#   3. Calcula totales en VES y USD.
#   4. Descuenta del inventario.
#   5. Anula ventas (devuelve el stock).
#
# ¿POR QUE SE LLAMA "CONTROLADOR" Y NO "SERVICIO"?
#   - Un servicio hace UNA cosa bien (ej: solo inventario).
#   - Un controlador ORQUESTA varios servicios (inventario + tasas).
#   - VentaController usa InventarioService y TasaCambioService.
#
# ¿QUE VERIFICAN ESTOS TESTS?
#   - Creacion de ventas con 1 o mas productos.
#   - Calculo correcto de totales (subtotal, total_bs, total_usd).
#   - Validacion de: productos vacio, cantidad 0, stock insuficiente.
#   - Metodos de pago: validar que cubran el total.
#   - Anulacion de ventas (cambio de estado + devolucion de stock).
#   - Busqueda por ID, factura, y rango de fechas.
# ============================================================

from datetime import datetime
from decimal import Decimal

import pytest

from sistema_financiero.core.tasa_cambio_service import TasaCambioService
from sistema_financiero.core.venta_controller import VentaController

# Producto: modelo ORM para crear productos de prueba.
from sistema_financiero.models import Producto


# ============================================================
# FUNCION AUXILIAR: _crear_producto
# Crea un producto y lo retorna con datos minimos para vender.
# ============================================================
def _crear_producto(session, nombre="PROD VENTA", stock=20, precio_bs=Decimal("10.00")) -> Producto:
    """Crea un producto de prueba en la BD."""
    producto = Producto(
        nombre_producto=nombre,
        precio_venta_bs=precio_bs,
        precio_venta_usd=Decimal("2.00"),
        stock_actual=stock,
        stock_minimo=5,
    )
    session.add(producto)
    session.commit()
    session.refresh(producto)
    return producto


# ============================================================
# FUNCION AUXILIAR: _crear_tasa
# Crea una tasa de cambio activa para la fecha de hoy.
# ============================================================
def _crear_tasa(session, tasa_valor=Decimal("50.00")) -> None:
    """Registra una tasa de cambio activa para poder calcular USD."""
    ts = TasaCambioService()
    ts.registrar(
        fecha=datetime.now().date(),
        tasa_venta=tasa_valor,
        tasa_compra=tasa_valor,
        activa=True,
        db_session=session,
    )


# ============================================================
# TEST: test_crear_venta_exitoso
# ¿QUE PRUEBA? Crear una venta basica con 1 producto.
# ============================================================
def test_crear_venta_exitoso(session) -> None:
    """Crea un producto, una tasa, y una venta. Verifica totales y factura."""
    # ARRANGE: crear datos necesarios.
    producto = _crear_producto(session, precio_bs=Decimal("25.00"))
    _crear_tasa(session)
    vc = VentaController()

    # ACT: crear venta de 3 unidades del producto.
    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 3}],  # type: ignore[arg-type]
        metodo_pago={"efectivo_bs": Decimal("75.00")},
        db_session=session,
    )

    # ASSERT: verificar la venta creada.
    assert venta is not None
    assert venta.idventa is not None
    assert venta.numero_factura is not None
    assert venta.numero_factura.startswith("FAC-")
    assert venta.estado == "COMPLETADA"
    # total_bs = 25.00 * 3 = 75.00
    assert venta.total_bs == Decimal("75.00")
    # total_usd = 75.00 / 50.00 = 1.50
    assert venta.total_usd == Decimal("1.50")

    # Verificar que el stock se haya descontado.
    session.refresh(producto)
    assert producto.stock_actual == 17  # 20 - 3


# ============================================================
# TEST: test_crear_venta_detalles
# ¿QUE PRUEBA? Que los detalles (VentaDetalle) se guarden.
# ============================================================
def test_crear_venta_detalles(session) -> None:
    """Verificar que los detalles de la venta se creen correctamente."""
    producto = _crear_producto(session, precio_bs=Decimal("10.00"))
    _crear_tasa(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 2}],  # type: ignore[arg-type]
        metodo_pago={"efectivo_bs": Decimal("20.00")},
        db_session=session,
    )

    # Obtener y verificar los detalles.
    detalles = vc.obtener_detalles(venta.idventa, db_session=session)  # type: ignore[arg-type]
    assert len(detalles) == 1
    detalle = detalles[0]
    assert detalle.producto_id == producto.idproducto
    assert detalle.cantidad == 2
    assert detalle.precio_unitario_bs == Decimal("10.00")
    assert detalle.subtotal_bs == Decimal("20.00")
    assert detalle.venta_id == venta.idventa


# ============================================================
# TEST: test_crear_venta_sin_productos
# ¿QUE PRUEBA? Que crear() rechace una lista vacia.
# ============================================================
def test_crear_venta_sin_productos(session) -> None:
    vc = VentaController()
    with pytest.raises(ValueError, match="debe tener al menos un producto"):
        vc.crear(productos=[], db_session=session)


# ============================================================
# TEST: test_crear_venta_cantidad_cero
# ¿QUE PRUEBA? Que crear() rechace cantidad <= 0.
# ============================================================
def test_crear_venta_cantidad_cero(session) -> None:
    producto = _crear_producto(session)
    _crear_tasa(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="debe ser mayor a cero"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 0}],  # type: ignore[arg-type]
            db_session=session,
        )


# ============================================================
# TEST: test_crear_venta_stock_insuficiente
# ¿QUE PRUEBA? Que crear() rechace si no hay stock suficiente.
# ============================================================
def test_crear_venta_stock_insuficiente(session) -> None:
    producto = _crear_producto(session, stock=2)
    _crear_tasa(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="Stock insuficiente"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 10}],  # type: ignore[arg-type]
            db_session=session,
        )

    # El stock NO debe haber cambiado.
    session.refresh(producto)
    assert producto.stock_actual == 2


# ============================================================
# TEST: test_crear_venta_pago_insuficiente
# ¿QUE PRUEBA? Que los metodos de pago no cubran el total.
# ============================================================
def test_crear_venta_pago_insuficiente(session) -> None:
    producto = _crear_producto(session, precio_bs=Decimal("100.00"))
    _crear_tasa(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="no cubre el total"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 1}],  # type: ignore[arg-type]
            metodo_pago={"efectivo_bs": Decimal("50.00")},  # Solo paga la mitad
            db_session=session,
        )


# ============================================================
# TEST: test_crear_venta_con_varios_productos
# ¿QUE PRUEBA? Venta con multiples productos.
# ============================================================
def test_crear_venta_con_varios_productos(session) -> None:
    """Crear 2 productos y venderlos juntos en una misma venta."""
    prod1 = _crear_producto(session, nombre="PROD A", precio_bs=Decimal("10.00"))
    prod2 = _crear_producto(session, nombre="PROD B", precio_bs=Decimal("20.00"))
    _crear_tasa(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[
            {"idproducto": prod1.idproducto, "cantidad": 2},  # type: ignore[arg-type]  2 * 10 = 20
            {"idproducto": prod2.idproducto, "cantidad": 3},  # type: ignore[arg-type]  3 * 20 = 60
        ],
        metodo_pago={"efectivo_bs": Decimal("80.00")},
        db_session=session,
    )

    assert venta.total_bs == Decimal("80.00")  # 20 + 60
    detalles = vc.obtener_detalles(venta.idventa, db_session=session)  # type: ignore[arg-type]
    assert len(detalles) == 2


# ============================================================
# TEST: test_anular_venta
# ¿QUE PRUEBA? Anular una venta y verificar que devuelva el stock.
# ============================================================
def test_anular_venta(session) -> None:
    """Anular una venta debe cambiar estado a ANULADA y devolver stock."""
    producto = _crear_producto(session, stock=10)
    _crear_tasa(session)
    vc = VentaController()

    # Crear venta.
    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 3}],  # type: ignore[arg-type]
        metodo_pago={"efectivo_bs": Decimal("30.00")},
        db_session=session,
    )

    session.refresh(producto)
    assert producto.stock_actual == 7  # 10 - 3

    # Anular venta.
    anulada = vc.anular(venta.idventa, db_session=session)  # type: ignore[arg-type]
    assert anulada is not None
    assert anulada.estado == "ANULADA"

    # El stock debe volver a 10.
    session.refresh(producto)
    assert producto.stock_actual == 10


# ============================================================
# TEST: test_anular_venta_inexistente
# ¿QUE PRUEBA? anular() retorna None si la venta no existe.
# ============================================================
def test_anular_venta_inexistente(session) -> None:
    vc = VentaController()
    resultado = vc.anular(9999, db_session=session)
    assert resultado is None


# ============================================================
# TEST: test_anular_venta_ya_anulada
# ¿QUE PRUEBA? No se puede anular dos veces.
# ============================================================
def test_anular_venta_ya_anulada(session) -> None:
    producto = _crear_producto(session)
    _crear_tasa(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],  # type: ignore[arg-type]
        metodo_pago={"efectivo_bs": Decimal("10.00")},
        db_session=session,
    )

    vc.anular(venta.idventa, db_session=session)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="ya esta anulada"):
        vc.anular(venta.idventa, db_session=session)  # type: ignore[arg-type]


# ============================================================
# TEST: test_obtener_por_id
# ============================================================
def test_obtener_por_id(session) -> None:
    producto = _crear_producto(session)
    _crear_tasa(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],  # type: ignore[arg-type]
        metodo_pago={"efectivo_bs": Decimal("10.00")},
        db_session=session,
    )

    encontrada = vc.obtener_por_id(venta.idventa, db_session=session)  # type: ignore[arg-type]
    assert encontrada is not None
    assert encontrada.idventa == venta.idventa


# ============================================================
# TEST: test_obtener_por_id_inexistente
# ============================================================
def test_obtener_por_id_inexistente(session) -> None:
    vc = VentaController()
    resultado = vc.obtener_por_id(9999, db_session=session)
    assert resultado is None


# ============================================================
# TEST: test_buscar_por_factura
# ============================================================
def test_buscar_por_factura(session) -> None:
    producto = _crear_producto(session)
    _crear_tasa(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],  # type: ignore[arg-type]
        metodo_pago={"efectivo_bs": Decimal("10.00")},
        db_session=session,
    )
    assert venta.numero_factura is not None

    # Buscar por el numero de factura.
    encontrada = vc.buscar_por_factura(venta.numero_factura, db_session=session)
    assert encontrada is not None
    assert encontrada.idventa == venta.idventa


# ============================================================
# TEST: test_buscar_por_factura_inexistente
# ============================================================
def test_buscar_por_factura_inexistente(session) -> None:
    vc = VentaController()
    resultado = vc.buscar_por_factura("FAC-99999999-999", db_session=session)
    assert resultado is None


# ============================================================
# TEST: test_historial_por_fecha
# ============================================================
def test_historial_por_fecha(session) -> None:
    producto = _crear_producto(session)
    _crear_tasa(session)
    vc = VentaController()

    vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],  # type: ignore[arg-type]
        metodo_pago={"efectivo_bs": Decimal("10.00")},
        db_session=session,
    )
    vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 2}],  # type: ignore[arg-type]
        metodo_pago={"efectivo_bs": Decimal("20.00")},
        db_session=session,
    )

    hoy = datetime.now()
    desde = datetime(hoy.year, hoy.month, hoy.day, 0, 0, 0)
    hasta = datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59)
    ventas = vc.historial_por_fecha(desde, hasta, db_session=session)
    assert len(ventas) == 2
    assert ventas[0].total_bs == Decimal("20.00")  # La mas reciente primero


# ============================================================
# TEST: test_obtener_detalles_sin_detalles
# ¿QUE PRUEBA? Detalles de una venta inexistente devuelve [].
# ============================================================
def test_obtener_detalles_sin_detalles(session) -> None:
    vc = VentaController()
    detalles = vc.obtener_detalles(9999, db_session=session)
    assert detalles == []
