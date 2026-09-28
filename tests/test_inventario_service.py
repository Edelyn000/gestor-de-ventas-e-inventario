from decimal import Decimal

import pytest
from sqlmodel import Session

from sistema_financiero.core.inventario_service import InventarioService
from sistema_financiero.models import Producto

pytestmark = pytest.mark.unitarias


# Crea un producto de prueba en la sesion.
def _crear_producto(
    session: Session, nombre: str = "PROD TEST", stock: Decimal = Decimal("50")
) -> Producto:
    producto = Producto(
        nombre_producto=nombre,
        precio_venta_bs=Decimal("10.00"),
        precio_venta_usd=Decimal("2.00"),
        stock_actual=stock,
        stock_minimo=Decimal("5"),
    )
    session.add(producto)
    session.commit()
    session.refresh(producto)
    assert producto.idproducto is not None
    return producto


# Prueba que una entrada suma stock y registra el movimiento.
def test_registrar_entrada_exitoso(session: Session) -> None:
    producto = _crear_producto(session)
    assert producto.idproducto is not None
    servicio = InventarioService()
    cantidad_entrada = Decimal("10")

    movimiento = servicio.registrar_entrada(
        producto_id=producto.idproducto,
        cantidad=cantidad_entrada,
        motivo="COMPRA",
        db_session=session,
    )

    assert movimiento is not None
    assert movimiento.producto_id == producto.idproducto
    assert movimiento.tipo == "ENTRADA"
    assert movimiento.motivo == "COMPRA"
    assert movimiento.cantidad == cantidad_entrada
    assert movimiento.stock_anterior == 50
    assert movimiento.stock_nuevo == 60

    session.refresh(producto)
    assert producto.stock_actual == Decimal("60")


# Prueba que la entrada rechaza cantidades invalidas.
def test_registrar_entrada_cantidad_invalida(session: Session) -> None:
    producto = _crear_producto(session)
    assert producto.idproducto is not None
    servicio = InventarioService()

    with pytest.raises(ValueError, match="debe ser mayor a cero"):
        servicio.registrar_entrada(
            producto_id=producto.idproducto,
            cantidad=Decimal("0"),
            motivo="COMPRA",
            db_session=session,
        )

    with pytest.raises(ValueError, match="debe ser mayor a cero"):
        servicio.registrar_entrada(
            producto_id=producto.idproducto,
            cantidad=Decimal("-5"),
            motivo="COMPRA",
            db_session=session,
        )


# Prueba que la entrada falla si el producto no existe.
def test_registrar_entrada_producto_inexistente(session: Session) -> None:
    servicio = InventarioService()
    with pytest.raises(ValueError, match="no existe"):
        servicio.registrar_entrada(
            producto_id=9999, cantidad=Decimal("5"), motivo="COMPRA", db_session=session
        )


# Prueba que una salida resta stock y registra el movimiento.
def test_registrar_salida_exitoso(session: Session) -> None:
    producto = _crear_producto(session, stock=Decimal("30"))
    assert producto.idproducto is not None
    servicio = InventarioService()
    cantidad_salida = Decimal("5")

    movimiento = servicio.registrar_salida(
        producto_id=producto.idproducto,
        cantidad=cantidad_salida,
        motivo="VENTA",
        db_session=session,
    )

    assert movimiento.tipo == "SALIDA"
    assert movimiento.motivo == "VENTA"
    assert movimiento.stock_anterior == 30
    assert movimiento.stock_nuevo == 25

    session.refresh(producto)
    assert producto.stock_actual == Decimal("25")


# Prueba que la salida rechaza stock insuficiente.
def test_registrar_salida_stock_insuficiente(session: Session) -> None:
    producto = _crear_producto(session, stock=Decimal("3"))
    assert producto.idproducto is not None
    servicio = InventarioService()

    with pytest.raises(ValueError, match="Stock insuficiente"):
        servicio.registrar_salida(
            producto_id=producto.idproducto,
            cantidad=Decimal("10"),
            motivo="VENTA",
            db_session=session,
        )

    session.refresh(producto)
    assert producto.stock_actual == Decimal("3")


# Prueba que la salida rechaza cantidades invalidas.
def test_registrar_salida_cantidad_invalida(session: Session) -> None:
    producto = _crear_producto(session)
    assert producto.idproducto is not None
    servicio = InventarioService()

    with pytest.raises(ValueError, match="debe ser mayor a cero"):
        servicio.registrar_salida(
            producto_id=producto.idproducto,
            cantidad=Decimal("0"),
            motivo="MERMA",
            db_session=session,
        )


# Prueba un ajuste que aumenta el stock.
def test_registrar_ajuste_exitoso_aumento(session: Session) -> None:
    producto = _crear_producto(session, stock=Decimal("50"))
    assert producto.idproducto is not None
    servicio = InventarioService()

    movimiento = servicio.registrar_ajuste(
        producto_id=producto.idproducto,
        stock_fisico=Decimal("60"),
        motivo="INVENTARIO FISICO",
        db_session=session,
    )

    assert movimiento.tipo == "AJUSTE"
    assert movimiento.stock_anterior == 50
    assert movimiento.stock_nuevo == 60
    assert movimiento.cantidad == 10

    session.refresh(producto)
    assert producto.stock_actual == Decimal("60")


# Prueba un ajuste que disminuye el stock.
def test_registrar_ajuste_exitoso_disminucion(session: Session) -> None:
    producto = _crear_producto(session, stock=Decimal("50"))
    assert producto.idproducto is not None
    servicio = InventarioService()

    movimiento = servicio.registrar_ajuste(
        producto_id=producto.idproducto,
        stock_fisico=Decimal("30"),
        db_session=session,
    )

    assert movimiento.stock_anterior == 50
    assert movimiento.stock_nuevo == 30

    session.refresh(producto)
    assert producto.stock_actual == Decimal("30")


# Prueba que un ajuste sin cambio no crea movimiento.
def test_registrar_ajuste_sin_cambio(session: Session) -> None:
    producto = _crear_producto(session, stock=Decimal("50"))
    assert producto.idproducto is not None
    servicio = InventarioService()

    with pytest.raises(ValueError, match="No hay nada que ajustar"):
        servicio.registrar_ajuste(
            producto_id=producto.idproducto,
            stock_fisico=Decimal("50"),
            db_session=session,
        )


# Prueba que el ajuste rechaza stock negativo.
def test_registrar_ajuste_stock_negativo(session: Session) -> None:
    producto = _crear_producto(session)
    assert producto.idproducto is not None
    servicio = InventarioService()

    with pytest.raises(ValueError, match="no puede ser negativo"):
        servicio.registrar_ajuste(
            producto_id=producto.idproducto,
            stock_fisico=Decimal("-1"),
            db_session=session,
        )


# Prueba el historial de movimientos de un producto.
def test_historial_por_producto(session: Session) -> None:
    producto = _crear_producto(session, stock=Decimal("100"))
    assert producto.idproducto is not None
    servicio = InventarioService()

    servicio.registrar_entrada(
        producto_id=producto.idproducto, cantidad=Decimal("10"), motivo="COMPRA", db_session=session
    )
    servicio.registrar_salida(
        producto_id=producto.idproducto, cantidad=Decimal("5"), motivo="VENTA", db_session=session
    )
    servicio.registrar_ajuste(
        producto_id=producto.idproducto, stock_fisico=Decimal("110"), db_session=session
    )

    historial = servicio.historial_por_producto(producto_id=producto.idproducto, db_session=session)

    assert len(historial) == 3

    assert historial[0].tipo == "AJUSTE"
    assert historial[1].tipo == "SALIDA"
    assert historial[2].tipo == "ENTRADA"

    for mov in historial:
        assert mov.producto_id == producto.idproducto


# Prueba que devuelve vacio sin movimientos.
def test_historial_por_producto_sin_movimientos(session: Session) -> None:
    producto = _crear_producto(session)
    assert producto.idproducto is not None
    servicio = InventarioService()

    historial = servicio.historial_por_producto(producto_id=producto.idproducto, db_session=session)
    assert historial == []


# Prueba que hay stock disponible suficiente.
def test_stock_disponible_suficiente(session: Session) -> None:
    producto = _crear_producto(session, stock=Decimal("10"))
    assert producto.idproducto is not None
    servicio = InventarioService()

    assert (
        servicio.stock_disponible(
            producto_id=producto.idproducto, cantidad=Decimal("5"), db_session=session
        )
        is True
    )

    assert (
        servicio.stock_disponible(
            producto_id=producto.idproducto, cantidad=Decimal("10"), db_session=session
        )
        is True
    )


# Prueba que detecta stock insuficiente.
def test_stock_disponible_insuficiente(session: Session) -> None:
    producto = _crear_producto(session, stock=Decimal("3"))
    assert producto.idproducto is not None
    servicio = InventarioService()

    assert (
        servicio.stock_disponible(
            producto_id=producto.idproducto, cantidad=Decimal("10"), db_session=session
        )
        is False
    )


# Prueba que falla si el producto no existe.
def test_stock_disponible_producto_inexistente(session: Session) -> None:
    servicio = InventarioService()
    assert (
        servicio.stock_disponible(producto_id=9999, cantidad=Decimal("1"), db_session=session)
        is False
    )


# Prueba listar los movimientos mas recientes.
def test_movimientos_recientes(session: Session) -> None:
    prod1 = _crear_producto(session, nombre="PROD1", stock=Decimal("50"))
    assert prod1.idproducto is not None
    prod2 = _crear_producto(session, nombre="PROD2", stock=Decimal("30"))
    assert prod2.idproducto is not None
    servicio = InventarioService()

    servicio.registrar_entrada(
        producto_id=prod1.idproducto, cantidad=Decimal("10"), motivo="COMPRA", db_session=session
    )
    servicio.registrar_salida(
        producto_id=prod2.idproducto, cantidad=Decimal("5"), motivo="VENTA", db_session=session
    )

    recientes = servicio.movimientos_recientes(limite=10, db_session=session)

    assert len(recientes) == 2

    assert recientes[0].tipo == "SALIDA"
    assert recientes[1].tipo == "ENTRADA"


# Prueba que devuelve vacio sin movimientos.
def test_movimientos_recientes_sin_movimientos(session: Session) -> None:
    servicio = InventarioService()
    recientes = servicio.movimientos_recientes(db_session=session)
    assert recientes == []
