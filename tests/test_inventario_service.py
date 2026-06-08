# ============================================================
# ARCHIVO: tests/test_inventario_service.py
# Pruebas para el servicio de inventario (InventarioService).
#
# ¿QUE ES InventarioService?
#   Es el servicio que maneja el control de stock. Permite:
#   - registrar_entrada()  → Suma stock (compra, devolucion).
#   - registrar_salida()   → Resta stock (venta, merma).
#   - registrar_ajuste()   → Ajusta al stock fisico real.
#   - historial_por_producto() → Movimientos de un producto.
#   - stock_disponible()   → Verifica si hay stock suficiente.
#   - movimientos_recientes() → Ultimos movimientos globales.
#
# ¿QUE VERIFICAN ESTOS TESTS?
#   - Que las entradas/salidas/ajustes actualicen el stock.
#   - Que se registren movimientos de auditoria correctamente.
#   - Que se validen cantidades negativas, stock insuficiente,
#     productos inexistentes, etc.
# ============================================================

# Decimal: necesario para crear precios con precision exacta.
from decimal import Decimal

# pytest: para usar pytest.raises y fixtures.
import pytest

# InventarioService: el servicio que vamos a probar.
from sistema_financiero.core.inventario_service import InventarioService

# Producto: el modelo ORM para crear productos de prueba.
from sistema_financiero.models import Producto


# ============================================================
# FUNCION AUXILIAR: _crear_producto
# ¿POR QUE UNA FUNCION AUXILIAR?
#   Casi todos los tests necesitan un producto existente en
#   la BD para probar el inventario. En lugar de repetir el
#   codigo de creacion en cada test, lo encapsulamos en una
#   funcion. Esto hace los tests mas cortos y legibles.
# ============================================================
def _crear_producto(session, nombre="PROD TEST", stock=50) -> Producto:
    """Crea un producto de prueba y lo retorna."""
    producto = Producto(
        nombre_producto=nombre,
        precio_venta_bs=Decimal("10.00"),
        precio_venta_usd=Decimal("2.00"),
        stock_actual=stock,
        stock_minimo=5,
    )
    session.add(producto)
    session.commit()
    session.refresh(producto)
    return producto


# ============================================================
# TEST: test_registrar_entrada_exitoso
# ¿QUE PRUEBA? Que registrar_entrada() sume stock correctamente.
# ============================================================
def test_registrar_entrada_exitoso(session) -> None:
    """Crea un producto, registra una entrada y verifica que el
    stock aumente y se cree un movimiento de auditoria."""
    # ARRANGE: crear producto con stock inicial 50.
    producto = _crear_producto(session)
    servicio = InventarioService()
    cantidad_entrada = 10

    # ACT: registrar entrada de 10 unidades.
    movimiento = servicio.registrar_entrada(
        producto_id=producto.idproducto,  # type: ignore[arg-type]
        cantidad=cantidad_entrada,
        motivo="COMPRA",
        db_session=session,
    )

    # ASSERT: verificar el movimiento de auditoria.
    assert movimiento is not None
    assert movimiento.producto_id == producto.idproducto
    assert movimiento.tipo == "ENTRADA"
    assert movimiento.motivo == "COMPRA"
    assert movimiento.cantidad == cantidad_entrada
    assert movimiento.stock_anterior == 50
    assert movimiento.stock_nuevo == 60  # 50 + 10

    # Verificar que el stock del producto se actualizo en la BD.
    session.refresh(producto)
    assert producto.stock_actual == 60


# ============================================================
# TEST: test_registrar_entrada_cantidad_invalida
# ¿QUE PRUEBA? Que registrar_entrada() rechace cantidad <= 0.
# ============================================================
def test_registrar_entrada_cantidad_invalida(session) -> None:
    """Intentar entrada con cantidad 0 o negativa debe lanzar ValueError."""
    producto = _crear_producto(session)
    servicio = InventarioService()

    with pytest.raises(ValueError, match="debe ser mayor a cero"):
        servicio.registrar_entrada(
            producto_id=producto.idproducto,  # type: ignore[arg-type]
            cantidad=0,
            motivo="COMPRA",
            db_session=session,
        )

    with pytest.raises(ValueError, match="debe ser mayor a cero"):
        servicio.registrar_entrada(
            producto_id=producto.idproducto,  # type: ignore[arg-type]
            cantidad=-5,
            motivo="COMPRA",
            db_session=session,
        )


# ============================================================
# TEST: test_registrar_entrada_producto_inexistente
# ¿QUE PRUEBA? Que registrar_entrada() rechace un ID inexistente.
# ============================================================
def test_registrar_entrada_producto_inexistente(session) -> None:
    """Intentar entrada con producto que no existe debe lanzar ValueError."""
    servicio = InventarioService()
    with pytest.raises(ValueError, match="no existe"):
        servicio.registrar_entrada(
            producto_id=9999, cantidad=5, motivo="COMPRA", db_session=session)


# ============================================================
# TEST: test_registrar_salida_exitoso
# ¿QUE PRUEBA? Que registrar_salida() reste stock correctamente.
# ============================================================
def test_registrar_salida_exitoso(session) -> None:
    """Registra una salida y verifica que el stock disminuya."""
    producto = _crear_producto(session, stock=30)
    servicio = InventarioService()
    cantidad_salida = 5

    movimiento = servicio.registrar_salida(
        producto_id=producto.idproducto,  # type: ignore[arg-type]
        cantidad=cantidad_salida,
        motivo="VENTA",
        db_session=session,
    )

    # Verificar movimiento.
    assert movimiento.tipo == "SALIDA"
    assert movimiento.motivo == "VENTA"
    assert movimiento.stock_anterior == 30
    assert movimiento.stock_nuevo == 25

    session.refresh(producto)
    assert producto.stock_actual == 25


# ============================================================
# TEST: test_registrar_salida_stock_insuficiente
# ¿QUE PRUEBA? Que registrar_salida() rechace si no hay stock.
# ============================================================
def test_registrar_salida_stock_insuficiente(session) -> None:
    """Intentar sacar mas stock del disponible debe lanzar ValueError."""
    producto = _crear_producto(session, stock=3)
    servicio = InventarioService()

    with pytest.raises(ValueError, match="Stock insuficiente"):
        servicio.registrar_salida(
            producto_id=producto.idproducto,  # type: ignore[arg-type]
            cantidad=10,
            motivo="VENTA",
            db_session=session,
        )

    # El stock NO debe haber cambiado.
    session.refresh(producto)
    assert producto.stock_actual == 3


# ============================================================
# TEST: test_registrar_salida_cantidad_invalida
# ¿QUE PRUEBA? Que registrar_salida() rechace cantidad <= 0.
# ============================================================
def test_registrar_salida_cantidad_invalida(session) -> None:
    producto = _crear_producto(session)
    servicio = InventarioService()

    with pytest.raises(ValueError, match="debe ser mayor a cero"):
        servicio.registrar_salida(
            producto_id=producto.idproducto,  # type: ignore[arg-type]
            cantidad=0,
            motivo="MERMA",
            db_session=session,
        )


# ============================================================
# TEST: test_registrar_ajuste_exitoso_aumento
# ¿QUE PRUEBA? Que registrar_ajuste() aumente el stock.
# ============================================================
def test_registrar_ajuste_exitoso_aumento(session) -> None:
    """Ajuste: stock fisico (60) > stock actual (50) → debe aumentar."""
    producto = _crear_producto(session, stock=50)
    servicio = InventarioService()

    movimiento = servicio.registrar_ajuste(
        producto_id=producto.idproducto,  # type: ignore[arg-type]
        stock_fisico=60,
        motivo="INVENTARIO FISICO",
        db_session=session,
    )

    assert movimiento.tipo == "AJUSTE"
    assert movimiento.stock_anterior == 50
    assert movimiento.stock_nuevo == 60
    assert movimiento.cantidad == 10  # Diferencia absoluta.

    session.refresh(producto)
    assert producto.stock_actual == 60


# ============================================================
# TEST: test_registrar_ajuste_exitoso_disminucion
# ¿QUE PRUEBA? Que registrar_ajuste() disminuya el stock.
# ============================================================
def test_registrar_ajuste_exitoso_disminucion(session) -> None:
    """Ajuste: stock fisico (30) < stock actual (50) → debe disminuir."""
    producto = _crear_producto(session, stock=50)
    servicio = InventarioService()

    movimiento = servicio.registrar_ajuste(
        producto_id=producto.idproducto,  # type: ignore[arg-type]
        stock_fisico=30,
        db_session=session,
    )

    assert movimiento.stock_anterior == 50
    assert movimiento.stock_nuevo == 30

    session.refresh(producto)
    assert producto.stock_actual == 30


# ============================================================
# TEST: test_registrar_ajuste_sin_cambio
# ¿QUE PRUEBA? Que registrar_ajuste() rechace si stock_fisico == stock_actual.
# ============================================================
def test_registrar_ajuste_sin_cambio(session) -> None:
    """Si el stock fisico es igual al actual, debe lanzar ValueError."""
    producto = _crear_producto(session, stock=50)
    servicio = InventarioService()

    with pytest.raises(ValueError, match="No hay nada que ajustar"):
        servicio.registrar_ajuste(
            producto_id=producto.idproducto,  # type: ignore[arg-type]
            stock_fisico=50,
            db_session=session,
        )


# ============================================================
# TEST: test_registrar_ajuste_stock_negativo
# ¿QUE PRUEBA? Que registrar_ajuste() rechace stock_fisico < 0.
# ============================================================
def test_registrar_ajuste_stock_negativo(session) -> None:
    producto = _crear_producto(session)
    servicio = InventarioService()

    with pytest.raises(ValueError, match="no puede ser negativo"):
        servicio.registrar_ajuste(
            producto_id=producto.idproducto,  # type: ignore[arg-type]
            stock_fisico=-1,
            db_session=session,
        )


# ============================================================
# TEST: test_historial_por_producto
# ¿QUE PRUEBA? Que historial_por_producto() devuelva los movimientos.
# ============================================================
def test_historial_por_producto(session) -> None:
    """Registrar varios movimientos y verificar que el historial los contenga."""
    producto = _crear_producto(session, stock=100)
    servicio = InventarioService()

    # Registrar 3 movimientos.
    servicio.registrar_entrada(
        producto_id=producto.idproducto, cantidad=10, motivo="COMPRA", db_session=session  # type: ignore[arg-type]
    )
    servicio.registrar_salida(
        producto_id=producto.idproducto, cantidad=5, motivo="VENTA", db_session=session  # type: ignore[arg-type]
    )
    servicio.registrar_ajuste(
        producto_id=producto.idproducto, stock_fisico=110, db_session=session  # type: ignore[arg-type]
    )

    historial = servicio.historial_por_producto(
        producto_id=producto.idproducto, db_session=session  # type: ignore[arg-type]
    )

    # Debe haber 3 movimientos (el mas reciente primero).
    assert len(historial) == 3

    # Verificar que esten ordenados (el ultimo registro debe ser el primero).
    assert historial[0].tipo == "AJUSTE"
    assert historial[1].tipo == "SALIDA"
    assert historial[2].tipo == "ENTRADA"

    # Verificar que todos pertenezcan al producto correcto.
    for mov in historial:
        assert mov.producto_id == producto.idproducto


# ============================================================
# TEST: test_historial_por_producto_sin_movimientos
# ¿QUE PRUEBA? Que un producto sin movimientos devuelva lista vacia.
# ============================================================
def test_historial_por_producto_sin_movimientos(session) -> None:
    producto = _crear_producto(session)
    servicio = InventarioService()

    historial = servicio.historial_por_producto(
        producto_id=producto.idproducto, db_session=session  # type: ignore[arg-type]
    )
    assert historial == []


# ============================================================
# TEST: test_stock_disponible_suficiente
# ¿QUE PRUEBA? Que stock_disponible() retorne True si hay stock.
# ============================================================
def test_stock_disponible_suficiente(session) -> None:
    producto = _crear_producto(session, stock=10)
    servicio = InventarioService()

    assert servicio.stock_disponible(
        producto_id=producto.idproducto, cantidad=5, db_session=session  # type: ignore[arg-type]
    ) is True

    # Exactamente el stock disponible tambien debe ser True.
    assert servicio.stock_disponible(
        producto_id=producto.idproducto, cantidad=10, db_session=session  # type: ignore[arg-type]
    ) is True


# ============================================================
# TEST: test_stock_disponible_insuficiente
# ¿QUE PRUEBA? Que stock_disponible() retorne False si falta stock.
# ============================================================
def test_stock_disponible_insuficiente(session) -> None:
    producto = _crear_producto(session, stock=3)
    servicio = InventarioService()

    assert servicio.stock_disponible(
        producto_id=producto.idproducto, cantidad=10, db_session=session  # type: ignore[arg-type]
    ) is False


# ============================================================
# TEST: test_stock_disponible_producto_inexistente
# ¿QUE PRUEBA? Que stock_disponible() retorne False si no existe.
# ============================================================
def test_stock_disponible_producto_inexistente(session) -> None:
    servicio = InventarioService()
    assert servicio.stock_disponible(producto_id=9999, cantidad=1, db_session=session) is False


# ============================================================
# TEST: test_movimientos_recientes
# ¿QUE PRUEBA? Que movimientos_recientes() devuelva los ultimos N.
# ============================================================
def test_movimientos_recientes(session) -> None:
    """Crear 2 productos con movimientos y verificar el listado global."""
    prod1 = _crear_producto(session, nombre="PROD1", stock=50)
    prod2 = _crear_producto(session, nombre="PROD2", stock=30)
    servicio = InventarioService()

    servicio.registrar_entrada(
        producto_id=prod1.idproducto, cantidad=10, motivo="COMPRA", db_session=session  # type: ignore[arg-type]
    )
    servicio.registrar_salida(
        producto_id=prod2.idproducto, cantidad=5, motivo="VENTA", db_session=session  # type: ignore[arg-type]
    )

    recientes = servicio.movimientos_recientes(limite=10, db_session=session)

    assert len(recientes) == 2

    # El primero debe ser la SALIDA (mas reciente), luego la ENTRADA.
    assert recientes[0].tipo == "SALIDA"
    assert recientes[1].tipo == "ENTRADA"


# ============================================================
# TEST: test_movimientos_recientes_sin_movimientos
# ¿QUE PRUEBA? Que movimientos_recientes() devuelva lista vacia.
# ============================================================
def test_movimientos_recientes_sin_movimientos(session) -> None:
    servicio = InventarioService()
    recientes = servicio.movimientos_recientes(db_session=session)
    assert recientes == []
